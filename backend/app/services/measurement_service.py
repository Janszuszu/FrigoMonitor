from __future__ import annotations

import math
from datetime import datetime, UTC
from typing import Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import or_

from app.database import SessionLocal
from app.core.event_bus import EVENT_MEASUREMENT_UPDATE, EVENT_SENSOR_UPDATE, Event, event_bus
from app.logger import logger
from app.models.device import Device
from app.models.sensor import Sensor
from app.models.measurement import Measurement
from app.services.alarm_service import alarm_service
from app.config import settings


class MeasurementService:
    def __init__(self) -> None:
        self.min_value = settings.MEASUREMENT_MIN
        self.max_value = settings.MEASUREMENT_MAX

    def save_measurement(
        self,
        serial_number: str,
        sensor_name: str,
        value: float,
        timestamp: Optional[datetime] = None,
    ) -> bool:
        """Validate and save a measurement for a device's sensor.

        Returns True when stored, False when rejected.
        """
        # validate numeric
        try:
            if value is None or math.isnan(value) or not math.isfinite(value):
                logger.warning("Invalid measurement: NaN/Infinite")
                return False
        except Exception:
            logger.warning("Invalid measurement: could not validate numeric value")
            return False

        # validate range
        if not (self.min_value <= value <= self.max_value):
            logger.warning("Invalid measurement: out of range (%s not in %s..%s)", value, self.min_value, self.max_value)
            return False

        ts = timestamp or datetime.now(UTC)

        try:
            with SessionLocal() as session:
                # find device
                device = session.query(Device).filter(Device.serial_number == serial_number).one_or_none()
                if device is None:
                    logger.warning("Measurement received for unknown device %s", serial_number)
                    return False

                # find or create sensor
                sensor = (
                    session.query(Sensor)
                    .filter(Sensor.device_id == device.id)
                    .filter(
                        or_(
                            Sensor.name == sensor_name,
                            Sensor.sensor_id == sensor_name,
                            Sensor.rom == sensor_name,
                        )
                    )
                    .one_or_none()
                )
                if sensor is None:
                    sensor = Sensor(device_id=device.id, name=sensor_name, sensor_id=sensor_name)
                    session.add(sensor)
                    session.commit()
                    session.refresh(sensor)

                # create measurement
                m = Measurement(sensor_id=sensor.id, measured_at=ts, value=value)
                session.add(m)
                session.commit()
                measurement_id = m.id

                # update sensor/device fields
                sensor.last_value = value
                sensor.last_measurement = ts
                device.last_seen = ts

                session.commit()
                logger.info("Measurement stored: device=%s sensor=%s value=%s", serial_number, sensor_name, value)
                sensor_id = sensor.id
                stored = True
        except SQLAlchemyError:
            logger.exception("Database error while storing measurement")
            return False

        if stored:
            try:
                event_bus.publish(
                    Event(
                        event_type=EVENT_MEASUREMENT_UPDATE,
                        source="MeasurementService",
                        payload={
                            "measurement_id": measurement_id,
                            "sensor_id": sensor_id,
                            "serial_number": serial_number,
                            "sensor_name": sensor_name,
                            "value": value,
                            "timestamp": ts.isoformat(),
                        },
                    )
                )
                event_bus.publish(
                    Event(
                        event_type=EVENT_SENSOR_UPDATE,
                        source="MeasurementService",
                        payload={
                            "id": sensor_id,
                            "last_value": value,
                            "last_measurement": ts.isoformat(),
                        },
                    )
                )
                alarm_service.process_measurement(sensor_id, value, ts, measurement_id=measurement_id)
            except Exception:
                logger.exception("Error while processing alarm from measurement")
        return stored


# module-level default service
measurement_service = MeasurementService()
