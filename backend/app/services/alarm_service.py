from __future__ import annotations

from datetime import datetime, UTC, timedelta
from typing import Optional

from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.logger import logger
from app.models.alarm import Alarm
from app.models.sensor import Sensor


class AlarmState:
    NORMAL = "NORMAL"
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    CLEARED = "CLEARED"


class AlarmLevel:
    HIGH = "HIGH"
    LOW = "LOW"


class AlarmService:
    def process_measurement(
        self,
        sensor_id: int,
        value: float,
        timestamp: datetime,
        measurement_id: Optional[int] = None,
    ) -> None:
        if timestamp is None:
            timestamp = datetime.now(UTC)

        try:
            with SessionLocal() as session:
                sensor = session.query(Sensor).filter(Sensor.id == sensor_id).one_or_none()
                if sensor is None:
                    logger.warning("AlarmService: unknown sensor %s", sensor_id)
                    return

                if not sensor.alarm_enabled:
                    if sensor.alarm_state not in (AlarmState.NORMAL, AlarmState.CLEARED):
                        self._transition_state(session, sensor, AlarmState.CLEARED, None, measurement_id, "Alarm disabled")
                    return

                rule = self._resolve_rule(sensor)
                if rule is None:
                    logger.warning("Invalid rule for sensor %s", sensor.id)
                    return

                self._evaluate_sensor(session, sensor, value, timestamp, measurement_id, rule)
        except SQLAlchemyError:
            logger.exception("Database error in AlarmService.process_measurement")

    def acknowledge(self, sensor_id: int) -> None:
        try:
            with SessionLocal() as session:
                sensor = session.query(Sensor).filter(Sensor.id == sensor_id).one_or_none()
                if sensor is None:
                    logger.warning("AlarmService: unknown sensor %s", sensor_id)
                    return

                if sensor.alarm_state != AlarmState.ACTIVE:
                    return

                self._transition_state(
                    session,
                    sensor,
                    AlarmState.ACKNOWLEDGED,
                    sensor.alarm_level,
                    None,
                    "Alarm acknowledged",
                )
                logger.info("Alarm acknowledged for sensor %s", sensor_id)
        except SQLAlchemyError:
            logger.exception("Database error while acknowledging alarm")

    def clear(self, sensor_id: int) -> None:
        try:
            with SessionLocal() as session:
                sensor = session.query(Sensor).filter(Sensor.id == sensor_id).one_or_none()
                if sensor is None:
                    logger.warning("AlarmService: unknown sensor %s", sensor_id)
                    return

                if sensor.alarm_state == AlarmState.NORMAL:
                    return

                self._transition_state(session, sensor, AlarmState.CLEARED, None, None, "Alarm cleared")
                logger.info("Alarm cleared for sensor %s", sensor_id)
        except SQLAlchemyError:
            logger.exception("Database error while clearing alarm")

    def _resolve_rule(self, sensor: Sensor) -> Optional[dict[str, object]]:
        low = sensor.alarm_low
        high = sensor.alarm_high
        hysteresis = sensor.alarm_hysteresis or 0.0
        delay = sensor.alarm_activation_delay or 0

        if low is None and high is None:
            return None

        if low is not None and high is not None and low >= high:
            return None

        if hysteresis < 0 or delay < 0:
            return None

        return {
            "low": low,
            "high": high,
            "hysteresis": hysteresis,
            "delay": delay,
        }

    def _normalize_timestamp(self, timestamp: datetime) -> datetime:
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=UTC)
        return timestamp.astimezone(UTC)

    def _evaluate_sensor(
        self,
        session,
        sensor: Sensor,
        value: float,
        timestamp: datetime,
        measurement_id: Optional[int],
        rule: dict[str, object],
    ) -> None:
        timestamp = self._normalize_timestamp(timestamp)
        low = rule["low"]
        high = rule["high"]
        hysteresis = rule["hysteresis"]
        delay = rule["delay"]

        triggered_level = None
        if high is not None and value > high:
            triggered_level = AlarmLevel.HIGH
        elif low is not None and value < low:
            triggered_level = AlarmLevel.LOW

        if triggered_level is None:
            self._handle_clear_if_needed(session, sensor, value, hysteresis, measurement_id)
            return

        if sensor.alarm_state == AlarmState.PENDING:
            if sensor.alarm_level != triggered_level:
                self._transition_to_pending(session, sensor, triggered_level, timestamp, measurement_id)
                return

            if sensor.alarm_pending_since is None:
                sensor.alarm_pending_since = timestamp
                session.commit()
                return

            pending_since = self._normalize_timestamp(sensor.alarm_pending_since)
            if timestamp - pending_since >= timedelta(seconds=delay):
                self._transition_state(
                    session,
                    sensor,
                    AlarmState.ACTIVE,
                    triggered_level,
                    measurement_id,
                    f"Alarm activated: {triggered_level}",
                )
                logger.info("Alarm activated for sensor %s", sensor.id)
                return

            return

        if sensor.alarm_state in (AlarmState.ACTIVE, AlarmState.ACKNOWLEDGED):
            if sensor.alarm_level == triggered_level:
                return
            self._transition_to_pending(session, sensor, triggered_level, timestamp, measurement_id)
            return

        if sensor.alarm_state in (AlarmState.NORMAL, AlarmState.CLEARED):
            if delay > 0:
                self._transition_to_pending(session, sensor, triggered_level, timestamp, measurement_id)
                return

            self._transition_state(
                session,
                sensor,
                AlarmState.ACTIVE,
                triggered_level,
                measurement_id,
                f"Alarm activated: {triggered_level}",
            )
            logger.info("Alarm activated for sensor %s", sensor.id)
            return

    def _handle_clear_if_needed(
        self,
        session,
        sensor: Sensor,
        value: float,
        hysteresis: float,
        measurement_id: Optional[int],
    ) -> None:
        if sensor.alarm_state in (AlarmState.NORMAL, AlarmState.CLEARED):
            return

        if sensor.alarm_level == AlarmLevel.HIGH:
            threshold = (sensor.alarm_high or 0.0) - hysteresis
            if value <= threshold:
                self._transition_state(
                    session,
                    sensor,
                    AlarmState.CLEARED,
                    None,
                    measurement_id,
                    "Alarm cleared",
                )
                logger.info("Alarm cleared for sensor %s", sensor.id)
        elif sensor.alarm_level == AlarmLevel.LOW:
            threshold = (sensor.alarm_low or 0.0) + hysteresis
            if value >= threshold:
                self._transition_state(
                    session,
                    sensor,
                    AlarmState.CLEARED,
                    None,
                    measurement_id,
                    "Alarm cleared",
                )
                logger.info("Alarm cleared for sensor %s", sensor.id)

    def _transition_to_pending(
        self,
        session,
        sensor: Sensor,
        level: str,
        timestamp: datetime,
        measurement_id: Optional[int],
    ) -> None:
        sensor.alarm_state = AlarmState.PENDING
        sensor.alarm_level = level
        sensor.alarm_pending_since = timestamp
        session.commit()
        self._create_alarm_event(
            session,
            sensor,
            measurement_id,
            AlarmState.PENDING,
            level,
            f"Alarm pending: {level}",
        )

    def _transition_state(
        self,
        session,
        sensor: Sensor,
        state: str,
        level: Optional[str],
        measurement_id: Optional[int],
        message: str,
    ) -> None:
        sensor.alarm_state = state
        sensor.alarm_level = level
        sensor.alarm_pending_since = None
        session.commit()
        self._create_alarm_event(session, sensor, measurement_id, state, level, message)

    def _create_alarm_event(
        self,
        session,
        sensor: Sensor,
        measurement_id: Optional[int],
        state: str,
        level: Optional[str],
        message: str,
    ) -> None:
        alarm = Alarm(
            device_id=sensor.device_id,
            sensor_id=sensor.id,
            measurement_id=measurement_id,
            level=level or "",
            state=state,
            message=message,
            active=state in (AlarmState.PENDING, AlarmState.ACTIVE, AlarmState.ACKNOWLEDGED),
        )
        session.add(alarm)
        session.commit()


alarm_service = AlarmService()
