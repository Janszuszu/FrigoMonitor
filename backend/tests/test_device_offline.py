"""Regression tests for DEVICE_OFFLINE alarm feature.

Tests cover:
1. Device remains online before timeout.
2. Device becomes offline after configured timeout.
3. Exactly one DEVICE_OFFLINE alarm is created per incident.
4. DEVICE_OFFLINE uses sensor_id = NULL.
5. DEVICE_OFFLINE contains correct device identity.
6. Active alarms API returns DEVICE_OFFLINE with sensor_id = NULL.
7. Existing sensor alarms still appear in active alarms API.
8. Telegram notification is emitted when enabled.
9. Telegram notification is not emitted when disabled.
10. Repeated monitor cycles do not create duplicate alarms.
11. Device reconnect clears active DEVICE_OFFLINE.
12. Cleared alarm remains in history if supported.
13. Last Seen timestamp is serialized unambiguously as UTC.
14. Frontend does not filter DEVICE_OFFLINE because sensor_id is null.
15. WebSocket alarm payload can represent DEVICE_OFFLINE.
"""

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
from app.models.alarm_event import AlarmEvent
from app.models.device_offline_settings import DeviceOfflineSettings
from app.services.device_offline_monitor import DeviceOfflineMonitor
from app.core.event_bus import EventBus, EVENT_ALARM_ACTIVE, EVENT_ALARM_UPDATE
from main import app


@pytest.fixture(autouse=True)
def prepare_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    with SessionLocal() as s:
        s.query(AlarmEvent).delete()
        s.query(Measurement).delete()
        s.query(Sensor).delete()
        s.query(Device).delete()
        s.query(DeviceOfflineSettings).delete()
        s.commit()


client = TestClient(app)


def _create_device(db_session, name="test-device", serial="SN-001", last_seen_minutes_ago=None):
    """Helper to create a device with optional last_seen in the past."""
    device = Device(name=name, serial_number=serial)
    if last_seen_minutes_ago is not None:
        device.last_seen = datetime.now(UTC) - timedelta(minutes=last_seen_minutes_ago)
    else:
        device.last_seen = datetime.now(UTC)
    device.online = True
    db_session.add(device)
    db_session.commit()
    db_session.refresh(device)
    return device


def _create_sensor(db_session, device_id, name="probe_1"):
    """Helper to create a sensor for a device."""
    sensor = Sensor(device_id=device_id, name=name)
    db_session.add(sensor)
    db_session.commit()
    db_session.refresh(sensor)
    return sensor


def _create_device_offline_settings(db_session, enabled=True, timeout_minutes=5, severity="CRITICAL", notifications_enabled=True):
    """Helper to create device offline settings."""
    settings = DeviceOfflineSettings(
        enabled=enabled,
        offline_timeout_minutes=timeout_minutes,
        severity=severity,
        notifications_enabled=notifications_enabled,
    )
    db_session.add(settings)
    db_session.commit()
    return settings


# ============================================================
# Test 1: Device remains online before timeout
# ============================================================
def test_device_remains_online_before_timeout():
    """Device with recent last_seen should remain online."""
    with SessionLocal() as s:
        device = _create_device(s, last_seen_minutes_ago=1)
        _create_device_offline_settings(s, timeout_minutes=5)
        dev_id = device.id

    bus = EventBus()
    monitor = DeviceOfflineMonitor(check_interval_seconds=1, startup_grace_seconds=0, bus=bus)
    import asyncio
    asyncio.run(monitor._check_devices())

    with SessionLocal() as s:
        device = s.query(Device).filter(Device.id == dev_id).first()
        assert device.online is True, "Device should remain online before timeout"
        alarm = s.query(AlarmEvent).filter(
            AlarmEvent.device_id == dev_id,
            AlarmEvent.alarm_type == "DEVICE_OFFLINE",
        ).first()
        assert alarm is None, "No DEVICE_OFFLINE alarm should exist before timeout"


