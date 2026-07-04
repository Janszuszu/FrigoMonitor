import sys
import os
import json
import time

sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

import pytest

from app.database import Base, engine, SessionLocal
import app.models.measurement as _m  # ensure relationships are registered
from app.models.device import Device
from app.models.sensor import Sensor
from app.services import device_manager


class FakeMsg:
    def __init__(self, topic: str, payload: bytes):
        self.topic = topic
        self.payload = payload


@pytest.fixture(autouse=True)
def prepare_db():
    # create tables and ensure a clean state for tests
    Base.metadata.create_all(bind=engine)
    yield
    # cleanup rows used by tests
    with SessionLocal() as s:
        s.query(Sensor).filter(Sensor.name.in_(["ambient", "dup"])).delete(synchronize_session=False)
        s.query(Device).filter(Device.serial_number.in_(["SIM123", "DUP123"])).delete(synchronize_session=False)
        s.commit()


def test_device_and_sensor_registration_and_last_seen():
    # simulate incoming message
    payload = json.dumps({
        "serial_number": "SIM123",
        "device_name": "Sim Device",
        "sensor_name": "ambient",
        "sensor_type": "temperature",
    }).encode("utf-8")

    msg = FakeMsg("devices/SIM123/sensors/ambient", payload)

    # call handler twice to verify duplicate handling and last_seen update
    device_manager.device_manager.handle_message(None, None, msg)
    # record time after first registration
    time.sleep(0.01)
    with SessionLocal() as s:
        dev = s.query(Device).filter(Device.serial_number == "SIM123").one_or_none()
        assert dev is not None
        first_seen = dev.last_seen
        assert first_seen is not None

    # call again (duplicate) and ensure no duplicate entries
    device_manager.device_manager.handle_message(None, None, msg)

    with SessionLocal() as s:
        devices = s.query(Device).filter(Device.serial_number == "SIM123").all()
        assert len(devices) == 1
        sensors = s.query(Sensor).filter(Sensor.device_id == devices[0].id, Sensor.name == "ambient").all()
        assert len(sensors) == 1

        # last_seen should be updated (>= first value)
        dev = devices[0]
        assert dev.last_seen is not None
        assert dev.last_seen >= first_seen


def test_duplicate_message_does_not_create_duplicates():
    payload = json.dumps({
        "serial_number": "DUP123",
        "device_name": "Dup Device",
        "sensor_name": "dup",
        "sensor_type": "humidity",
    }).encode("utf-8")
    msg = FakeMsg("devices/DUP123/sensors/dup", payload)

    # call multiple times
    device_manager.device_manager.handle_message(None, None, msg)
    device_manager.device_manager.handle_message(None, None, msg)
    device_manager.device_manager.handle_message(None, None, msg)

    with SessionLocal() as s:
        devs = s.query(Device).filter(Device.serial_number == "DUP123").all()
        assert len(devs) == 1
        sens = s.query(Sensor).filter(Sensor.device_id == devs[0].id, Sensor.name == "dup").all()
        assert len(sens) == 1
