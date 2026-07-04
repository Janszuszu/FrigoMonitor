from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from threading import RLock
from typing import List

from app.core.event_bus import (
    EVENT_ALARM_ACTIVE,
    EVENT_ALARM_CLEARED,
    EVENT_ALARM_PENDING,
    EVENT_NOTIFICATION_CREATED,
    EVENT_NOTIFICATION_SENT,
    Event,
    EventBus,
    event_bus,
)
from app.logger import logger
from app.models.notification import Notification


class NotificationStatus:
    QUEUED = "QUEUED"
    SENT = "SENT"
    FAILED = "FAILED"


class Notifier(ABC):
    @abstractmethod
    def send(self, notification: Notification) -> bool:
        raise NotImplementedError


class TelegramNotifier(Notifier):
    def send(self, notification: Notification) -> bool:
        return True


class EmailNotifier(Notifier):
    def send(self, notification: Notification) -> bool:
        return True


class WebhookNotifier(Notifier):
    def send(self, notification: Notification) -> bool:
        return True


ALARM_SEVERITY = {
    EVENT_ALARM_PENDING: "WARNING",
    EVENT_ALARM_ACTIVE: "HIGH",
    EVENT_ALARM_CLEARED: "INFO",
}


class NotificationService:
    def __init__(self, max_retries: int = 3, bus: EventBus | None = None) -> None:
        self.max_retries = max_retries
        self._drivers: List[Notifier] = []
        self._queue: List[Notification] = []
        self._lock = RLock()
        self._bus = bus or event_bus
        self._bus.subscribe(EVENT_ALARM_PENDING, self._handle_alarm_event)
        self._bus.subscribe(EVENT_ALARM_ACTIVE, self._handle_alarm_event)
        self._bus.subscribe(EVENT_ALARM_CLEARED, self._handle_alarm_event)

    def register_driver(self, driver: Notifier) -> None:
        with self._lock:
            if driver not in self._drivers:
                self._drivers.append(driver)

    def queue(self, notification: Notification) -> Notification:
        self._track(notification)
        with self._lock:
            notification.status = NotificationStatus.QUEUED
        logger.info("Notification queued: %s", notification.title)
        self._publish_notification_event(
            EVENT_NOTIFICATION_CREATED,
            notification,
        )
        return notification

    def send(self, notification: Notification) -> bool:
        self._track(notification)
        result = self._deliver(notification)
        if result:
            self._publish_notification_event(EVENT_NOTIFICATION_SENT, notification)
        return result

    def retry_failed(self) -> int:
        retried = 0
        with self._lock:
            pending = [item for item in self._queue if item.status == NotificationStatus.FAILED]

        for notification in pending:
            if notification.retry_count >= self.max_retries:
                continue
            logger.warning("Retry notification: %s", notification.title)
            if self._deliver(notification):
                retried += 1

        return retried

    def _track(self, notification: Notification) -> None:
        with self._lock:
            if notification.created_at is None:
                notification.created_at = datetime.now(UTC)
            if notification.retry_count is None:
                notification.retry_count = 0
            if notification not in self._queue:
                self._queue.append(notification)

    def _deliver(self, notification: Notification) -> bool:
        with self._lock:
            drivers = list(self._drivers)

        if not drivers:
            logger.error("Delivery failed: %s", notification.title)
            with self._lock:
                notification.status = NotificationStatus.FAILED
                notification.retry_count = (notification.retry_count or 0) + 1
            return False

        succeeded = True
        for driver in drivers:
            try:
                delivered = driver.send(notification)
                if delivered is False:
                    succeeded = False
            except Exception:
                succeeded = False
                logger.exception("Delivery failed: %s", notification.title)

        with self._lock:
            if succeeded:
                notification.status = NotificationStatus.SENT
                notification.sent_at = datetime.now(UTC)
                if notification in self._queue:
                    self._queue.remove(notification)
                logger.info("Notification sent: %s", notification.title)
                return True

            notification.status = NotificationStatus.FAILED
            notification.sent_at = None
            notification.retry_count = (notification.retry_count or 0) + 1
            logger.error("Delivery failed: %s", notification.title)
            return False

    def _handle_alarm_event(self, event: Event) -> None:
        payload = event.payload or {}
        notification = Notification(
            type=event.event_type,
            title=payload.get("title") or f"Alarm event: {event.event_type}",
            message=payload.get("message") or f"Alarm event received from {event.source}",
            severity=payload.get("severity") or ALARM_SEVERITY.get(event.event_type, "INFO"),
        )
        self.queue(notification)
        self.send(notification)

    def _publish_notification_event(self, event_type: str, notification: Notification) -> None:
        self._bus.publish(
            Event(
                event_type=event_type,
                source="NotificationService",
                payload={
                    "notification_id": notification.id,
                    "type": notification.type,
                    "title": notification.title,
                    "message": notification.message,
                    "severity": notification.severity,
                    "status": notification.status,
                    "retry_count": notification.retry_count,
                },
            )
        )


notification_service = NotificationService()