# ============================================================
# Test 2: Device becomes offline after configured timeout
# ============================================================
def test_device_becomes_offline_after_timeout():
    """Device with old last_seen should become offline."""
    with SessionLocal() as s:
        device = _create_device(s, last_seen_minutes_ago=10)
        _create_device_offline_settings(s, timeout_minutes=5)
        dev_id = device.id

    bus = EventBus()
    monitor = DeviceOfflineMonitor(check_interval_seconds=1, startup_grace_seconds=0, bus=bus)
    import asyncio
    asyncio.run(monitor._check_devices())

    with SessionLocal() as s:
        device = s.query(Device).filter(Device.id == dev_id).first()
        assert device.online is False, "Device should be offline after timeout"
        alarm = s.query(AlarmEvent).filter(
            AlarmEvent.device_id == dev_id,
            AlarmEvent.alarm_type == "DEVICE_OFFLINE",
        ).first()
        assert alarm is not None, "DEVICE_OFFLINE alarm should exist"
        assert alarm.state == "ACTIVE", "Alarm should be ACTIVE"


# ============================================================
# Test 3: Exactly one DEVICE_OFFLINE alarm per incident
# ============================================================
def test_exactly_one_alarm_per_incident():
    """Only one DEVICE_OFFLINE alarm should be created per offline incident."""
    with SessionLocal() as s:
        device = _create_device(s, last_seen_minutes_ago=10)
        _create_device_offline_settings(s, timeout_minutes=5)
        dev_id = device.id

    bus = EventBus()
    monitor = DeviceOfflineMonitor(check_interval_seconds=1, startup_grace_seconds=0, bus=bus)
    import asyncio

    # Run multiple cycles
    for _ in range(3):
        asyncio.run(monitor._check_devices())

    with SessionLocal() as s:
        alarms = s.query(AlarmEvent).filter(
            AlarmEvent.device_id == dev_id,
            AlarmEvent.alarm_type == "DEVICE_OFFLINE",
        ).all()
        assert len(alarms) == 1, f"Expected 1 alarm, got {len(alarms)}"
        assert alarms[0].state == "ACTIVE"


# ============================================================
# Test 4: DEVICE_OFFLINE uses sensor_id = NULL
# ============================================================
def test_device_offline_sensor_id_is_null():
    """DEVICE_OFFLINE alarm must have sensor_id = NULL."""
    with SessionLocal() as s:
        device = _create_device(s, last_seen_minutes_ago=10)
        _create_device_offline_settings(s, timeout_minutes=5)
        dev_id = device.id

    bus = EventBus()
    monitor = DeviceOfflineMonitor(check_interval_seconds=1, startup_grace_seconds=0, bus=bus)
    import asyncio
    asyncio.run(monitor._check_devices())

    with SessionLocal() as s:
        alarm = s.query(AlarmEvent).filter(
            AlarmEvent.device_id == dev_id,
            AlarmEvent.alarm_type == "DEVICE_OFFLINE",
        ).first()
        assert alarm is not None
        assert alarm.sensor_id is None, "sensor_id must be NULL for DEVICE_OFFLINE"


# ============================================================
# Test 5: DEVICE_OFFLINE contains correct device identity
# ============================================================
def test_device_offline_identity():
    """DEVICE_OFFLINE alarm must reference the correct device."""
    with SessionLocal() as s:
        device = _create_device(s, name="esp32", serial="SN-ESP32", last_seen_minutes_ago=10)
        _create_device_offline_settings(s, timeout_minutes=5)
        dev_id = device.id

    bus = EventBus()
    monitor = DeviceOfflineMonitor(check_interval_seconds=1, startup_grace_seconds=0, bus=bus)
    import asyncio
    asyncio.run(monitor._check_devices())

    with SessionLocal() as s:
        alarm = s.query(AlarmEvent).filter(
            AlarmEvent.device_id == dev_id,
            AlarmEvent.alarm_type == "DEVICE_OFFLINE",
        ).first()
        assert alarm is not None
        assert alarm.device_id == dev_id, f"Expected device_id={dev_id}, got {alarm.device_id}"
        device = s.query(Device).filter(Device.id == dev_id).first()
        assert device is not None
        assert device.name == "esp32"


