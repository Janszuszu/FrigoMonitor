import sys
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

from app.core.event_bus import (
    EVENT_ALARM_ACTIVE,
    EVENT_MEASUREMENT_SAVED,
    Event,
    EventBus,
)


def test_publish_subscribe():
    bus = EventBus()
    received = []

    def handler(event: Event) -> None:
        received.append(event.event_id)

    bus.subscribe(EVENT_MEASUREMENT_SAVED, handler)
    event = Event(event_type=EVENT_MEASUREMENT_SAVED, source="test", payload={"index": 1})

    bus.publish(event)

    assert received == [event.event_id]


def test_unsubscribe():
    bus = EventBus()
    received = []

    def handler(event: Event) -> None:
        received.append(event.event_id)

    bus.subscribe(EVENT_MEASUREMENT_SAVED, handler)
    bus.unsubscribe(EVENT_MEASUREMENT_SAVED, handler)
    bus.publish(Event(event_type=EVENT_MEASUREMENT_SAVED, source="test", payload={}))

    assert received == []


def test_multiple_subscribers():
    bus = EventBus()
    first = []
    second = []

    def handler_one(event: Event) -> None:
        first.append(event.event_type)

    def handler_two(event: Event) -> None:
        second.append(event.event_type)

    bus.subscribe(EVENT_ALARM_ACTIVE, handler_one)
    bus.subscribe(EVENT_ALARM_ACTIVE, handler_two)
    bus.publish(Event(event_type=EVENT_ALARM_ACTIVE, source="test", payload={}))

    assert first == [EVENT_ALARM_ACTIVE]
    assert second == [EVENT_ALARM_ACTIVE]


def test_event_ordering():
    bus = EventBus()
    received = []

    def handler(event: Event) -> None:
        received.append(event.payload["order"])

    bus.subscribe(EVENT_MEASUREMENT_SAVED, handler)

    bus.publish(Event(event_type=EVENT_MEASUREMENT_SAVED, source="test", payload={"order": 1}))
    bus.publish(Event(event_type=EVENT_MEASUREMENT_SAVED, source="test", payload={"order": 2}))
    bus.publish(Event(event_type=EVENT_MEASUREMENT_SAVED, source="test", payload={"order": 3}))

    assert received == [1, 2, 3]


def test_thread_safety():
    bus = EventBus()
    received = []
    received_lock = Lock()

    def handler(event: Event) -> None:
        with received_lock:
            received.append(event.payload["index"])

    bus.subscribe(EVENT_MEASUREMENT_SAVED, handler)

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [
            executor.submit(
                bus.publish,
                Event(event_type=EVENT_MEASUREMENT_SAVED, source="test", payload={"index": index}),
            )
            for index in range(50)
        ]
        for future in futures:
            future.result()

    assert sorted(received) == list(range(50))
