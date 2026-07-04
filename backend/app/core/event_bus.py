from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from typing import Any, Callable
from uuid import uuid4

from app.logger import logger

EVENT_MEASUREMENT_SAVED = "measurement.saved"
EVENT_ALARM_PENDING = "alarm.pending"
EVENT_ALARM_ACTIVE = "alarm.active"
EVENT_ALARM_CLEARED = "alarm.cleared"
EVENT_NOTIFICATION_CREATED = "notification.created"
EVENT_NOTIFICATION_SENT = "notification.sent"
EVENT_DEVICE_ONLINE = "device.online"
EVENT_DEVICE_OFFLINE = "device.offline"

SUPPORTED_EVENTS = {
    EVENT_MEASUREMENT_SAVED,
    EVENT_ALARM_PENDING,
    EVENT_ALARM_ACTIVE,
    EVENT_ALARM_CLEARED,
    EVENT_NOTIFICATION_CREATED,
    EVENT_NOTIFICATION_SENT,
    EVENT_DEVICE_ONLINE,
    EVENT_DEVICE_OFFLINE,
}


@dataclass(slots=True)
class Event:
    event_type: str
    source: str
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: uuid4().hex)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


EventHandler = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._subscriptions: dict[str, list[EventHandler]] = {}
        self._lock = RLock()

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        with self._lock:
            handlers = self._subscriptions.setdefault(event_type, [])
            if handler not in handlers:
                handlers.append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        with self._lock:
            handlers = self._subscriptions.get(event_type)
            if not handlers:
                return
            if handler in handlers:
                handlers.remove(handler)
            if not handlers:
                self._subscriptions.pop(event_type, None)

    def publish(self, event: Event) -> Event:
        with self._lock:
            handlers = list(self._subscriptions.get(event.event_type, []))

        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception("Event handler failed for %s", event.event_type)

        return event


event_bus = EventBus()