# ============================================================
# Test 6: Active alarms API returns DEVICE_OFFLINE with sensor_id = NULL
# ============================================================
def test_active_alarms_api_returns_device_offline():
    """GET /api/v1/alarms/active must return DEVICE_OFFLINE with sensor_id = NULL."""
    with SessionLocal() as s:
        _create_device(s, last_seen_minutes_ago=10)
        _create_device_offline_settings(s, timeout_minutes=5)

    bus = EventBus()
    monitor = DeviceOfflineMonitor(check_interval_seconds=1, startup_grace_seconds=0, bus=bus)
    import asyncio
    asyncio.run(monitor._check_devices())

    r = client.get("/api/v1/alarms/active")
    assert r.status_code == 200
    alarms = r.json()
    device_offline_alarms = [a for a in alarms if a["alarm_type"] == "DEVICE_OFFLINE"]
    assert len(device_offline_alarms) >= 1, "DEVICE_OFFLINE should appear in active alarms API"
    for alarm in device_offline_alarms:
        assert alarm["sensor_id"] is None, "sensor_id must be null in API response"
        assert alarm["device_id"] is not None, "device_id must not be null"
        assert alarm["device_name"] is not None, "device_name must be present"


# ============================================================
# Test 7: Existing sensor alarms still appear in active alarms API
# ============================================================
def test_sensor_alarms_still_appear():
    """Sensor alarms must still appear alongside DEVICE_OFFLINE in active alarms API."""
    with SessionLocal() as s:
        device = _create_device(s, last_seen_minutes_ago=10)
        _create_device_offline_settings(s, timeout_minutes=5)
        sensor = _create_sensor(s, device.id)
        # Create a sensor alarm event
        sensor_alarm = AlarmEvent(
            sensor_id=sensor.id,
            device_id=device.id,
            alarm_type="ALARM_HIGH",
            state="ACTIVE",
            activated_at=datetime.now(UTC),
        )
        s.add(sensor_alarm)
        s.commit()

    bus = EventBus()
    monitor = DeviceOfflineMonitor(check_interval_seconds=1, startup_grace_seconds=0, bus=bus)
    import asyncio
    asyncio.run(monitor._check_devices())

    r = client.get("/api/v1/alarms/active")
    assert r.status_code == 200
    alarms = r.json()
    types = {a["alarm_type"] for a in alarms}
    assert "DEVICE_OFFLINE" in types, "DEVICE_OFFLINE must appear"
    assert "ALARM_HIGH" in types, "Sensor alarms must still appear"
    # Verify sensor alarm has sensor_id
    sensor_alarms = [a for a in alarms if a["alarm_type"] == "ALARM_HIGH"]
    for a in sensor_alarms:
        assert a["sensor_id"] is not None, "Sensor alarm must have sensor_id"


# ============================================================
# Test 8: Telegram notification is emitted when enabled
# ============================================================
def test_telegram_notification_emitted_when_enabled():
    """EVENT_ALARM_ACTIVE must be published when notifications are enabled."""
    received_events = []

    def collector(event):
        received_events.append(event)

    bus = EventBus()
    bus.subscribe(EVENT_ALARM_ACTIVE, collector)

    with SessionLocal() as s:
        _create_device(s, last_seen_minutes_ago=10)
        _create_device_offline_settings(s, timeout_minutes=5, notifications_enabled=True)

    monitor = DeviceOfflineMonitor(check_interval_seconds=1, startup_grace_seconds=0, bus=bus)
    import asyncio
    asyncio.run(monitor._check_devices())

    # Check that EVENT_ALARM_ACTIVE was published
    alarm_active_events = [e for e in received_events if e.event_type == EVENT_ALARM_ACTIVE]
    assert len(alarm_active_events) >= 1, "EVENT_ALARM_ACTIVE should be published"
    payload = alarm_active_events[0].payload
    assert payload.get("telegram_enabled") is True, "telegram_enabled should be True"


