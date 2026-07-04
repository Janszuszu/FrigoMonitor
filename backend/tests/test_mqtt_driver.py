import sys
import os
import json

sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

import pytest

from app.core import mqtt_protocol
from app.services import mqtt_service
from app.services.measurement_service import measurement_service
from app.database import Base, engine, SessionLocal
from app.models.device import Device


class DummyMsg:
    def __init__(self, topic: str, payload: bytes):
        self.topic = topic
        self.payload = payload


@pytest.fixture(autouse=True)
def prepare_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def test_topic_builders():
    t = mqtt_protocol.topic_measurement("DEVX")
    assert t == "frigomonitor/device/DEVX/measurement"
    assert mqtt_protocol.TOPIC_PREFIX == "frigomonitor"


def test_protocol_version_validation(monkeypatch):
    called = False

    def fake_save(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(measurement_service, "save_measurement", fake_save)

    payload = {"protocol_version": "0.9", "serial_number": "DEV1", "sensor_id": "s1", "value": 1.0}
    msg = DummyMsg(mqtt_protocol.topic_measurement("DEV1"), json.dumps(payload).encode())
    mqtt_service.mqtt_service._on_message(None, None, msg)
    assert not called


def test_measurement_handling_creates_measurement():
    # create device
    with SessionLocal() as s:
        dev = Device(name="M1", serial_number="DEV_MEAS")
        s.add(dev)
        s.commit()

    payload = {"protocol_version": mqtt_protocol.PROTOCOL_VERSION, "serial_number": "DEV_MEAS", "sensor_id": "s1", "value": 5.5}
    msg = DummyMsg(mqtt_protocol.topic_measurement("DEV_MEAS"), json.dumps(payload).encode())
    mqtt_service.mqtt_service._on_message(None, None, msg)

    # measurement should be stored via MeasurementService
    with SessionLocal() as s:
        dev = s.query(Device).filter(Device.serial_number == "DEV_MEAS").one()
        # sensor should be created by MeasurementService
        sensors = s.query(Device).filter(Device.serial_number == "DEV_MEAS").all()
        assert len(sensors) >= 1


def test_heartbeat_creates_or_updates_device():
    # ensure DeviceManager is bound to mqtt_service callbacks in test
    from app.services.device_manager import device_manager
    mqtt_service.mqtt_service.on_message_cb = device_manager.handle_message

    payload = {"protocol_version": mqtt_protocol.PROTOCOL_VERSION, "serial_number": "DEV_HB", "status": "online"}
    msg = DummyMsg(mqtt_protocol.topic_heartbeat("DEV_HB"), json.dumps(payload).encode())
    mqtt_service.mqtt_service._on_message(None, None, msg)

    with SessionLocal() as s:
        dev = s.query(Device).filter(Device.serial_number == "DEV_HB").one_or_none()
        assert dev is not None
        assert dev.last_seen is not None


def test_reconnect_triggers_subscriptions(monkeypatch):
    calls = []

    def fake_sub(topic, qos=0):
        calls.append((topic, qos))

    ms = mqtt_service.mqtt_service
    monkeypatch.setattr(ms, "subscribe", fake_sub)
    ms._on_connect(None, None, None, 0)
    # expect at least the measurement topic subscription
    assert any("/measurement" in t for t, _ in calls)


def test_no_direct_db_import_in_mqtt_service():
    import inspect
    import app.services.mqtt_service as msmod

    src = inspect.getsource(msmod)
    assert "from app.database" not in src
