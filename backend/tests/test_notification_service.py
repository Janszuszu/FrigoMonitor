import sys
import os

sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

import pytest

from app.core.event_bus import (
    EVENT_ALARM_ACTIVE,
    EVENT_NOTIFICATION_CREATED,
    EVENT_NOTIFICATION_SENT,
    Event,
    EventBus,
)
from app.database import Base, engine
from app.models.notification import Notification
from app.services.notification_service import (
    EmailNotifier,
    NotificationService,
    NotificationStatus,
    Notifier,
    TelegramNotifier,
    WebhookNotifier,
)


@pytest.fixture(autouse=True)
def prepare_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


class RecordingNotifier(Notifier):
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.sent = []

    def send(self, notification: Notification) -> bool:
        if self.should_fail:
            raise RuntimeError("delivery failed")

        self.sent.append(notification.title)
        return True


class FlakyNotifier(Notifier):
    def __init__(self):
        self.calls = 0

    def send(self, notification: Notification) -> bool:
        self.calls += 1
        return self.calls > 1


def build_notification() -> Notification:
    return Notification(
        type="alarm",
        title="Temperature alert",
        message="Temperature is above threshold",
        severity="HIGH",
    )


def test_queue_adds_notification_to_memory_queue():
    service = NotificationService()
    notification = build_notification()

    queued = service.queue(notification)

    assert queued.status == NotificationStatus.QUEUED
    assert queued.created_at is not None
    assert len(service._queue) == 1


def test_register_driver_avoids_duplicates():
    service = NotificationService()
    telegram = TelegramNotifier()
    email = EmailNotifier()
    webhook = WebhookNotifier()

    service.register_driver(telegram)
    service.register_driver(email)
    service.register_driver(webhook)
    service.register_driver(telegram)

    assert len(service._drivers) == 3


def test_send_delivers_notification_and_clears_queue():
    service = NotificationService()
    driver = EmailNotifier()
    service.register_driver(driver)
    notification = build_notification()

    result = service.send(notification)

    assert result is True
    assert notification.status == NotificationStatus.SENT
    assert notification.sent_at is not None
    assert len(service._queue) == 0


def test_send_uses_multiple_drivers():
    service = NotificationService()
    telegram = RecordingNotifier()
    webhook = RecordingNotifier()
    service.register_driver(telegram)
    service.register_driver(webhook)
    notification = build_notification()

    result = service.send(notification)

    assert result is True
    assert telegram.sent == [notification.title]
    assert webhook.sent == [notification.title]


def test_failed_delivery_is_retained_for_retry(caplog):
    service = NotificationService()
    driver = RecordingNotifier(should_fail=True)
    service.register_driver(driver)
    notification = build_notification()

    with caplog.at_level("ERROR"):
        result = service.send(notification)

    assert result is False
    assert notification.status == NotificationStatus.FAILED
    assert notification.retry_count == 1
    assert len(service._queue) == 1
    assert any("Delivery failed" in record.message for record in caplog.records)


def test_retry_failed_resends_notification(caplog):
    service = NotificationService(max_retries=3)
    driver = FlakyNotifier()
    service.register_driver(driver)
    notification = build_notification()

    first_result = service.send(notification)
    assert first_result is False
    assert notification.status == NotificationStatus.FAILED
    assert notification.retry_count == 1

    with caplog.at_level("WARNING"):
        retried = service.retry_failed()

    assert retried == 1
    assert notification.status == NotificationStatus.SENT
    assert notification.sent_at is not None
    assert len(service._queue) == 0
    assert driver.calls == 2
    assert any("Retry notification" in record.message for record in caplog.records)


def test_notification_service_auto_registers_with_event_bus():
    bus = EventBus()
    service = NotificationService(bus=bus)
    driver = RecordingNotifier()
    created_events = []
    sent_events = []

    bus.subscribe(EVENT_NOTIFICATION_CREATED, created_events.append)
    bus.subscribe(EVENT_NOTIFICATION_SENT, sent_events.append)
    service.register_driver(driver)

    bus.publish(
        Event(
            event_type=EVENT_ALARM_ACTIVE,
            source="AlarmService",
            payload={
                "title": "Temperature alarm",
                "message": "Temperature exceeded threshold",
                "severity": "HIGH",
            },
        )
    )

    assert created_events and created_events[0].event_type == EVENT_NOTIFICATION_CREATED
    assert sent_events and sent_events[0].event_type == EVENT_NOTIFICATION_SENT
    assert driver.sent == ["Temperature alarm"]
    assert len(service._queue) == 0