# ============================================================
# Test 9: Telegram notification is not emitted when disabled
# ============================================================
def test_telegram_notification_not_emitted_when_disabled():
    """EVENT_ALARM_ACTIVE must have telegram_enabled=False when disabled."""
    received_events = []

    def collector(event):
        received_events.append(event)

    bus = EventBus()
    bus.subscribe(EVENT_ALARM_ACTIVE, collector)

    with SessionLocal() as s:
        _create_device(s, last_seen_minutes_ago=10)
        _create_device_offline_settings(s, timeout_minutes=5, notifications_enabled=False)

    monitor = DeviceOfflineMonitor(check_interval_seconds=1, startup_grace_seconds=0, bus=bus)
    import asyncio
    asyncio.run(monitor._check_devices())

    alarm_active_events = [e for e in received_events if e.event_type == EVENT_ALARM_ACTIVE]
    assert len(alarm_active_events) >= 1, "EVENT_ALARM_ACTIVE should be published"
    payload = alarm_active_events[0].payload
    assert payload.get("telegram_enabled") is False, "telegram_enabled should be False"


# ============================================================
# Test 10: Repeated monitor cycles do not create duplicate alarms
# ============================================================
def test_no_duplicate_alarms_on_repeated_cycles():
    """Multiple monitor cycles must not create duplicate DEVICE_OFFLINE alarms."""
    with SessionLocal() as s:
        device = _create_device(s, last_seen_minutes_ago=10)
        _create_device_offline_settings(s, timeout_minutes=5)
        dev_id = device.id

    bus = EventBus()
    monitor = DeviceOfflineMonitor(check_interval_seconds=1, startup_grace_seconds=0, bus=bus)
    import asyncio

    # Run 5 cycles
    for _ in range(5):
        asyncio.run(monitor._check_devices())

    with SessionLocal() as s:
        alarms = s.query(AlarmEvent).filter(
            AlarmEvent.device_id == dev_id,
            AlarmEvent.alarm_type == "DEVICE_OFFLINE",
        ).all()
        assert len(alarms) == 1, f"Expected 1 alarm, got {len(alarms)}"


# ============================================================
# Test 11: Device reconnect clears active DEVICE_OFFLINE
# ============================================================
def test_reconnect_clears_alarm():
    """When device communicates again, DEVICE_OFFLINE alarm must be cleared."""
    with SessionLocal() as s:
        device = _create_device(s, last_seen_minutes_ago=10)
        _create_device_offline_settings(s, timeout_minutes=5)
        dev_id = device.id

    bus = EventBus()
    monitor = DeviceOfflineMonitor(check_interval_seconds=1, startup_grace_seconds=0, bus=bus)
    import asyncio

    # First cycle: device goes offline
    asyncio.run(monitor._check_devices())

    with SessionLocal() as s:
        alarm = s.query(AlarmEvent).filter(
            AlarmEvent.device_id == dev_id,
            AlarmEvent.alarm_type == "DEVICE_OFFLINE",
        ).first()
        assert alarm is not None
        assert alarm.state == "ACTIVE"

    # Simulate device reconnecting by updating last_seen
    with SessionLocal() as s:
        device = s.query(Device).filter(Device.id == dev_id).first()
        device.last_seen = datetime.now(UTC)
        s.commit()

    # Second cycle: device is back online
    asyncio.run(monitor._check_devices())

    with SessionLocal() as s:
        alarm = s.query(AlarmEvent).filter(
            AlarmEvent.device_id == dev_id,
            AlarmEvent.alarm_type == "DEVICE_OFFLINE",
        ).first()
        assert alarm is not None
        assert alarm.state == "CLEARED", f"Expected CLEARED, got {alarm.state}"
        assert alarm.cleared_at is not None, "cleared_at should be set"
        device = s.query(Device).filter(Device.id == dev_id).first()
        assert device.online is True, "Device should be online after reconnect"


