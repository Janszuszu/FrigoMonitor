"""Device Offline Monitor.

Detects when devices have stopped communicating for longer than a
configured timeout and creates DEVICE_OFFLINE alarms through the
existing AlarmService / EventBus architecture.

Architecture:
    Device.last_seen
        |
        v
    DeviceOfflineMonitor (background asyncio task)
        |
        v
    AlarmService / Alarm model
        |
        v
    EventBus -> WebSocketManager + NotificationService

The monitor runs as a lightweight asyncio background task that
periodically checks all devices.  It does NOT depend on MQTT or
frontend timers.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, UTC
from typing import Optional

from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.core.event_bus import (
    EVENT_ALARM_ACTIVE,
    EVENT_ALARM_CLEARED,
    EVENT_ALARM_UPDATE,
    EVENT_DEVICE_ONLINE,
    EVENT_DEVICE_OFFLINE,
    EVENT_DEVICE_UPDATE,
    Event,
    event_bus,
)
from app.logger import logger
from app.models.device import Device
from app.models.alarm import Alarm
from app.models.device_offline_settings import DeviceOfflineSettings


# Severity mapping for EventBus notification routing
SEVERITY_MAP = {
    "INFO": "INFO",
    "WARNING": "WARNING",
    "CRITICAL": "CRITICAL",
}


class DeviceOfflineMonitor:
    """Background monitor that checks device last_seen timestamps.

    The monitor runs at a configurable interval (default 60 seconds)
    and checks all devices against the configured offline timeout.

    A startup grace period prevents false alarms immediately after
    backend startup / reboot.
    """

    def __init__(self, check_interval_seconds: int = 60) -> None:
        self._check_interval = check_interval_seconds
        self._task: Optional[asyncio.Task[None]] = None
        self._startup_time: Optional[datetime] = None
        self._grace_period_minutes: int = 2

    @property
    def startup_time(self) -> Optional[datetime]:
        return self._startup_time

    def start(self) -> None:
        """Start the background monitoring task."""
        self._startup_time = datetime.now(UTC)
        self._task = asyncio.create_task(self._run())
        logger.info(
            "DeviceOfflineMonitor started (check_interval=%ss, grace_period=%smin)",
            self._check_interval,
            self._grace_period_minutes,
        )

    async def stop(self) -> None:
        """Stop the background monitoring task."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            logger.info("DeviceOfflineMonitor stopped")

    async def _run(self) -> None:
        """Main monitoring loop."""
        while True:
            try:
                await asyncio.sleep(self._check_interval)
                self._check_devices()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("DeviceOfflineMonitor check failed")

    def _check_devices(self) -> None:
        """Check all devices for offline condition."""
        try:
            with SessionLocal() as session:
                settings = self._get_settings(session)
                if settings is None or not settings.enabled:
                    return

                timeout = timedelta(minutes=settings.offline_timeout_minutes)
                now = datetime.now(UTC)

                # Skip grace period check
                if self._startup_time is not None:
                    grace_end = self._startup_time + timedelta(minutes=self._grace_period_minutes)
                    if now < grace_end:
                        logger.debug(
                            "DeviceOfflineMonitor: within startup grace period "
                            "(until %s), skipping checks",
                            grace_end.isoformat(),
                        )
                        return

                devices = session.query(Device).all()
                for device in devices:
                    self._evaluate_device(session, device, now, timeout, settings)
        except SQLAlchemyError:
            logger.exception("DeviceOfflineMonitor: database error during check")

    def _evaluate_device(
        self,
        session,
        device: Device,
        now: datetime,
        timeout: timedelta,
        settings: DeviceOfflineSettings,
    ) -> None:
        """Evaluate a single device for offline condition."""
        if device.last_seen is None:
            # Device has never communicated - not yet ready to evaluate
            return

        last_seen = self._normalize_timestamp(device.last_seen)
        elapsed = now - last_seen
        is_offline = elapsed >= timeout

        if is_offline and device.online:
            # Device just went offline
            self._mark_device_offline(session, device, now, settings)
        elif not is_offline and not device.online:
            # Device came back online (last_seen updated by other code)
            self._clear_device_offline(session, device, now)

    def _mark_device_offline(
        self,
        session,
        device: Device,
        now: datetime,
        settings: DeviceOfflineSettings,
    ) -> None:
        """Mark device as offline and create DEVICE_OFFLINE alarm."""
        device.online = False
        session.commit()

        # Check for existing active DEVICE_OFFLINE alarm (duplicate prevention)
        existing = self._find_active_offline_alarm(session, device.id)
        if existing is not None:
            logger.debug(
                "Device %s already has active DEVICE_OFFLINE alarm, skipping",
                device.id,
            )
            return

        timeout_minutes = settings.offline_timeout_minutes
        device_name = device.display_name or device.name
        message = (
            f'Device "{device_name}" has been offline for more than '
            f"{timeout_minutes} minutes."
        )

        # Create Alarm record
        alarm = Alarm(
            device_id=device.id,
            sensor_id=None,
            measurement_id=None,
            state="ACTIVE",
            level="DEVICE_OFFLINE",
            message=message,
            active=True,
        )
        session.add(alarm)
        session.commit()

        logger.warning(
            "DEVICE_OFFLINE alarm created for device %s (id=%s): %s",
            device_name,
            device.id,
            message,
        )

        # Publish events through EventBus
        self._publish_device_offline_events(device, settings, message, now)

    def _clear_device_offline(
        self,
        session,
        device: Device,
        now: datetime,
    ) -> None:
        """Mark device as online and clear DEVICE_OFFLINE alarm."""
        device.online = True
        session.commit()

        # Find and clear the active DEVICE_OFFLINE alarm
        alarm = self._find_active_offline_alarm(session, device.id)
        if alarm is not None:
            alarm.state = "CLEARED"
            alarm.active = False
            session.commit()

            device_name = device.display_name or device.name
            logger.info(
                "DEVICE_OFFLINE alarm cleared for device %s (id=%s): "
                "device reconnected",
                device_name,
                device.id,
            )

        # Publish events through EventBus
        self._publish_device_online_events(device, now)

    def _find_active_offline_alarm(self, session, device_id: int) -> Optional[Alarm]:
        """Find an active DEVICE_OFFLINE alarm for the given device.

        Returns None if no active alarm exists.
        Prevents duplicate active alarms for the same device.
        """
        return (
            session.query(Alarm)
            .filter(
                Alarm.device_id == device_id,
                Alarm.level == "DEVICE_OFFLINE",
                Alarm.active == True,  # noqa: E712
                Alarm.state.in_(["PENDING", "ACTIVE", "ACKNOWLEDGED"]),
            )
            .order_by(Alarm.id.desc())
            .first()
        )

    def _publish_device_offline_events(
        self,
        device: Device,
        settings: DeviceOfflineSettings,
        message: str,
        now: datetime,
    ) -> None:
        """Publish events when a device goes offline."""
        severity = settings.severity.upper()
        device_name = device.display_name or device.name

        # Device offline event
        event_bus.publish(
            Event(
                event_type=EVENT_DEVICE_OFFLINE,
                source="DeviceOfflineMonitor",
                payload={
                    "device_id": device.id,
                    "device_uuid": device.device_id,
                    "device_name": device_name,
                    "serial_number": device.serial_number,
                    "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                    "online": False,
                },
            )
        )

        # Device update event (for WebSocket live updates)
        event_bus.publish(
            Event(
                event_type=EVENT_DEVICE_UPDATE,
                source="DeviceOfflineMonitor",
                payload={
                    "id": device.id,
                    "name": device.name,
                    "display_name": device.display_name,
                    "serial_number": device.serial_number,
                    "device_id": device.device_id,
                    "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                    "online": False,
                },
            )
        )

        # Alarm update event (for WebSocket live updates)
        event_bus.publish(
            Event(
                event_type=EVENT_ALARM_UPDATE,
                source="DeviceOfflineMonitor",
                payload={
                    "device_id": device.id,
                    "sensor_id": None,
                    "state": "ACTIVE",
                    "alarm_state": "ACTIVE",
                    "level": "DEVICE_OFFLINE",
                    "message": message,
                    "severity": severity,
                    "alarm_type": "DEVICE_OFFLINE",
                },
            )
        )

        # Alarm active event (for NotificationService routing)
        event_bus.publish(
            Event(
                event_type=EVENT_ALARM_ACTIVE,
                source="DeviceOfflineMonitor",
                payload={
                    "device_id": device.id,
                    "device": device_name,
                    "sensor_id": None,
                    "sensor": None,
                    "title": f"DEVICE OFFLINE: {device_name}",
                    "message": message,
                    "severity": severity,
                    "alarm_type": "DEVICE_OFFLINE",
                    "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                    "configured_timeout": settings.offline_timeout_minutes,
                },
            )
        )

    def _publish_device_online_events(
        self,
        device: Device,
        now: datetime,
    ) -> None:
        """Publish events when a device comes back online."""
        device_name = device.display_name or device.name

        # Device online event
        event_bus.publish(
            Event(
                event_type=EVENT_DEVICE_ONLINE,
                source="DeviceOfflineMonitor",
                payload={
                    "device_id": device.id,
                    "device_uuid": device.device_id,
                    "device_name": device_name,
                    "serial_number": device.serial_number,
                    "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                    "online": True,
                },
            )
        )

        # Device update event (for WebSocket live updates)
        event_bus.publish(
            Event(
                event_type=EVENT_DEVICE_UPDATE,
                source="DeviceOfflineMonitor",
                payload={
                    "id": device.id,
                    "name": device.name,
                    "display_name": device.display_name,
                    "serial_number": device.serial_number,
                    "device_id": device.device_id,
                    "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                    "online": True,
                },
            )
        )

        # Alarm update event (for WebSocket live updates)
        event_bus.publish(
            Event(
                event_type=EVENT_ALARM_UPDATE,
                source="DeviceOfflineMonitor",
                payload={
                    "device_id": device.id,
                    "sensor_id": None,
                    "state": "CLEARED",
                    "alarm_state": "CLEARED",
                    "level": "DEVICE_OFFLINE",
                    "message": f'Device "{device_name}" reconnected.',
                    "alarm_type": "DEVICE_OFFLINE",
                },
            )
        )

        # Alarm cleared event (for NotificationService routing)
        event_bus.publish(
            Event(
                event_type=EVENT_ALARM_CLEARED,
                source="DeviceOfflineMonitor",
                payload={
                    "device_id": device.id,
                    "device": device_name,
                    "sensor_id": None,
                    "sensor": None,
                    "title": f"DEVICE ONLINE: {device_name}",
                    "message": f'Device "{device_name}" has reconnected.',
                    "severity": "INFO",
                    "alarm_type": "DEVICE_OFFLINE",
                },
            )
        )

    def _get_settings(self, session) -> Optional[DeviceOfflineSettings]:
        """Get the device offline settings from the database."""
        settings = session.query(DeviceOfflineSettings).first()
        if settings is None:
            # Create default settings if none exist
            settings = DeviceOfflineSettings(
                enabled=True,
                offline_timeout_minutes=5,
                severity="CRITICAL",
                notifications_enabled=True,
            )
            session.add(settings)
            session.commit()
            session.refresh(settings)
        return settings

    @staticmethod
    def _normalize_timestamp(timestamp: datetime) -> datetime:
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=UTC)
        return timestamp.astimezone(UTC)


# Module-level singleton
device_offline_monitor = DeviceOfflineMonitor()
