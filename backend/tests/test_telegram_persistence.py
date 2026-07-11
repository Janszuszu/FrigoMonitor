"""Tests for persistent Telegram notification deduplication.

These tests verify that Telegram notifications are sent exactly once per
alarm event, and that the deduplication state survives backend restarts
because it is stored in the database (AlarmEvent.telegram_notification_sent_at).
"""
import sys
import os
from datetime import datetime, UTC, timedelta
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

import pytest

from app.database import SessionLocal, engine, Base
from app.models.sensor import Sensor
from app.models.device import Device
from app.models.alarm_event import AlarmEvent
from app.models.telegram_settings import TelegramSettings
from app.services.telegram_service import (
    send_alarm_notification,
    _sent_notifications,
    _has_notification_been_sent,
    _mark_notification_sent,
    clear_notification_tracking,
    clear_all_notification_tracking,
)
from app.services.alarm_service import AlarmState


@pytest.fixture(autouse=True)
def clean_db():
    """Ensure a clean database for each test."""
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
    _sent_notifications.clear()
    yield
    _sent_notifications.clear()


@pytest.fixture
def telegram_settings():
    """Create enabled Telegram settings in the database."""
    with SessionLocal() as session:
        settings = TelegramSettings(
            enabled=True,
            bot_token="test:bot_token",
            chat_id="test_chat_id",
        )
        session.add(settings)
        session.commit()
    return settings


@pytest.fixture
def device():
    """Create a test device."""
    with SessionLocal() as session:
        d = Device(name="Test Device", serial_number="TEST001", device_id="TEST001")
        session.add(d)
        session.commit()
        session.refresh(d)
        return d


@pytest.fixture
def sensor(device):
    """Create a test sensor."""
    with SessionLocal() as session:
        s = Sensor(
            device_id=device.id,
            name="Test Sensor",
            sensor_id="sensor-01",
            sensor_type="DS18B20",
            unit="C",
            alarm_enabled=True,
            alarm_high=30.0,
            alarm_low=-10.0,
            alarm_hysteresis=1.0,
            alarm_activation_delay=0,
            alarm_state=AlarmState.NORMAL,
            alarm_no_data_enabled=True,
            alarm_no_data_timeout=15,
            alarm_no_data_state=AlarmState.NORMAL,
        )
        session.add(s)
        session.commit()
        session.refresh(s)
        return s


def _create_active_alarm_event(session, sensor, device, alarm_type, activated_at=None):
    """Helper to create an active alarm event. Returns the event ID."""
    event = AlarmEvent(
        sensor_id=sensor.id,
        device_id=device.id,
        alarm_type=alarm_type,
        threshold=30.0 if alarm_type == AlarmState.ALARM_HIGH else -10.0,
        temperature=35.0 if alarm_type == AlarmState.ALARM_HIGH else -15.0,
        state=alarm_type,
        activated_at=activated_at or datetime.now(UTC),
    )
    session.add(event)
    session.commit()
    return event.id