# ============================================================
# Test 12: Cleared alarm remains in history
# ============================================================
def test_cleared_alarm_in_history():
    """Cleared DEVICE_OFFLINE alarm must remain in history API."""
    with SessionLocal() as s:
        device = _create_device(s, last_seen_minutes_ago=10)
        _create_device_offline_settings(s, timeout_minutes=5)
        dev_id = device.id

    bus = EventBus()
    monitor = DeviceOfflineMonitor(check_interval_seconds=1, startup_grace_seconds=0, bus=bus)
    import asyncio

    # Create alarm
    asyncio.run(monitor._check_devices())

    # Reconnect
    with SessionLocal() as s:
        device = s.query(Device).filter(Device.id == dev_id).first()
        device.last_seen = datetime.now(UTC)
        s.commit()

    asyncio.run(monitor._check_devices())

    # Check history API
    r = client.get("/api/v1/alarms/history?limit=100")
    assert r.status_code == 200
    history = r.json()
    device_offline_history = [h for h in history if h["alarm_type"] == "DEVICE_OFFLINE"]
    assert len(device_offline_history) >= 1, "DEVICE_OFFLINE should appear in history"
    assert device_offline_history[0]["state"] == "CLEARED"


# ============================================================
# Test 13: Last Seen timestamp serialized as UTC
# ============================================================
def test_last_seen_serialized_as_utc():
    """Device last_seen must be serialized with Z or +00:00 in API response."""
    with SessionLocal() as s:
        device = _create_device(s, last_seen_minutes_ago=1)
        dev_id = device.id

    r = client.get(f"/api/v1/devices/{dev_id}")
    assert r.status_code == 200
    data = r.json()
    last_seen = data.get("last_seen")
    assert last_seen is not None, "last_seen should not be None"
    # Must end with Z or contain +00:00
    assert last_seen.endswith("Z") or "+00:00" in last_seen, \
        f"last_seen must be UTC, got: {last_seen}"


# ============================================================
# Test 14: Frontend does not filter DEVICE_OFFLINE because sensor_id is null
# ============================================================
def test_frontend_can_handle_null_sensor_id():
    """ActiveAlarm type must support sensor_id = None (TypeScript interface check)."""
    # This test verifies the API returns sensor_id = null for DEVICE_OFFLINE
    with SessionLocal() as s:
        _create_device(s, last_seen_minutes_ago=10)
        _create_device_offline_settings(s, timeout_minutes=5)

    bus = EventBus()
    monitor = DeviceOfflineMonitor(check_interval_seconds=1, startup_grace_seconds=0, bus=bus)
    import asyncio
    asyncio.run(monitor._check_devices())

    r = client.get("/api/v1/alarms/active")
    assert r.status_code == 200
    alarms = r.json()
    for alarm in alarms:
        # The frontend ActiveAlarm type has sensor_id: number | null
        # This verifies the API can return null
        if alarm["alarm_type"] == "DEVICE_OFFLINE":
            assert alarm["sensor_id"] is None, "sensor_id must be null"
            # Frontend can safely access these fields
            assert "device_id" in alarm
            assert "device_name" in alarm
            assert "device_display_name" in alarm


# ============================================================
# Test 15: WebSocket alarm payload can represent DEVICE_OFFLINE
# ============================================================
def test_websocket_payload_represents_device_offline():
    """WebSocket EVENT_ALARM_UPDATE payload must represent DEVICE_OFFLINE correctly."""
    received_events = []

    def collector(event):
        received_events.append(event)

    bus = EventBus()
    bus.subscribe(EVENT_ALARM_UPDATE, collector)

    with SessionLocal() as s:
        _create_device(s, name="esp32", serial="SN-ESP32", last_seen_minutes_ago=10)
        _create_device_offline_settings(s, timeout_minutes=5)

    monitor = DeviceOfflineMonitor(check_interval_seconds=1, startup_grace_seconds=0, bus=bus)
    import asyncio
    asyncio.run(monitor._check_devices())

    alarm_update_events = [e for e in received_events if e.event_type == EVENT_ALARM_UPDATE]
    assert len(alarm_update_events) >= 1, "EVENT_ALARM_UPDATE should be published"
    payload = alarm_update_events[0].payload
    assert payload.get("type") == "DEVICE_OFFLINE"
    assert payload.get("state") == "ACTIVE"
    assert payload.get("sensor_id") is None, "sensor_id must be None in WebSocket payload"
    assert payload.get("device_id") is not None
    assert payload.get("device_name") is not None
    assert payload.get("message") is not None


