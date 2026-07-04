import sys
import os
from datetime import datetime, timedelta, UTC

sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

import pytest

from app.database import Base, engine, SessionLocal
from app.models.device import Device
from app.models.sensor import Sensor
from app.services.measurement_service import measurement_service


@pytest.fixture(autouse=True)
def prepare_db():
    # recreate schema to ensure models' columns are applied
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    # cleanup
    with SessionLocal() as s:
        s.query(Sensor).delete()
        s.query(Device).delete()
        s.commit()


def test_measurement_inserted_and_last_values():
    with SessionLocal() as s:
        dev = Device(name="T1", serial_number="DEV1")
        s.add(dev)
        s.commit()
        s.refresh(dev)

    now = datetime.now(UTC)
    ok = measurement_service.save_measurement("DEV1", "s1", 12.5, timestamp=now)
    assert ok

    with SessionLocal() as s:
        dev = s.query(Device).filter(Device.serial_number == "DEV1").one()
        sensors = s.query(Sensor).filter(Sensor.device_id == dev.id, Sensor.name == "s1").all()
        assert len(sensors) == 1
        sensor = sensors[0]
        assert sensor.last_value == 12.5
        assert sensor.last_measurement is not None


def test_duplicate_sensor_not_created_and_last_measurement_updated():
    with SessionLocal() as s:
        dev = Device(name="T2", serial_number="DEV2")
        s.add(dev)
        s.commit()
        s.refresh(dev)

    t1 = datetime.now(UTC)
    assert measurement_service.save_measurement("DEV2", "sdup", 1.1, timestamp=t1)
    t2 = t1 + timedelta(seconds=10)
    assert measurement_service.save_measurement("DEV2", "sdup", 2.2, timestamp=t2)

    with SessionLocal() as s:
        dev = s.query(Device).filter(Device.serial_number == "DEV2").one()
        sensors = s.query(Sensor).filter(Sensor.device_id == dev.id, Sensor.name == "sdup").all()
        assert len(sensors) == 1
        sensor = sensors[0]
        assert sensor.last_value == 2.2
        # DB may return naive datetimes for SQLite; make timezone-aware for comparison
        lm = sensor.last_measurement
        if lm is not None and lm.tzinfo is None:
            lm = lm.replace(tzinfo=UTC)
        assert lm >= t2


def test_invalid_values_rejected():
    with SessionLocal() as s:
        dev = Device(name="T3", serial_number="DEV3")
        s.add(dev)
        s.commit()

    assert not measurement_service.save_measurement("DEV3", "s1", float("nan"))
    assert not measurement_service.save_measurement("DEV3", "s1", float("inf"))
    # out of default range (-100..100)
    assert not measurement_service.save_measurement("DEV3", "s1", 1000.0)


def test_multiple_sensors_on_one_device():
    with SessionLocal() as s:
        dev = Device(name="T4", serial_number="DEV4")
        s.add(dev)
        s.commit()

    assert measurement_service.save_measurement("DEV4", "a", 10.0)
    assert measurement_service.save_measurement("DEV4", "b", 20.0)

    with SessionLocal() as s:
        dev = s.query(Device).filter(Device.serial_number == "DEV4").one()
        sensors = s.query(Sensor).filter(Sensor.device_id == dev.id).all()
        names = sorted([x.name for x in sensors])
        assert names == ["a", "b"]