class TestTelegramPersistence:
    """Tests for persistent Telegram notification deduplication."""

    def test_notification_sent_once_for_active_alarm(self, telegram_settings, sensor, device):
        """Alarm becomes ACTIVE -> Telegram sent once -> DB field is set."""
        with SessionLocal() as session:
            event_id = _create_active_alarm_event(session, sensor, device, AlarmState.ALARM_HIGH)

        # Mock the actual HTTP call to Telegram
        with patch("app.services.telegram_service.send_telegram_message", return_value=(True, "OK")):
            send_alarm_notification(
                sensor=sensor,
                device=device,
                alarm_type=AlarmState.ALARM_HIGH,
                current_value=35.0,
                threshold=30.0,
                activated_at=datetime.now(UTC),
            )

        # Verify DB field is set
        with SessionLocal() as session:
            updated = session.query(AlarmEvent).filter(AlarmEvent.id == event_id).first()
            assert updated is not None
            assert updated.telegram_notification_sent_at is not None

    def test_no_duplicate_after_restart(self, telegram_settings, sensor, device):
        """Simulate backend restart: fresh service instance with no in-memory state
        should NOT send another notification for the same active alarm."""
        with SessionLocal() as session:
            event_id = _create_active_alarm_event(session, sensor, device, AlarmState.ALARM_HIGH)
            # Mark as already sent (simulating previous notification)
            event = session.query(AlarmEvent).filter(AlarmEvent.id == event_id).first()
            event.telegram_notification_sent_at = datetime.now(UTC)
            session.commit()

        # Clear in-memory cache (simulating restart)
        _sent_notifications.clear()

        # Now process another measurement for the same still-active alarm
        call_count = 0

        def counting_send(text, bot_token, chat_id, timeout_seconds=10):
            nonlocal call_count
            call_count += 1
            return True, "OK"

        with patch("app.services.telegram_service.send_telegram_message", side_effect=counting_send):
            send_alarm_notification(
                sensor=sensor,
                device=device,
                alarm_type=AlarmState.ALARM_HIGH,
                current_value=36.0,
                threshold=30.0,
                activated_at=datetime.now(UTC),
            )

        # Telegram should NOT be called again
        assert call_count == 0, "Telegram was called again after restart despite DB field being set"

    def test_new_alarm_event_allows_new_notification(self, telegram_settings, sensor, device):
        """After alarm resolves and a new alarm event occurs, a new notification is sent."""
        with SessionLocal() as session:
            # Create a resolved (cleared) alarm event with notification already sent
            old_event = AlarmEvent(
                sensor_id=sensor.id,
                device_id=device.id,
                alarm_type=AlarmState.ALARM_HIGH,
                threshold=30.0,
                temperature=35.0,
                state=AlarmState.CLEARED,
                activated_at=datetime.now(UTC) - timedelta(hours=2),
                cleared_at=datetime.now(UTC) - timedelta(hours=1),
                telegram_notification_sent_at=datetime.now(UTC) - timedelta(hours=2),
            )
            session.add(old_event)
            session.commit()

        # Clear in-memory cache
        _sent_notifications.clear()

        # Now create a NEW active alarm event (new alarm after resolution)
        with SessionLocal() as session:
            _create_active_alarm_event(session, sensor, device, AlarmState.ALARM_HIGH)

        call_count = 0

        def counting_send(text, bot_token, chat_id, timeout_seconds=10):
            nonlocal call_count
            call_count += 1
            return True, "OK"

        with patch("app.services.telegram_service.send_telegram_message", side_effect=counting_send):
            send_alarm_notification(
                sensor=sensor,
                device=device,
                alarm_type=AlarmState.ALARM_HIGH,
                current_value=35.0,
                threshold=30.0,
                activated_at=datetime.now(UTC),
            )

        # Telegram should be called for the new event
        assert call_count == 1, "New alarm event should trigger a new notification"

    def test_failed_send_does_not_mark_sent(self, telegram_settings, sensor, device):
        """If Telegram send fails, the DB field should NOT be set."""
        with SessionLocal() as session:
            event_id = _create_active_alarm_event(session, sensor, device, AlarmState.ALARM_HIGH)

        with patch("app.services.telegram_service.send_telegram_message", return_value=(False, "API Error")):
            send_alarm_notification(
                sensor=sensor,
                device=device,
                alarm_type=AlarmState.ALARM_HIGH,
                current_value=35.0,
                threshold=30.0,
                activated_at=datetime.now(UTC),
            )

        # Verify DB field is NOT set
        with SessionLocal() as session:
            updated = session.query(AlarmEvent).filter(AlarmEvent.id == event_id).first()
            assert updated is not None
            assert updated.telegram_notification_sent_at is None, \
                "DB field should not be set when Telegram send fails"

    def test_retry_possible_after_failure(self, telegram_settings, sensor, device):
        """After a failed send, a retry should still be possible."""
        with SessionLocal() as session:
            event_id = _create_active_alarm_event(session, sensor, device, AlarmState.ALARM_HIGH)

        # First attempt fails
        with patch("app.services.telegram_service.send_telegram_message", return_value=(False, "API Error")):
            send_alarm_notification(
                sensor=sensor,
                device=device,
                alarm_type=AlarmState.ALARM_HIGH,
                current_value=35.0,
                threshold=30.0,
                activated_at=datetime.now(UTC),
            )

        # Clear in-memory cache (simulating restart or next measurement cycle)
        _sent_notifications.clear()

        # Second attempt succeeds
        call_count = 0

        def counting_send(text, bot_token, chat_id, timeout_seconds=10):
            nonlocal call_count
            call_count += 1
            return True, "OK"

        with patch("app.services.telegram_service.send_telegram_message", side_effect=counting_send):
            send_alarm_notification(
                sensor=sensor,
                device=device,
                alarm_type=AlarmState.ALARM_HIGH,
                current_value=35.0,
                threshold=30.0,
                activated_at=datetime.now(UTC),
            )

        assert call_count == 1, "Retry after failure should send notification"

        # Verify DB field IS now set
        with SessionLocal() as session:
            updated = session.query(AlarmEvent).filter(AlarmEvent.id == event_id).first()
            assert updated is not None
            assert updated.telegram_notification_sent_at is not None

    def test_no_data_alarm_deduplication(self, telegram_settings, sensor, device):
        """NO DATA alarm also uses persistent deduplication."""
        with SessionLocal() as session:
            event_id = _create_active_alarm_event(session, sensor, device, AlarmState.NO_DATA)

        with patch("app.services.telegram_service.send_telegram_message", return_value=(True, "OK")):
            send_alarm_notification(
                sensor=sensor,
                device=device,
                alarm_type=AlarmState.NO_DATA,
                current_value=None,
                threshold=None,
                activated_at=datetime.now(UTC),
            )

        # Verify DB field is set
        with SessionLocal() as session:
            updated = session.query(AlarmEvent).filter(AlarmEvent.id == event_id).first()
            assert updated.telegram_notification_sent_at is not None

        # Clear cache and verify no duplicate
        _sent_notifications.clear()

        call_count = 0

        def counting_send(text, bot_token, chat_id, timeout_seconds=10):
            nonlocal call_count
            call_count += 1
            return True, "OK"

        with patch("app.services.telegram_service.send_telegram_message", side_effect=counting_send):
            send_alarm_notification(
                sensor=sensor,
                device=device,
                alarm_type=AlarmState.NO_DATA,
                current_value=None,
                threshold=None,
                activated_at=datetime.now(UTC),
            )

        assert call_count == 0, "NO DATA alarm should not send duplicate after restart"

    def test_low_temperature_alarm_deduplication(self, telegram_settings, sensor, device):
        """LOW TEMPERATURE alarm also uses persistent deduplication."""
        with SessionLocal() as session:
            event_id = _create_active_alarm_event(session, sensor, device, AlarmState.ALARM_LOW)

        with patch("app.services.telegram_service.send_telegram_message", return_value=(True, "OK")):
            send_alarm_notification(
                sensor=sensor,
                device=device,
                alarm_type=AlarmState.ALARM_LOW,
                current_value=-15.0,
                threshold=-10.0,
                activated_at=datetime.now(UTC),
            )

        with SessionLocal() as session:
            updated = session.query(AlarmEvent).filter(AlarmEvent.id == event_id).first()
            assert updated.telegram_notification_sent_at is not None

    def test_clear_notification_tracking(self, telegram_settings, sensor, device):
        """clear_notification_tracking clears the in-memory cache but not the DB field."""
        with SessionLocal() as session:
            event_id = _create_active_alarm_event(session, sensor, device, AlarmState.ALARM_HIGH)
            event = session.query(AlarmEvent).filter(AlarmEvent.id == event_id).first()
            event.telegram_notification_sent_at = datetime.now(UTC)
            session.commit()

        # Populate in-memory cache
        _sent_notifications[f"{sensor.id}:{AlarmState.ALARM_HIGH}"] = True

        # Clear tracking
        clear_notification_tracking(sensor.id, AlarmState.ALARM_HIGH)

        # In-memory cache should be cleared
        assert _sent_notifications.get(f"{sensor.id}:{AlarmState.ALARM_HIGH}") is None

        # DB field should still be set
        with SessionLocal() as session:
            updated = session.query(AlarmEvent).filter(AlarmEvent.id == event_id).first()
            assert updated.telegram_notification_sent_at is not None

    def test_clear_all_notification_tracking(self, telegram_settings, sensor, device):
        """clear_all_notification_tracking clears all in-memory cache."""
        _sent_notifications["test:key"] = True
        clear_all_notification_tracking()
        assert len(_sent_notifications) == 0

    def test_has_notification_been_sent_checks_db(self, telegram_settings, sensor, device):
        """_has_notification_been_sent correctly checks the database."""
        with SessionLocal() as session:
            # No active alarm event yet
            assert _has_notification_been_sent(session, sensor.id, AlarmState.ALARM_HIGH) is False

            # Create active alarm without notification
            event_id = _create_active_alarm_event(session, sensor, device, AlarmState.ALARM_HIGH)
            assert _has_notification_been_sent(session, sensor.id, AlarmState.ALARM_HIGH) is False

            # Mark notification as sent
            _mark_notification_sent(session, sensor.id, AlarmState.ALARM_HIGH)
            assert _has_notification_been_sent(session, sensor.id, AlarmState.ALARM_HIGH) is True

    def test_resolved_alarm_does_not_block_new_notification(self, telegram_settings, sensor, device):
        """A cleared alarm with notification_sent_at should not prevent a new alarm from sending."""
        with SessionLocal() as session:
            # Create a CLEARED alarm event with notification already sent
            old_event = AlarmEvent(
                sensor_id=sensor.id,
                device_id=device.id,
                alarm_type=AlarmState.ALARM_HIGH,
                threshold=30.0,
                temperature=35.0,
                state=AlarmState.CLEARED,
                activated_at=datetime.now(UTC) - timedelta(hours=2),
                cleared_at=datetime.now(UTC) - timedelta(hours=1),
                telegram_notification_sent_at=datetime.now(UTC) - timedelta(hours=2),
            )
            session.add(old_event)
            session.commit()

        # Verify: no active alarm, so _has_notification_been_sent should return False
        with SessionLocal() as session:
            assert _has_notification_been_sent(session, sensor.id, AlarmState.ALARM_HIGH) is False

    def test_concurrent_send_protection(self, telegram_settings, sensor, device):
        """Two near-simultaneous calls should not both send notifications."""
        with SessionLocal() as session:
            _create_active_alarm_event(session, sensor, device, AlarmState.ALARM_HIGH)

        call_count = 0

        def counting_send(text, bot_token, chat_id, timeout_seconds=10):
            nonlocal call_count
            call_count += 1
            return True, "OK"

        # Simulate two near-simultaneous processing calls
        with patch("app.services.telegram_service.send_telegram_message", side_effect=counting_send):
            send_alarm_notification(
                sensor=sensor,
                device=device,
                alarm_type=AlarmState.ALARM_HIGH,
                current_value=35.0,
                threshold=30.0,
                activated_at=datetime.now(UTC),
            )
            send_alarm_notification(
                sensor=sensor,
                device=device,
                alarm_type=AlarmState.ALARM_HIGH,
                current_value=35.0,
                threshold=30.0,
                activated_at=datetime.now(UTC),
            )

        # Only one notification should be sent
        assert call_count == 1, "Two near-simultaneous calls should only send one notification"
