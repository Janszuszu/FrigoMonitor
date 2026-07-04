from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from threading import RLock
from typing import List

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


class NotificationService:
    def __init__(self, max_retries: int = 3) -> None:
        self.max_retries = max_retries
        self._drivers: List[Notifier] = []
        self._queue: List[Notification] = []
        self._lock = RLock()

    def register_driver(self, driver: Notifier) -> None:
        with self._lock:
            if driver not in self._drivers:
                self._drivers.append(driver)

    def queue(self, notification: Notification) -> Notification:
        self._track(notification)
        with self._lock:
            notification.status = NotificationStatus.QUEUED
        logger.info("Notification queued: %s", notification.title)
        return notification

    def send(self, notification: Notification) -> bool:
        self._track(notification)
        return self._deliver(notification)

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


notification_service = NotificationService()