# ============================================================
# Test: Device offline settings API
# ============================================================
def test_device_offline_settings_api():
    """GET and PUT /api/v1/device-offline/settings must work."""
    # GET should return default settings
    r = client.get("/api/v1/device-offline/settings")
    assert r.status_code == 200
    data = r.json()
    assert "enabled" in data
    assert "offline_timeout_minutes" in data
    assert "severity" in data
    assert "notifications_enabled" in data

    # PUT should update settings
    r = client.put("/api/v1/device-offline/settings", json={
        "enabled": False,
        "offline_timeout_minutes": 10,
        "severity": "WARNING",
        "notifications_enabled": False,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["enabled"] is False
    assert data["offline_timeout_minutes"] == 10
    assert data["severity"] == "WARNING"
    assert data["notifications_enabled"] is False

    # Verify persistence
    r = client.get("/api/v1/device-offline/settings")
    assert r.status_code == 200
    data = r.json()
    assert data["enabled"] is False
    assert data["offline_timeout_minutes"] == 10


# ============================================================
# Test: Startup grace period
# ============================================================
def test_startup_grace_period():
    """Monitor must respect startup grace period."""
    with SessionLocal() as s:
        device = _create_device(s, last_seen_minutes_ago=10)
        _create_device_offline_settings(s, timeout_minutes=5)
        dev_id = device.id

    bus = EventBus()
    # Set grace period to 300 seconds (5 minutes)
    monitor = DeviceOfflineMonitor(check_interval_seconds=1, startup_grace_seconds=300, bus=bus)
    # Simulate that the monitor started recently (within grace period)
    monitor._started_at = datetime.now(UTC)
    import asyncio
    asyncio.run(monitor._check_devices())

    with SessionLocal() as s:
        device = s.query(Device).filter(Device.id == dev_id).first()
        # Device should still be online during grace period
        assert device.online is True, "Device should remain online during grace period"
        alarm = s.query(AlarmEvent).filter(
            AlarmEvent.device_id == dev_id,
            AlarmEvent.alarm_type == "DEVICE_OFFLINE",
        ).first()
        assert alarm is None, "No alarm should be created during grace period"


# ============================================================
# Test: Disabled settings prevent alarm creation
# ============================================================
def test_disabled_settings_no_alarm():
    """When device offline detection is disabled, no alarm should be created."""
    with SessionLocal() as s:
        device = _create_device(s, last_seen_minutes_ago=10)
        _create_device_offline_settings(s, enabled=False, timeout_minutes=5)
        dev_id = device.id

    bus = EventBus()
    monitor = DeviceOfflineMonitor(check_interval_seconds=1, startup_grace_seconds=0, bus=bus)
    import asyncio
    asyncio.run(monitor._check_devices())

    with SessionLocal() as s:
        alarm = s.query(AlarmEvent).filter(
            AlarmEvent.device_id == dev_id,
            AlarmEvent.alarm_type == "DEVICE_OFFLINE",
        ).first()
        assert alarm is None, "No alarm should be created when detection is disabled"


# ============================================================
# Test: Device with no last_seen is skipped
# ============================================================
def test_device_with_no_last_seen_skipped():
    """Device that never communicated (last_seen is None) should be skipped."""
    with SessionLocal() as s:
        device = _create_device(s)
        device.last_seen = None
        s.commit()
        dev_id = device.id
        _create_device_offline_settings(s, timeout_minutes=5)

    bus = EventBus()
    monitor = DeviceOfflineMonitor(check_interval_seconds=1, startup_grace_seconds=0, bus=bus)
    import asyncio
    asyncio.run(monitor._check_devices())

    with SessionLocal() as s:
        alarm = s.query(AlarmEvent).filter(
            AlarmEvent.device_id == dev_id,
            AlarmEvent.alarm_type == "DEVICE_OFFLINE",
        ).first()
        assert alarm is None, "No alarm should be created for device with no last_seen"
