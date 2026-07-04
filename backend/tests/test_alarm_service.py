import sys
import os
from datetime import datetime, timedelta, UTC

sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

import pytest

from app.database import Base, engine, SessionLocal
from app.models.device import Device
from app.models.sensor import Sensor
from app.models.alarm import Alarm
from app.services.measurement_service import measurement_service
from app.services.alarm_service import alarm_service, AlarmState


@pytest.fixture(autouse=True)
def prepare_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def create_device_sensor(sensor_kwargs=None):
    sensor_kwargs = sensor_kwargs or {}
    with SessionLocal() as s:
        dev = Device(name="AlarmDev", serial_number="DEV0")
        s.add(dev)
        s.commit()
        s.refresh(dev)
        sensor = Sensor(device_id=dev.id, name="sensor1", **sensor_kwargs)
        s.add(sensor)
        s.commit()
        s.refresh(sensor)
        return dev, sensor


def test_high_alarm_activation():
    _, sensor = create_device_sensor({"alarm_high": 10.0, "alarm_low": None})
    measurement_service.save_measurement("DEV0", "sensor1", 12.0, timestamp=datetime.now(UTC))

    with SessionLocal() as s:
        sensor_db = s.get(Sensor, sensor.id)
        assert sensor_db.alarm_state == AlarmState.ACTIVE
        alarm = s.query(Alarm).filter(Alarm.sensor_id == sensor.id).order_by(Alarm.id.desc()).first()
        assert alarm is not None
        assert alarm.state == AlarmState.ACTIVE
        assert alarm.level == "HIGH"


def test_low_alarm_activation():
    _, sensor = create_device_sensor({"alarm_high": None, "alarm_low": 5.0})
    measurement_service.save_measurement("DEV0", "sensor1", 3.0, timestamp=datetime.now(UTC))

    with SessionLocal() as s:
        sensor_db = s.get(Sensor, sensor.id)
        assert sensor_db.alarm_state == AlarmState.ACTIVE
        alarm = s.query(Alarm).filter(Alarm.sensor_id == sensor.id).order_by(Alarm.id.desc()).first()
        assert alarm.state == AlarmState.ACTIVE
        assert alarm.level == "LOW"


def test_hysteresis_prevents_clear_until_threshold():
    _, sensor = create_device_sensor({"alarm_high": 10.0, "alarm_hysteresis": 2.0})
    now = datetime.now(UTC)
    measurement_service.save_measurement("DEV0", "sensor1", 12.0, timestamp=now)
    measurement_service.save_measurement("DEV0", "sensor1", 9.5, timestamp=now + timedelta(seconds=10))

    with SessionLocal() as s:
        sensor_db = s.get(Sensor, sensor.id)
        assert sensor_db.alarm_state == AlarmState.ACTIVE

    measurement_service.save_measurement("DEV0", "sensor1", 8.0, timestamp=now + timedelta(seconds=20))
    with SessionLocal() as s:
        sensor_db = s.get(Sensor, sensor.id)
        assert sensor_db.alarm_state == AlarmState.CLEARED


def test_activation_delay_enforces_pending():
    _, sensor = create_device_sensor({"alarm_high": 10.0, "alarm_activation_delay": 5})
    now = datetime.now(UTC)
    measurement_service.save_measurement("DEV0", "sensor1", 12.0, timestamp=now)

    with SessionLocal() as s:
        sensor_db = s.get(Sensor, sensor.id)
        assert sensor_db.alarm_state == AlarmState.PENDING

    measurement_service.save_measurement("DEV0", "sensor1", 12.0, timestamp=now + timedelta(seconds=6))
    with SessionLocal() as s:
        sensor_db = s.get(Sensor, sensor.id)
        assert sensor_db.alarm_state == AlarmState.ACTIVE


def test_acknowledge_moves_active_to_acknowledged():
    _, sensor = create_device_sensor({"alarm_high": 10.0})
    measurement_service.save_measurement("DEV0", "sensor1", 12.0, timestamp=datetime.now(UTC))
    alarm_service.acknowledge(sensor.id)

    with SessionLocal() as s:
        sensor_db = s.get(Sensor, sensor.id)
        assert sensor_db.alarm_state == AlarmState.ACKNOWLEDGED


def test_clear_resets_state():
    _, sensor = create_device_sensor({"alarm_high": 10.0})
    measurement_service.save_measurement("DEV0", "sensor1", 12.0, timestamp=datetime.now(UTC))
    alarm_service.clear(sensor.id)

    with SessionLocal() as s:
        sensor_db = s.get(Sensor, sensor.id)
        assert sensor_db.alarm_state == AlarmState.CLEARED


def test_disabled_rule_ignores_alarm():
    _, sensor = create_device_sensor({"alarm_high": 10.0, "alarm_enabled": False})
    measurement_service.save_measurement("DEV0", "sensor1", 12.0, timestamp=datetime.now(UTC))

    with SessionLocal() as s:
        sensor_db = s.get(Sensor, sensor.id)
        assert sensor_db.alarm_state in (AlarmState.CLEARED, AlarmState.NORMAL)
