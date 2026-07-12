"""Tests for the alarm service."""

import sys
import os
from datetime import UTC, datetime, timedelta

sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.device import Device
from app.models.sensor import Sensor
from app.models.alarm_event import AlarmEvent
from app.services.alarm_service import AlarmService, AlarmState



@pytest.fixture
def db_session():
    """Create a fresh in-memory database for each test."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def device(db_session):
    """Create a test device."""
    d = Device(name="TestDevice", serial_number="SN001")
    db_session.add(d)
    db_session.commit()
    db_session.refresh(d)
    return d


@pytest.fixture
def sensor(db_session, device):
    """Create a test sensor with alarm settings."""
    s = Sensor(
        device_id=device.id,
        name="TestSensor",
        sensor_type="temperature",
        alarm_enabled=True,
        alarm_low=-25.0,
        alarm_high=-15.0,
        alarm_activation_delay=600,  # 10 minutes in seconds
        alarm_state=AlarmState.NORMAL,
        alarm_level=None,
        alarm_pending_since=None,
        alarm_no_data_enabled=False,
        alarm_no_data_timeout=15,
        alarm_no_data_state=AlarmState.NORMAL,
        alarm_no_data_since=None,
    )
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


class TestAlarmService:
    """Test suite for AlarmService."""

    def test_high_temperature_pending_state(self, db_session, sensor):
        """Test that high temperature creates a pending state."""
        service = AlarmService()
        now = datetime.now(UTC)

        # Temperature exceeds high threshold
        service.process_measurement(sensor.id, -12.0, now, session=db_session)

        db_session.refresh(sensor)
        assert sensor.alarm_state == AlarmState.PENDING_HIGH
        assert sensor.alarm_level == AlarmState.ALARM_HIGH
        assert sensor.alarm_pending_since is not None

    def test_high_temperature_activation_after_delay(self, db_session, sensor):
        """Test that alarm activates after the configured delay."""
        service = AlarmService()
        now = datetime.now(UTC)

        # First measurement - should go to pending
        service.process_measurement(sensor.id, -12.0, now, session=db_session)

        db_session.refresh(sensor)
        assert sensor.alarm_state == AlarmState.PENDING_HIGH

        # Second measurement after delay - should activate
        later = now + timedelta(seconds=sensor.alarm_activation_delay + 1)
        service.process_measurement(sensor.id, -12.0, later, session=db_session)

        db_session.refresh(sensor)
        assert sensor.alarm_state == AlarmState.ALARM_HIGH
        assert sensor.alarm_level == AlarmState.ALARM_HIGH
        assert sensor.alarm_pending_since is None

    def test_pending_alarm_cancellation_after_recovery(self, db_session, sensor):
        """Test that pending alarm is cancelled when temperature returns to normal."""
        service = AlarmService()
        now = datetime.now(UTC)

        # First measurement - should go to pending
        service.process_measurement(sensor.id, -12.0, now, session=db_session)

        db_session.refresh(sensor)
        assert sensor.alarm_state == AlarmState.PENDING_HIGH

        # Temperature returns to normal - should cancel pending
        service.process_measurement(sensor.id, -20.0, now + timedelta(minutes=1), session=db_session)

        db_session.refresh(sensor)
        assert sensor.alarm_state == AlarmState.NORMAL
        assert sensor.alarm_level is None

    def test_low_temperature_alarm(self, db_session, sensor):
        """Test that low temperature creates alarm after delay."""
        service = AlarmService()
        now = datetime.now(UTC)

        # Temperature below low threshold
        service.process_measurement(sensor.id, -30.0, now, session=db_session)

        db_session.refresh(sensor)
        assert sensor.alarm_state == AlarmState.PENDING_LOW
        assert sensor.alarm_level == AlarmState.ALARM_LOW

        # After delay
        later = now + timedelta(seconds=sensor.alarm_activation_delay + 1)
        service.process_measurement(sensor.id, -30.0, later, session=db_session)

        db_session.refresh(sensor)
        assert sensor.alarm_state == AlarmState.ALARM_LOW

    def test_alarm_recovery(self, db_session, sensor):
        """Test that active alarm clears when temperature returns to normal."""
        service = AlarmService()
        now = datetime.now(UTC)

        # Activate alarm
        service.process_measurement(sensor.id, -12.0, now, session=db_session)
        later = now + timedelta(seconds=sensor.alarm_activation_delay + 1)
        service.process_measurement(sensor.id, -12.0, later, session=db_session)

        db_session.refresh(sensor)
        assert sensor.alarm_state == AlarmState.ALARM_HIGH

        # Temperature returns to normal
        service.process_measurement(sensor.id, -20.0, later + timedelta(minutes=1), session=db_session)

        db_session.refresh(sensor)
        assert sensor.alarm_state == AlarmState.NORMAL
        assert sensor.alarm_level is None

    def test_no_data_alarm(self, db_session, sensor):
        """Test that no-data alarm activates after timeout."""
        sensor.alarm_no_data_enabled = True
        sensor.alarm_no_data_timeout = 1  # 1 minute
        sensor.last_measurement = datetime.now(UTC) - timedelta(minutes=5)
        db_session.commit()

        service = AlarmService()
        service.check_no_data_alarms(session=db_session)

        db_session.refresh(sensor)
        assert sensor.alarm_no_data_state == AlarmState.NO_DATA

    def test_no_data_alarm_clears_on_measurement(self, db_session, sensor):
        """Test that no-data alarm clears when measurement arrives."""
        sensor.alarm_no_data_enabled = True
        sensor.alarm_no_data_timeout = 1
        sensor.last_measurement = datetime.now(UTC) - timedelta(minutes=5)
        sensor.alarm_no_data_state = AlarmState.NO_DATA
        sensor.alarm_no_data_since = datetime.now(UTC) - timedelta(minutes=5)
        db_session.commit()

        service = AlarmService()
        now = datetime.now(UTC)
        service.process_measurement(sensor.id, -20.0, now, session=db_session)

        db_session.refresh(sensor)
        assert sensor.alarm_no_data_state == AlarmState.NORMAL
        assert sensor.alarm_no_data_since is None

    def test_persistence_of_settings(self, db_session, sensor):
        """Test that alarm settings persist in the database."""
        sensor.alarm_low = -30.0
        sensor.alarm_high = -10.0
        sensor.alarm_activation_delay = 300
        sensor.alarm_no_data_enabled = True
        sensor.alarm_no_data_timeout = 30
        db_session.commit()

        # Re-read from database
        db_session.expire_all()
        reloaded = db_session.query(Sensor).filter(Sensor.id == sensor.id).one()

        assert reloaded.alarm_low == -30.0
        assert reloaded.alarm_high == -10.0
        assert reloaded.alarm_activation_delay == 300
        assert reloaded.alarm_no_data_enabled is True
        assert reloaded.alarm_no_data_timeout == 30

    def test_independent_settings_for_different_sensors(self, db_session, device):
        """Test that different sensors have independent alarm settings."""
        s1 = Sensor(
            device_id=device.id,
            name="Sensor1",
            alarm_enabled=True,
            alarm_low=-25.0,
            alarm_high=-15.0,
            alarm_activation_delay=600,
            alarm_state=AlarmState.NORMAL,
            alarm_no_data_enabled=True,
            alarm_no_data_timeout=10,
            alarm_no_data_state=AlarmState.NORMAL,
        )
        s2 = Sensor(
            device_id=device.id,
            name="Sensor2",
            alarm_enabled=False,
            alarm_low=None,
            alarm_high=None,
            alarm_activation_delay=0,
            alarm_state=AlarmState.NORMAL,
            alarm_no_data_enabled=False,
            alarm_no_data_timeout=30,
            alarm_no_data_state=AlarmState.NORMAL,
        )
        db_session.add_all([s1, s2])
        db_session.commit()

        assert s1.alarm_low == -25.0
        assert s1.alarm_high == -15.0
        assert s1.alarm_activation_delay == 600
        assert s1.alarm_no_data_enabled is True
        assert s1.alarm_no_data_timeout == 10

        assert s2.alarm_low is None
        assert s2.alarm_high is None
        assert s2.alarm_activation_delay == 0
        assert s2.alarm_no_data_enabled is False
        assert s2.alarm_no_data_timeout == 30

    def test_alarm_disabled_clears_alarm(self, db_session, sensor):
        """Test that disabling alarms clears any active alarm."""
        service = AlarmService()
        now = datetime.now(UTC)

        # Activate alarm
        service.process_measurement(sensor.id, -12.0, now, session=db_session)
        later = now + timedelta(seconds=sensor.alarm_activation_delay + 1)
        service.process_measurement(sensor.id, -12.0, later, session=db_session)

        db_session.refresh(sensor)
        assert sensor.alarm_state == AlarmState.ALARM_HIGH

        # Disable alarm
        sensor.alarm_enabled = False
        db_session.commit()

        # Process measurement - should clear alarm
        service.process_measurement(sensor.id, -12.0, later + timedelta(minutes=1), session=db_session)

        db_session.refresh(sensor)
        assert sensor.alarm_state == AlarmState.NORMAL

    def test_no_thresholds_no_alarm(self, db_session, sensor):
        """Test that no thresholds configured means no alarm."""
        sensor.alarm_low = None
        sensor.alarm_high = None
        db_session.commit()

        service = AlarmService()
        now = datetime.now(UTC)
        service.process_measurement(sensor.id, 100.0, now, session=db_session)

        db_session.refresh(sensor)
        assert sensor.alarm_state == AlarmState.NORMAL

    def test_alarm_event_created(self, db_session, sensor):
        """Test that alarm events are created in the database."""
        service = AlarmService()
        now = datetime.now(UTC)

        service.process_measurement(sensor.id, -12.0, now, session=db_session)

        events = db_session.query(AlarmEvent).filter(AlarmEvent.sensor_id == sensor.id).all()
        assert len(events) >= 1
        assert events[0].alarm_type == AlarmState.ALARM_HIGH
        assert events[0].state == AlarmState.PENDING_HIGH

    def test_alarm_history_persists(self, db_session, sensor):
        """Test that alarm history persists in the database."""
        service = AlarmService()
        now = datetime.now(UTC)

        # Create alarm event
        service.process_measurement(sensor.id, -12.0, now, session=db_session)

        # Simulate restart by clearing session
        db_session.expire_all()

        # Verify history still exists
        events = db_session.query(AlarmEvent).filter(AlarmEvent.sensor_id == sensor.id).all()
        assert len(events) >= 1

    def test_reset_single_alarm(self, db_session, sensor):
        """Test resetting a single active alarm."""
        service = AlarmService()
        now = datetime.now(UTC)

        # Activate alarm
        service.process_measurement(sensor.id, -12.0, now, session=db_session)
        later = now + timedelta(seconds=sensor.alarm_activation_delay + 1)
        service.process_measurement(sensor.id, -12.0, later, session=db_session)

        db_session.refresh(sensor)
        assert sensor.alarm_state == AlarmState.ALARM_HIGH

        # Find the active alarm event
        event = db_session.query(AlarmEvent).filter(
            AlarmEvent.sensor_id == sensor.id,
            AlarmEvent.state == AlarmState.ALARM_HIGH,
        ).first()
        assert event is not None
        assert event.cleared_at is None

        # Reset the alarm
        result = service.reset_alarm(event.id, session=db_session)
        assert result is True

        # Verify alarm event is cleared
        db_session.refresh(event)
        assert event.state == AlarmState.CLEARED
        assert event.cleared_at is not None

        # Verify sensor state is reset
        db_session.refresh(sensor)
        assert sensor.alarm_state == AlarmState.NORMAL
        assert sensor.alarm_level is None
        assert sensor.alarm_pending_since is None

        # Verify alarm thresholds are preserved
        assert sensor.alarm_low == -25.0
        assert sensor.alarm_high == -15.0
        assert sensor.alarm_enabled is True

    def test_reset_nonexistent_alarm(self, db_session, sensor):
        """Test resetting a nonexistent alarm returns False."""
        service = AlarmService()
        result = service.reset_alarm(99999, session=db_session)
        assert result is False

    def test_reset_already_cleared_alarm(self, db_session, sensor):
        """Test resetting an already cleared alarm returns False."""
        service = AlarmService()
        now = datetime.now(UTC)

        # Activate alarm
        service.process_measurement(sensor.id, -12.0, now, session=db_session)
        later = now + timedelta(seconds=sensor.alarm_activation_delay + 1)
        service.process_measurement(sensor.id, -12.0, later, session=db_session)

        # Find the active alarm event
        event = db_session.query(AlarmEvent).filter(
            AlarmEvent.sensor_id == sensor.id,
            AlarmEvent.state == AlarmState.ALARM_HIGH,
        ).first()
        assert event is not None

        # Reset once
        result = service.reset_alarm(event.id, session=db_session)
        assert result is True

        # Try to reset again - should return False since it's already CLEARED
        result = service.reset_alarm(event.id, session=db_session)
        assert result is False

    def test_reset_all_alarms(self, db_session, device):
        """Test resetting all active alarms."""
        service = AlarmService()
        now = datetime.now(UTC)

        # Create two sensors with alarms
        s1 = Sensor(
            device_id=device.id,
            name="Sensor1",
            alarm_enabled=True,
            alarm_low=-25.0,
            alarm_high=-15.0,
            alarm_activation_delay=0,
            alarm_state=AlarmState.NORMAL,
            alarm_no_data_enabled=False,
            alarm_no_data_timeout=15,
            alarm_no_data_state=AlarmState.NORMAL,
        )
        s2 = Sensor(
            device_id=device.id,
            name="Sensor2",
            alarm_enabled=True,
            alarm_low=-25.0,
            alarm_high=-15.0,
            alarm_activation_delay=0,
            alarm_state=AlarmState.NORMAL,
            alarm_no_data_enabled=False,
            alarm_no_data_timeout=15,
            alarm_no_data_state=AlarmState.NORMAL,
        )
        db_session.add_all([s1, s2])
        db_session.commit()
        db_session.refresh(s1)
        db_session.refresh(s2)

        # Activate alarms on both sensors
        service.process_measurement(s1.id, -12.0, now, session=db_session)
        service.process_measurement(s2.id, -12.0, now, session=db_session)

        db_session.refresh(s1)
        db_session.refresh(s2)
        assert s1.alarm_state == AlarmState.ALARM_HIGH
        assert s2.alarm_state == AlarmState.ALARM_HIGH

        # Reset all alarms
        count = service.reset_all_alarms(session=db_session)
        assert count == 2

        # Verify both sensors are reset
        db_session.refresh(s1)
        db_session.refresh(s2)
        assert s1.alarm_state == AlarmState.NORMAL
        assert s2.alarm_state == AlarmState.NORMAL

        # Verify alarm events are cleared
        active_events = db_session.query(AlarmEvent).filter(
            AlarmEvent.state.in_(["ALARM_HIGH", "ALARM_LOW", "PENDING_HIGH", "PENDING_LOW", "NO_DATA"])
        ).count()
        assert active_events == 0

        # Verify history is preserved (events exist but are CLEARED)
        cleared_events = db_session.query(AlarmEvent).filter(
            AlarmEvent.state == AlarmState.CLEARED
        ).count()
        assert cleared_events >= 2

    def test_reset_all_no_active_alarms(self, db_session):
        """Test resetting all alarms when none are active returns 0."""
        service = AlarmService()
        count = service.reset_all_alarms(session=db_session)
        assert count == 0

    def test_reset_preserves_alarm_configuration(self, db_session, sensor):
        """Test that reset does not change alarm thresholds or enabled state."""
        service = AlarmService()
        now = datetime.now(UTC)

        # Activate alarm
        service.process_measurement(sensor.id, -12.0, now, session=db_session)
        later = now + timedelta(seconds=sensor.alarm_activation_delay + 1)
        service.process_measurement(sensor.id, -12.0, later, session=db_session)

        # Store original config
        orig_low = sensor.alarm_low
        orig_high = sensor.alarm_high
        orig_enabled = sensor.alarm_enabled
        orig_delay = sensor.alarm_activation_delay

        # Find and reset the alarm
        event = db_session.query(AlarmEvent).filter(
            AlarmEvent.sensor_id == sensor.id,
            AlarmEvent.state == AlarmState.ALARM_HIGH,
        ).first()
        service.reset_alarm(event.id, session=db_session)

        # Verify configuration is unchanged
        db_session.refresh(sensor)
        assert sensor.alarm_low == orig_low
        assert sensor.alarm_high == orig_high
        assert sensor.alarm_enabled == orig_enabled
        assert sensor.alarm_activation_delay == orig_delay


