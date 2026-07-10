import sys
import os
from datetime import datetime, timedelta, UTC

sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine, SessionLocal
from app.models.device import Device
from app.models.sensor import Sensor
from app.models.measurement import Measurement
from main import app


@pytest.fixture(autouse=True)
def prepare_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    with SessionLocal() as s:
        s.query(Measurement).delete()
        s.query(Sensor).delete()
        s.query(Device).delete()
        s.commit()


client = TestClient(app)


def test_system_health():
    r = client.get("/api/v1/system/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"


def test_devices_endpoints():
    # empty list
    r = client.get("/api/v1/devices")
    assert r.status_code == 200
    assert r.json() == []

    # create device
    with SessionLocal() as s:
        dev = Device(name="API-D1", serial_number="A1")
        s.add(dev)
        s.commit()
        s.refresh(dev)
        dev_id = dev.id

    r = client.get("/api/v1/devices")
    assert r.status_code == 200
    arr = r.json()
    assert any(d["id"] == dev_id for d in arr)

    r = client.get(f"/api/v1/devices/{dev_id}")
    assert r.status_code == 200
    assert r.json()["id"] == dev_id


def test_create_device_and_sensor_from_api():
    r = client.post(
        "/api/v1/devices",
        json={"name": "Manual fridge", "serial_number": "MANUAL-1", "location": "Cold room"},
    )
    assert r.status_code == 201
    device = r.json()
    assert device["name"] == "Manual fridge"
    assert device["serial_number"] == "MANUAL-1"

    r = client.post(
        f"/api/v1/devices/{device['id']}/sensors",
        json={"name": "probe_1", "sensor_type": "temperature", "address": "GPIO4", "correction": 0.2},
    )
    assert r.status_code == 201
    sensor = r.json()
    assert sensor["device_id"] == device["id"]
    assert sensor["name"] == "probe_1"
    assert sensor["address"] == "GPIO4"

    duplicate = client.post(
        "/api/v1/devices",
        json={"name": "Duplicate", "serial_number": "MANUAL-1"},
    )
    assert duplicate.status_code == 409


def test_sensors_endpoints_and_measurements():
    with SessionLocal() as s:
        dev = Device(name="API-D2", serial_number="A2")
        s.add(dev)
        s.commit()
        s.refresh(dev)
        sensor = Sensor(device_id=dev.id, name="sapi")
        s.add(sensor)
        s.commit()
        s.refresh(sensor)
        sensor_id = sensor.id
        # add measurements across multiple timestamps
        base = datetime.now(UTC)
        measurements = [
            Measurement(sensor_id=sensor_id, measured_at=base + timedelta(minutes=i), value=float(i % 7) + 0.5)
            for i in range(20)
        ]
        s.add_all(measurements)
        s.commit()
    
    # sensors list
    r = client.get("/api/v1/sensors")
    assert r.status_code == 200
    sensors = r.json()
    assert any(s["id"] == sensor_id for s in sensors)

    r = client.get(f"/api/v1/sensors/{sensor_id}")
    assert r.status_code == 200
    assert r.json()["id"] == sensor_id

    r = client.put(
        f"/api/v1/sensors/{sensor_id}/alarm",
        json={
            "alarm_enabled": True,
            "alarm_low": -2.0,
            "alarm_high": 8.0,
            "alarm_hysteresis": 0.5,
            "alarm_activation_delay": 30,
        },
    )
    assert r.status_code == 200
    alarm_data = r.json()
    assert alarm_data["alarm_low"] == -2.0
    assert alarm_data["alarm_high"] == 8.0
    assert alarm_data["alarm_hysteresis"] == 0.5
    assert alarm_data["alarm_activation_delay"] == 30

    # measurements latest
    r = client.get("/api/v1/measurements/latest?limit=10")
    assert r.status_code == 200
    latest = r.json()
    assert len(latest) >= 2

    # history filtered by sensor
    r = client.get(f"/api/v1/measurements/history?sensor_id={sensor_id}&limit=10")
    assert r.status_code == 200
    hist = r.json()
    assert all(m["sensor_id"] == sensor_id for m in hist)

    dt_from = (base + timedelta(minutes=5)).isoformat()
    dt_to = (base + timedelta(minutes=12)).isoformat()
    r = client.get(
        "/api/v1/measurements/history",
        params={
            "sensor_id": sensor_id,
            "from": dt_from,
            "to": dt_to,
            "limit": 100,
        },
    )
    assert r.status_code == 200
    ranged = r.json()
    assert len(ranged) > 0
    dt_from_obj = datetime.fromisoformat(dt_from.replace("Z", "+00:00"))
    dt_to_obj = datetime.fromisoformat(dt_to.replace("Z", "+00:00"))

    if dt_from_obj.tzinfo is None:
        dt_from_obj = dt_from_obj.replace(tzinfo=UTC)
    if dt_to_obj.tzinfo is None:
        dt_to_obj = dt_to_obj.replace(tzinfo=UTC)

    def _as_utc(value: str) -> datetime:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)

    assert all(
        dt_from_obj <= _as_utc(item["measured_at"]) <= dt_to_obj
        for item in ranged
    )

    r = client.get(
        "/api/v1/measurements/history",
        params={
            "sensor_id": sensor_id,
            "from": base.isoformat(),
            "to": (base + timedelta(minutes=19)).isoformat(),
            "limit": 100,
            "target_points": 6,
        },
    )
    assert r.status_code == 422

    r = client.get(
        "/api/v1/measurements/history",
        params={
            "sensor_id": sensor_id,
            "from": base.isoformat(),
            "to": (base + timedelta(minutes=19)).isoformat(),
            "limit": 100,
            "target_points": 100,
        },
    )
    assert r.status_code == 200
    downsampled = r.json()
    assert len(downsampled) <= 100


def test_network_settings_endpoints():
    r = client.get("/api/v1/system/network")
    assert r.status_code == 200
    assert "mqtt_host" in r.json()

    r = client.put(
        "/api/v1/system/network",
        json={
            "mqtt_host": "broker.local",
            "mqtt_port": 1884,
            "mqtt_user": "frigo",
            "mqtt_password": "secret",
            "frontend_origins": ["http://localhost:5173"],
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["mqtt_host"] == "broker.local"
    assert data["mqtt_port"] == 1884
    assert data["mqtt_user"] == "frigo"
    assert data["mqtt_password_configured"] is True
