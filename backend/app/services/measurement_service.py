from __future__ import annotations

import math
from datetime import datetime, UTC
from typing import Optional

from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.logger import logger
from app.models.device import Device
from app.models.sensor import Sensor
from app.models.measurement import Measurement
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
                    .filter(Sensor.name == sensor_name)
                    .one_or_none()
                )
                if sensor is None:
                    sensor = Sensor(device_id=device.id, name=sensor_name)
                    session.add(sensor)
                    session.commit()
                    session.refresh(sensor)

                # create measurement
                m = Measurement(sensor_id=sensor.id, measured_at=ts, value=value)
                session.add(m)

                # update sensor/device fields
                sensor.last_value = value
                sensor.last_measurement = ts
                device.last_seen = ts

                session.commit()
                logger.info("Measurement stored: device=%s sensor=%s value=%s", serial_number, sensor_name, value)
                return True
        except SQLAlchemyError:
            logger.exception("Database error while storing measurement")
            return False


# module-level default service
measurement_service = MeasurementService()
