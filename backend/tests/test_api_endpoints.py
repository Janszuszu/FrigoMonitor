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
        # add measurements
        m1 = Measurement(sensor_id=sensor_id, measured_at=datetime.now(UTC), value=1.0)
        m2 = Measurement(sensor_id=sensor_id, measured_at=datetime.now(UTC) + timedelta(seconds=5), value=2.0)
        s.add_all([m1, m2])
        s.commit()
    
    # sensors list
    r = client.get("/api/v1/sensors")
    assert r.status_code == 200
    sensors = r.json()
    assert any(s["id"] == sensor_id for s in sensors)

    r = client.get(f"/api/v1/sensors/{sensor_id}")
    assert r.status_code == 200
    assert r.json()["id"] == sensor_id

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
