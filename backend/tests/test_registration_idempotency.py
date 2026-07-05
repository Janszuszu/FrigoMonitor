import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

from app.database import Base, SessionLocal, engine
from app.models.device import Device
from app.models.sensor import Sensor
from app.services import device_manager


class FakeMsg:
    def __init__(self, topic: str, payload: bytes):
        self.topic = topic
        self.payload = payload


@pytest.fixture(autouse=True)
def prepare_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def _send(topic: str, payload: dict) -> None:
    msg = FakeMsg(topic, json.dumps(payload).encode("utf-8"))
    device_manager.device_manager.handle_message(None, None, msg)


def test_register_same_device_twice_updates_metadata_without_duplicates():
    topic = "frigomonitor/device/ESP-001/register"
    payload = {
        "device_id": "ESP-001",
        "firmware": "1.0.0",
        "build": "2026-07-04",
        "board": "ESP32-C3",
        "chip_id": "ABC123",
        "mac": "AA:BB:CC:DD:EE:FF",
        "ip": "192.168.1.10",
    }

    _send(topic, payload)
    time.sleep(0.01)
    _send(topic, payload)

    with SessionLocal() as s:
        rows = s.query(Device).filter(Device.device_id == "ESP-001").all()
        assert len(rows) == 1
        assert rows[0].firmware == "1.0.0"
        assert rows[0].last_seen is not None


def test_register_same_sensor_twice_updates_metadata_without_duplicates():
    device_topic = "frigomonitor/device/ESP-002/register"
    sensor_topic = "frigomonitor/device/ESP-002/sensor/register"

    _send(device_topic, {"device_id": "ESP-002", "firmware": "1.0.0"})
    _send(
        sensor_topic,
        {
            "device_id": "ESP-002",
            "sensor_id": "ESP-002:28FFAA",
            "rom": "28FFAA",
            "type": "DS18B20",
            "unit": "C",
        },
    )
    _send(
        sensor_topic,
        {
            "device_id": "ESP-002",
            "sensor_id": "ESP-002:28FFAA",
            "rom": "28FFAA",
            "type": "DS18B20",
            "unit": "C",
        },
    )

    with SessionLocal() as s:
        device = s.query(Device).filter(Device.device_id == "ESP-002").one()
        sensors = s.query(Sensor).filter(Sensor.device_id == device.id, Sensor.rom == "28FFAA").all()
        assert len(sensors) == 1
        assert sensors[0].sensor_id == "ESP-002:28FFAA"
        assert sensors[0].last_seen is not None


def test_firmware_version_changes_updates_device():
    topic = "frigomonitor/device/ESP-003/register"

    _send(topic, {"device_id": "ESP-003", "firmware": "1.0.0"})
    _send(topic, {"device_id": "ESP-003", "firmware": "1.0.1"})

    with SessionLocal() as s:
        device = s.query(Device).filter(Device.device_id == "ESP-003").one()
        assert device.firmware == "1.0.1"


def test_ip_changes_updates_device():
    topic = "frigomonitor/device/ESP-004/register"

    _send(topic, {"device_id": "ESP-004", "ip": "192.168.1.20"})
    _send(topic, {"device_id": "ESP-004", "ip": "192.168.1.21"})

    with SessionLocal() as s:
        device = s.query(Device).filter(Device.device_id == "ESP-004").one()
        assert device.ip == "192.168.1.21"


def test_sensor_name_changes_updates_sensor():
    device_topic = "frigomonitor/device/ESP-005/register"
    sensor_topic = "frigomonitor/device/ESP-005/sensor/register"

    _send(device_topic, {"device_id": "ESP-005", "firmware": "1.0.0"})
    _send(
        sensor_topic,
        {
            "device_id": "ESP-005",
            "sensor_id": "ESP-005:28FFBB",
            "rom": "28FFBB",
            "name": "ambient",
            "type": "DS18B20",
            "unit": "C",
        },
    )
    _send(
        sensor_topic,
        {
            "device_id": "ESP-005",
            "sensor_id": "ESP-005:28FFBB",
            "rom": "28FFBB",
            "name": "ambient-new",
            "type": "DS18B20",
            "unit": "C",
        },
    )

    with SessionLocal() as s:
        device = s.query(Device).filter(Device.device_id == "ESP-005").one()
        sensor = s.query(Sensor).filter(Sensor.device_id == device.id, Sensor.rom == "28FFBB").one()
        assert sensor.name == "ambient-new"


def test_sensor_register_updates_existing_sensor_without_rom():
    device_topic = "frigomonitor/device/ESP-006/register"
    sensor_topic = "frigomonitor/device/ESP-006/sensor/register"

    _send(device_topic, {"device_id": "ESP-006", "firmware": "1.0.0"})

    # Simulate a pre-existing sensor row created by older flow without ROM.
    _send(
        "devices/ESP-006/sensors/ESP-006:28FFCC",
        {
            "serial_number": "ESP-006",
            "sensor_name": "ESP-006:28FFCC",
            "sensor_id": "ESP-006:28FFCC",
        },
    )

    # Proper sensor/register should update the same row instead of creating a duplicate.
    _send(
        sensor_topic,
        {
            "device_id": "ESP-006",
            "sensor_id": "ESP-006:28FFCC",
            "rom": "28FFCC",
            "type": "DS18B20",
            "unit": "C",
        },
    )

    with SessionLocal() as s:
        device = s.query(Device).filter(Device.device_id == "ESP-006").one()
        sensors = s.query(Sensor).filter(Sensor.device_id == device.id).all()
        assert len(sensors) == 1
        assert sensors[0].rom == "28FFCC"
        assert sensors[0].sensor_id == "ESP-006:28FFCC"
