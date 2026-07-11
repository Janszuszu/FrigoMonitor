from __future__ import annotations

from datetime import datetime, UTC, timedelta
from typing import Optional

from sqlalchemy.exc import SQLAlchemyError

from app.core.event_bus import (
    EVENT_ALARM_UPDATE,
    Event,
    event_bus,
)
from app.database import SessionLocal
from app.logger import logger
from app.models.alarm import Alarm
from app.models.alarm_event import AlarmEvent
from app.models.sensor import Sensor


class AlarmState:
    NORMAL = "NORMAL"
    PENDING_HIGH = "PENDING_HIGH"
    PENDING_LOW = "PENDING_LOW"
    ALARM_HIGH = "ALARM_HIGH"
    ALARM_LOW = "ALARM_LOW"
    NO_DATA = "NO_DATA"
    CLEARED = "CLEARED"


class AlarmService:
    def process_measurement(
        self,
        sensor_id: int,
        value: float,
        timestamp: datetime,
        measurement_id: Optional[int] = None,
        session: Optional[SessionLocal] = None,
    ) -> None:
        if timestamp is None:
            timestamp = datetime.now(UTC)

        def _process(s):
            sensor = s.query(Sensor).filter(Sensor.id == sensor_id).one_or_none()
            if sensor is None:
                logger.warning("AlarmService: unknown sensor %s", sensor_id)
                return

            # Update last_measurement for no-data detection
            sensor.last_measurement = timestamp

            if not sensor.alarm_enabled:
                self._clear_any_alarm(s, sensor, measurement_id, "Alarm disabled")
                return

            # Check no-data alarm - if we got a measurement, clear no-data state
            if sensor.alarm_no_data_state == AlarmState.NO_DATA:
                self._clear_no_data(s, sensor, measurement_id)

            low = sensor.alarm_low
            high = sensor.alarm_high
            delay = sensor.alarm_activation_delay or 0

            if low is None and high is None:
                self._clear_any_alarm(s, sensor, measurement_id, "No thresholds configured")
                return

            if low is not None and high is not None and low >= high:
                self._clear_any_alarm(s, sensor, measurement_id, "Invalid thresholds")
                return

            self._evaluate_sensor(s, sensor, value, timestamp, measurement_id, low, high, delay)

        if session is not None:
            _process(session)
        else:
            try:
                with SessionLocal() as s:
                    _process(s)
            except SQLAlchemyError:
                logger.exception("Database error in AlarmService.process_measurement")

    def check_no_data_alarms(self, session: Optional[SessionLocal] = None) -> None:
        """Check all sensors for no-data condition. Called periodically."""
        def _check(s):
            sensors = s.query(Sensor).filter(Sensor.alarm_enabled == True).all()  # noqa: E712
            now = datetime.now(UTC)
            for sensor in sensors:
                if not sensor.alarm_no_data_enabled:
                    continue
                if sensor.last_measurement is None:
                    continue
                last = self._normalize_timestamp(sensor.last_measurement)
                timeout = timedelta(minutes=sensor.alarm_no_data_timeout or 15)
                if now - last >= timeout:
                    if sensor.alarm_no_data_state != AlarmState.NO_DATA:
                        self._activate_no_data(s, sensor, now)

        if session is not None:
            _check(session)
        else:
            try:
                with SessionLocal() as s:
                    _check(s)
            except SQLAlchemyError:
                logger.exception("Database error in AlarmService.check_no_data_alarms")

    def _evaluate_sensor(
        self,
        session,
        sensor: Sensor,
        value: float,
        timestamp: datetime,
        measurement_id: Optional[int],
        low: Optional[float],
        high: Optional[float],
        delay: int,
    ) -> None:
        timestamp = self._normalize_timestamp(timestamp)
        current_state = sensor.alarm_state

        # Determine if we're outside bounds
        is_high = high is not None and value > high
        is_low = low is not None and value < low

        if not is_high and not is_low:
            # Within normal range - clear any pending or active alarms
            if current_state in (AlarmState.PENDING_HIGH, AlarmState.PENDING_LOW,
                                 AlarmState.ALARM_HIGH, AlarmState.ALARM_LOW):
                self._clear_alarm(session, sensor, measurement_id, "Temperature returned to normal")
            return

        # We're outside bounds
        if is_high:
            target_state = AlarmState.ALARM_HIGH
            target_pending = AlarmState.PENDING_HIGH
        else:
            target_state = AlarmState.ALARM_LOW
            target_pending = AlarmState.PENDING_LOW

        if current_state == AlarmState.NORMAL:
            if delay > 0:
                self._transition_to_pending(session, sensor, target_pending, timestamp, measurement_id, value, high if is_high else low)
            else:
                self._activate_alarm(session, sensor, target_state, timestamp, measurement_id, value, high if is_high else low)
            return

        if current_state == target_pending:
            # Check if we need to switch direction (e.g., was pending low, now high)
            if sensor.alarm_level != target_state:
                self._transition_to_pending(session, sensor, target_pending, timestamp, measurement_id, value, high if is_high else low)
                return

            # Still in pending - check if delay has elapsed
            if sensor.alarm_pending_since is None:
                sensor.alarm_pending_since = timestamp
                session.commit()
                return

            pending_since = self._normalize_timestamp(sensor.alarm_pending_since)
            if timestamp - pending_since >= timedelta(seconds=delay):
                self._activate_alarm(session, sensor, target_state, timestamp, measurement_id, value, high if is_high else low)
            return

        if current_state == target_state:
            # Already active, just update temperature
            self._update_alarm_temperature(session, sensor, measurement_id, value)
            return

        # If we're in some other state, transition to pending/active as appropriate
        if delay > 0:
            self._transition_to_pending(session, sensor, target_pending, timestamp, measurement_id, value, high if is_high else low)
        else:
            self._activate_alarm(session, sensor, target_state, timestamp, measurement_id, value, high if is_high else low)

    def _clear_any_alarm(self, session, sensor: Sensor, measurement_id: Optional[int], message: str) -> None:
        """Clear any non-normal alarm state."""
        if sensor.alarm_state != AlarmState.NORMAL:
            self._clear_alarm(session, sensor, measurement_id, message)
        if sensor.alarm_no_data_state == AlarmState.NO_DATA:
            self._clear_no_data(session, sensor, measurement_id)

    def _clear_alarm(self, session, sensor: Sensor, measurement_id: Optional[int], message: str) -> None:
        old_state = sensor.alarm_state
        old_level = sensor.alarm_level
        sensor.alarm_state = AlarmState.NORMAL
        sensor.alarm_level = None
        sensor.alarm_pending_since = None
        session.commit()

        # Update alarm event if exists
        if old_state in (AlarmState.PENDING_HIGH, AlarmState.PENDING_LOW,
                         AlarmState.ALARM_HIGH, AlarmState.ALARM_LOW):
            self._update_alarm_event_cleared(session, sensor, old_level)

        self._create_alarm_event(session, sensor, measurement_id, AlarmState.CLEARED, old_level or "", message)
        self._publish_alarm_event(sensor, measurement_id, AlarmState.NORMAL, None, message)
        logger.info("Alarm cleared for sensor %s: %s", sensor.id, message)

    def _clear_no_data(self, session, sensor: Sensor, measurement_id: Optional[int]) -> None:
        sensor.alarm_no_data_state = AlarmState.NORMAL
        sensor.alarm_no_data_since = None
        session.commit()
        self._update_alarm_event_cleared(session, sensor, AlarmState.NO_DATA)
        self._create_alarm_event(session, sensor, measurement_id, AlarmState.CLEARED, AlarmState.NO_DATA, "No-data alarm cleared")
        self._publish_alarm_event(sensor, measurement_id, AlarmState.NORMAL, None, "No-data alarm cleared")
        logger.info("No-data alarm cleared for sensor %s", sensor.id)

    def _transition_to_pending(
        self,
        session,
        sensor: Sensor,
        pending_state: str,
        timestamp: datetime,
        measurement_id: Optional[int],
        value: float,
        threshold: Optional[float],
    ) -> None:
        sensor.alarm_state = pending_state
        sensor.alarm_level = AlarmState.ALARM_HIGH if "HIGH" in pending_state else AlarmState.ALARM_LOW
        sensor.alarm_pending_since = timestamp
        session.commit()

        self._create_alarm_event(
            session,
            sensor,
            measurement_id,
            pending_state,
            sensor.alarm_level,
            f"Alarm pending: {sensor.alarm_level}",
            threshold=threshold,
            temperature=value,
            pending_start=timestamp,
        )
        self._publish_alarm_event(sensor, measurement_id, pending_state, sensor.alarm_level, f"Alarm pending: {sensor.alarm_level}")
        logger.info("Alarm pending for sensor %s: %s", sensor.id, sensor.alarm_level)

    def _activate_alarm(
        self,
        session,
        sensor: Sensor,
        active_state: str,
        timestamp: datetime,
        measurement_id: Optional[int],
        value: float,
        threshold: Optional[float],
    ) -> None:
        sensor.alarm_state = active_state
        sensor.alarm_level = AlarmState.ALARM_HIGH if "HIGH" in active_state else AlarmState.ALARM_LOW
        sensor.alarm_pending_since = None
        session.commit()

        # Update the pending event to activated
        self._update_alarm_event_activated(session, sensor, timestamp)

        self._create_alarm_event(
            session,
            sensor,
            measurement_id,
            active_state,
            sensor.alarm_level,
            f"Alarm activated: {sensor.alarm_level}",
            threshold=threshold,
            temperature=value,
            activated_at=timestamp,
        )
        self._publish_alarm_event(sensor, measurement_id, active_state, sensor.alarm_level, f"Alarm activated: {sensor.alarm_level}")
        logger.info("Alarm activated for sensor %s: %s", sensor.id, sensor.alarm_level)

    def _activate_no_data(self, session, sensor: Sensor, timestamp: datetime) -> None:
        sensor.alarm_no_data_state = AlarmState.NO_DATA
        sensor.alarm_no_data_since = timestamp
        session.commit()

        self._create_alarm_event(
            session,
            sensor,
            None,
            AlarmState.NO_DATA,
            AlarmState.NO_DATA,
            "No data received",
            activated_at=timestamp,
        )
        self._publish_alarm_event(sensor, None, AlarmState.NO_DATA, AlarmState.NO_DATA, "No data received")
        logger.info("No-data alarm activated for sensor %s", sensor.id)

    def _update_alarm_temperature(self, session, sensor: Sensor, measurement_id: Optional[int], value: float) -> None:
        """Update the latest temperature for an active alarm event."""
        # Find the latest active alarm event and update its temperature
        latest = (
            session.query(AlarmEvent)
            .filter(
                AlarmEvent.sensor_id == sensor.id,
                AlarmEvent.state.in_([AlarmState.ALARM_HIGH, AlarmState.ALARM_LOW]),
            )
            .order_by(AlarmEvent.id.desc())
            .first()
        )
        if latest is not None:
            latest.temperature = value
            session.commit()

    def _update_alarm_event_activated(self, session, sensor: Sensor, timestamp: datetime) -> None:
        """Update the pending alarm event with activation timestamp."""
        latest = (
            session.query(AlarmEvent)
            .filter(
                AlarmEvent.sensor_id == sensor.id,
                AlarmEvent.state.in_([AlarmState.PENDING_HIGH, AlarmState.PENDING_LOW]),
            )
            .order_by(AlarmEvent.id.desc())
            .first()
        )
        if latest is not None:
            latest.state = AlarmState.ALARM_HIGH if "HIGH" in latest.alarm_type else AlarmState.ALARM_LOW
            latest.activated_at = timestamp
            session.commit()

    def _update_alarm_event_cleared(self, session, sensor: Sensor, alarm_type: Optional[str]) -> None:
        """Update the active/pending alarm event with clear timestamp."""
        if alarm_type is None:
            return
        states = [AlarmState.PENDING_HIGH, AlarmState.PENDING_LOW, AlarmState.ALARM_HIGH, AlarmState.ALARM_LOW, AlarmState.NO_DATA]
        latest = (
            session.query(AlarmEvent)
            .filter(
                AlarmEvent.sensor_id == sensor.id,
                AlarmEvent.state.in_(states),
            )
            .order_by(AlarmEvent.id.desc())
            .first()
        )
        if latest is not None:
            latest.state = AlarmState.CLEARED
            latest.cleared_at = datetime.now(UTC)
            session.commit()

    def _create_alarm_event(
        self,
        session,
        sensor: Sensor,
        measurement_id: Optional[int],
        state: str,
        alarm_type: str,
        message: str,
        threshold: Optional[float] = None,
        temperature: Optional[float] = None,
        pending_start: Optional[datetime] = None,
        activated_at: Optional[datetime] = None,
    ) -> None:
        alarm = Alarm(
            device_id=sensor.device_id,
            sensor_id=sensor.id,
            measurement_id=measurement_id,
            level=alarm_type or "",
            state=state,
            message=message,
            active=state not in (AlarmState.NORMAL, AlarmState.CLEARED),
        )
        session.add(alarm)
        session.commit()

        # Also create AlarmEvent for history
        event = AlarmEvent(
            sensor_id=sensor.id,
            device_id=sensor.device_id,
            alarm_type=alarm_type or state,
            threshold=threshold,
            temperature=temperature,
            state=state,
            pending_start=pending_start,
            activated_at=activated_at,
        )
        session.add(event)
        session.commit()

    def _publish_alarm_event(
        self,
        sensor: Sensor,
        measurement_id: Optional[int],
        state: str,
        level: Optional[str],
        message: str,
    ) -> None:
        if state not in (AlarmState.PENDING_HIGH, AlarmState.PENDING_LOW,
                         AlarmState.ALARM_HIGH, AlarmState.ALARM_LOW,
                         AlarmState.NO_DATA, AlarmState.NORMAL, AlarmState.CLEARED):
            return

        event_bus.publish(
            Event(
                event_type=EVENT_ALARM_UPDATE,
                source="AlarmService",
                payload={
                    "device_id": sensor.device_id,
                    "sensor_id": sensor.id,
                    "measurement_id": measurement_id,
                    "state": state,
                    "alarm_state": state,
                    "level": level,
                    "message": message,
                },
            )
        )

    def reset_alarm(self, alarm_event_id: int, session: Optional[SessionLocal] = None) -> bool:
        """Reset/acknowledge a single active alarm event.
        
        This clears the alarm event and resets the sensor state to NORMAL,
        but does NOT disable alarms or change thresholds.
        If the alarm condition is still active, the next measurement will
        re-evaluate and create a new alarm.
        
        Returns True if the alarm was found and reset, False otherwise.
        """
        def _reset(s):
            event = s.query(AlarmEvent).filter(AlarmEvent.id == alarm_event_id).one_or_none()
            if event is None:
                return False

            active_states = ["PENDING_HIGH", "PENDING_LOW", "ALARM_HIGH", "ALARM_LOW", "NO_DATA"]
            if event.state not in active_states:
                logger.warning("AlarmEvent %s is not active (state=%s), skipping reset", alarm_event_id, event.state)
                return False

            # Mark the alarm event as cleared
            event.state = AlarmState.CLEARED
            event.cleared_at = datetime.now(UTC)
            s.commit()

            # Reset the sensor's alarm state
            sensor = s.query(Sensor).filter(Sensor.id == event.sensor_id).one_or_none()
            if sensor is not None:
                if event.alarm_type in (AlarmState.NO_DATA, "NO_DATA"):
                    sensor.alarm_no_data_state = AlarmState.NORMAL
                    sensor.alarm_no_data_since = None
                else:
                    sensor.alarm_state = AlarmState.NORMAL
                    sensor.alarm_level = None
                    sensor.alarm_pending_since = None
                s.commit()

                # Publish alarm update event so WebSocket clients get notified
                self._publish_alarm_event(
                    sensor, None, AlarmState.CLEARED, event.alarm_type,
                    f"Alarm reset by user: {event.alarm_type}"
                )

            logger.info("Alarm %s reset by user for sensor %s", alarm_event_id, event.sensor_id)
            return True

        if session is not None:
            return _reset(session)
        else:
            try:
                with SessionLocal() as s:
                    return _reset(s)
            except SQLAlchemyError:
                logger.exception("Database error in AlarmService.reset_alarm")
                return False

    def reset_all_alarms(self, session: Optional[SessionLocal] = None) -> int:
        """Reset all currently active alarms.
        
        Returns the number of alarms that were reset.
        """
        def _reset_all(s):
            active_states = ["PENDING_HIGH", "PENDING_LOW", "ALARM_HIGH", "ALARM_LOW", "NO_DATA"]
            events = (
                s.query(AlarmEvent)
                .filter(AlarmEvent.state.in_(active_states))
                .all()
            )
            count = 0
            for event in events:
                event.state = AlarmState.CLEARED
                event.cleared_at = datetime.now(UTC)
                count += 1

                sensor = s.query(Sensor).filter(Sensor.id == event.sensor_id).one_or_none()
                if sensor is not None:
                    if event.alarm_type in (AlarmState.NO_DATA, "NO_DATA"):
                        sensor.alarm_no_data_state = AlarmState.NORMAL
                        sensor.alarm_no_data_since = None
                    else:
                        sensor.alarm_state = AlarmState.NORMAL
                        sensor.alarm_level = None
                        sensor.alarm_pending_since = None

                    self._publish_alarm_event(
                        sensor, None, AlarmState.CLEARED, event.alarm_type,
                        f"Alarm reset by user (bulk): {event.alarm_type}"
                    )

            s.commit()
            logger.info("Bulk reset: %s alarms cleared", count)
            return count

        if session is not None:
            return _reset_all(session)
        else:
            try:
                with SessionLocal() as s:
                    return _reset_all(s)
            except SQLAlchemyError:
                logger.exception("Database error in AlarmService.reset_all_alarms")
                return 0

    @staticmethod
    def _normalize_timestamp(timestamp: datetime) -> datetime:
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=UTC)
        return timestamp.astimezone(UTC)


alarm_service = AlarmService()


