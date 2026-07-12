from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.event_bus import (
    EVENT_ALARM_ACTIVE,
    EVENT_ALARM_CLEARED,
    EVENT_ALARM_UPDATE,
    Event,
    EventBus,
    event_bus,
)
from app.database import SessionLocal
from app.logger import logger
from app.models.alarm_event import AlarmEvent
from app.models.device import Device
from app.models.device_offline_settings import DeviceOfflineSettings


class DeviceOfflineMonitor:
    """Monitors device last_seen timestamps and creates/clears DEVICE_OFFLINE alarms."""

    def __init__(
        self,
        check_interval_seconds: int = 60,
        startup_grace_seconds: int = 120,
        bus: EventBus | None = None,
    ) -> None:
        self._check_interval = check_interval_seconds
        self._startup_grace = startup_grace_seconds
        self._bus = bus or event_bus
        self._task: asyncio.Task | None = None
        self._started_at: datetime | None = None

    def start(self) -> None:
        if self._task is not None:
            logger.warning("DeviceOfflineMonitor already running")
            return
        self._started_at = datetime.now(UTC)
        self._task = asyncio.create_task(self._run_loop())
        logger.info("DeviceOfflineMonitor started (check_interval=%ds, startup_grace=%ds)", self._check_interval, self._startup_grace)

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            logger.info("DeviceOfflineMonitor stopped")

    async def _run_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._check_interval)
                await self._check_devices()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("DeviceOfflineMonitor check failed")

    async def _check_devices(self) -> None:
        """Check all devices for offline status and create/clear alarms."""
        db: Session = SessionLocal()
        try:
            settings_row = db.query(DeviceOfflineSettings).first()
            if settings_row is None or not settings_row.enabled:
                return

            timeout_minutes = settings_row.offline_timeout_minutes
            severity = settings_row.severity
            telegram_enabled = settings_row.notifications_enabled
            now = datetime.now(UTC)

            # Respect startup grace period
            if self._started_at and (now - self._started_at).total_seconds() < self._startup_grace:
                logger.debug("DeviceOfflineMonitor still in startup grace period")
                return

            devices = db.query(Device).all()

            for device in devices:
                if device.last_seen is None:
                    # Device never communicated - skip
                    continue

                last_seen = device.last_seen
                # Handle naive datetime from SQLite
                if last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=UTC)

                offline_delta = now - last_seen
                is_offline = offline_delta > timedelta(minutes=timeout_minutes)

                if is_offline:
                    await self._handle_offline(db, device, severity, telegram_enabled)
                else:
                    await self._handle_online(db, device)
        finally:
            db.close()

    async def _handle_offline(
        self, db: Session, device: Device, severity: str, telegram_enabled: bool
    ) -> None:
        """Create DEVICE_OFFLINE alarm if not already active."""
        # Check if an active DEVICE_OFFLINE alarm already exists for this device
        # Use AlarmEvent model since that's what the alarms API returns
        existing = (
            db.query(AlarmEvent)
            .filter(
                AlarmEvent.device_id == device.id,
                AlarmEvent.alarm_type == "DEVICE_OFFLINE",
                AlarmEvent.state == "ACTIVE",
            )
            .first()
        )
        if existing is not None:
            # Alarm already exists - no duplicate
            return

        display_name = device.display_name or device.name
        message = f"Device {display_name} is offline"
        now = datetime.now(UTC)

        # Update device online status
        device.online = False
        db.commit()

        # Create AlarmEvent record (used by alarms API)
        event = AlarmEvent(
            sensor_id=None,
            device_id=device.id,
            alarm_type="DEVICE_OFFLINE",
            threshold=None,
            temperature=None,
            state="ACTIVE",
            activated_at=now,
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        logger.warning("DEVICE_OFFLINE alarm created for device %s (id=%d)", display_name, device.id)

        # Publish event for NotificationService (Telegram)
        self._bus.publish(
            Event(
                event_type=EVENT_ALARM_ACTIVE,
                source="DeviceOfflineMonitor",
                payload={
                    "alarm_id": event.id,
                    "event_id": event.id,
                    "type": "DEVICE_OFFLINE",
                    "state": "ACTIVE",
                    "severity": severity,
                    "device_id": device.id,
                    "device_name": device.name,
                    "device_display_name": display_name,
                    "sensor_id": None,
                    "message": message,
                    "title": f"Device Offline: {display_name}",
                    "telegram_enabled": telegram_enabled,
                },
            )
        )

        # Publish event for WebSocket
        self._bus.publish(
            Event(
                event_type=EVENT_ALARM_UPDATE,
                source="DeviceOfflineMonitor",
                payload={
                    "alarm_id": event.id,
                    "event_id": event.id,
                    "type": "DEVICE_OFFLINE",
                    "state": "ACTIVE",
                    "severity": severity,
                    "device_id": device.id,
                    "device_name": device.name,
                    "device_display_name": display_name,
                    "sensor_id": None,
                    "message": message,
                    "title": f"Device Offline: {display_name}",
                },
            )
        )

    async def _handle_online(self, db: Session, device: Device) -> None:
        """Clear active DEVICE_OFFLINE alarm if device is back online."""
        existing = (
            db.query(AlarmEvent)
            .filter(
                AlarmEvent.device_id == device.id,
                AlarmEvent.alarm_type == "DEVICE_OFFLINE",
                AlarmEvent.state == "ACTIVE",
            )
            .first()
        )
        if existing is None:
            return

        display_name = device.display_name or device.name
        now = datetime.now(UTC)

        # Update device online status
        device.online = True
        db.commit()

        # Clear the AlarmEvent record
        existing.state = "CLEARED"
        existing.cleared_at = now
        db.commit()

        logger.info("DEVICE_OFFLINE alarm cleared for device %s (id=%d)", display_name, device.id)

        self._bus.publish(
            Event(
                event_type=EVENT_ALARM_CLEARED,
                source="DeviceOfflineMonitor",
                payload={
                    "alarm_id": existing.id,
                    "type": "DEVICE_OFFLINE",
                    "state": "CLEARED",
                    "severity": existing.alarm_type,
                    "device_id": device.id,
                    "device_name": device.name,
                    "device_display_name": display_name,
                    "sensor_id": None,
                    "message": f"Device {display_name} is back online",
                    "title": f"Device Online: {display_name}",
                },
            )
        )


# Singleton instance
device_offline_monitor = DeviceOfflineMonitor()
