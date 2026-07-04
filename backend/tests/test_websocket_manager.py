import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

import pytest
from fastapi.testclient import TestClient

from app.core.event_bus import (
    EVENT_ALARM_ACTIVE,
    EVENT_MEASUREMENT_SAVED,
    Event,
    EventBus,
)
from main import app
from app.ws import websocket_manager as ws_module
from app.ws.websocket_manager import WebSocketManager


class FakeWebSocket:
    def __init__(self):
        self.messages = []
        self.closed = False

    async def accept(self):
        return None

    async def send_json(self, payload):
        self.messages.append(payload)

    async def receive_text(self):
        await asyncio.sleep(0)
        raise RuntimeError("not used")

    async def close(self):
        self.closed = True


@pytest.fixture
def manager_and_bus(monkeypatch):
    bus = EventBus()
    manager = WebSocketManager(bus=bus, heartbeat_interval=0.05)
    monkeypatch.setattr(ws_module, "manager", manager)
    return manager, bus


@pytest.fixture
def client(manager_and_bus):
    with TestClient(app) as test_client:
        yield test_client


def test_connect_and_disconnect(client, manager_and_bus):
    manager, _ = manager_and_bus
    with client.websocket_connect("/ws"):
        assert manager.client_count == 1
    assert manager.client_count == 0


def test_broadcast(manager_and_bus):
    manager, _ = manager_and_bus
    first = FakeWebSocket()
    second = FakeWebSocket()

    async def run_broadcast() -> None:
        await manager.connect(first)
        await manager.connect(second)
        await manager.broadcast(
            Event(
                event_type=EVENT_MEASUREMENT_SAVED,
                source="test",
                payload={"value": 2.5},
            )
        )
        await manager.disconnect(first)
        await manager.disconnect(second)

    asyncio.run(run_broadcast())

    assert first.messages[0]["event"] == EVENT_MEASUREMENT_SAVED
    assert second.messages[0]["payload"]["value"] == 2.5


def test_multiple_clients_receive_event(client, manager_and_bus):
    _, bus = manager_and_bus
    with client.websocket_connect("/ws") as first, client.websocket_connect("/ws") as second:
        bus.publish(
            Event(
                event_type=EVENT_ALARM_ACTIVE,
                source="AlarmService",
                payload={"message": "alarm active"},
            )
        )

        assert first.receive_json()["event"] == EVENT_ALARM_ACTIVE
        assert second.receive_json()["event"] == EVENT_ALARM_ACTIVE


def test_event_forwarding(client, manager_and_bus):
    _, bus = manager_and_bus
    with client.websocket_connect("/ws") as websocket:
        bus.publish(
            Event(
                event_type=EVENT_MEASUREMENT_SAVED,
                source="MeasurementService",
                payload={"sensor_id": 1, "value": 4.2},
            )
        )

        message = websocket.receive_json()
        assert message["event"] == EVENT_MEASUREMENT_SAVED
        assert message["payload"]["sensor_id"] == 1


def test_heartbeat(client, manager_and_bus):
    manager, _ = manager_and_bus
    manager.heartbeat_interval = 0.01

    with client.websocket_connect("/ws") as websocket:
        heartbeat = websocket.receive_json()
        assert heartbeat["event"] == "heartbeat"
        assert heartbeat["payload"]["ping"] is True
