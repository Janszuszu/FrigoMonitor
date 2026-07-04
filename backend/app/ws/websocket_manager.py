from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.event_bus import (
    EVENT_ALARM_ACTIVE,
    EVENT_ALARM_CLEARED,
    EVENT_ALARM_PENDING,
    EVENT_DEVICE_OFFLINE,
    EVENT_DEVICE_ONLINE,
    EVENT_MEASUREMENT_SAVED,
    EVENT_NOTIFICATION_CREATED,
    EVENT_NOTIFICATION_SENT,
    Event,
    EventBus,
    event_bus,
)
from app.logger import logger

SUPPORTED_WS_EVENTS = {
    EVENT_MEASUREMENT_SAVED,
    EVENT_ALARM_PENDING,
    EVENT_ALARM_ACTIVE,
    EVENT_ALARM_CLEARED,
    EVENT_NOTIFICATION_CREATED,
    EVENT_NOTIFICATION_SENT,
    EVENT_DEVICE_ONLINE,
    EVENT_DEVICE_OFFLINE,
}

router = APIRouter()


@dataclass(slots=True)
class _ClientState:
    websocket: WebSocket
    heartbeat_task: asyncio.Task[None] | None = None


class WebSocketManager:
    def __init__(self, bus: EventBus | None = None, heartbeat_interval: float = 30.0) -> None:
        self._bus = bus or event_bus
        self.heartbeat_interval = heartbeat_interval
        self._clients: dict[int, _ClientState] = {}
        self._lock = RLock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._event_queue: asyncio.Queue[Event] | None = None
        self._worker_task: asyncio.Task[None] | None = None
        for event_type in SUPPORTED_WS_EVENTS:
            self._bus.subscribe(event_type, self._handle_event)

    @property
    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)

    async def connect(self, websocket: WebSocket) -> None:
        self._ensure_runtime()
        await websocket.accept()
        key = id(websocket)
        heartbeat_task = asyncio.create_task(self._heartbeat(websocket))
        with self._lock:
            self._clients[key] = _ClientState(websocket=websocket, heartbeat_task=heartbeat_task)
        logger.info("Client connected")

    async def disconnect(self, websocket: WebSocket) -> None:
        key = id(websocket)
        heartbeat_task: asyncio.Task[None] | None = None
        with self._lock:
            state = self._clients.pop(key, None)
            if state is not None:
                heartbeat_task = state.heartbeat_task
        if heartbeat_task is not None:
            heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task
        logger.info("Client disconnected")
        self._stop_worker_if_idle()

    async def broadcast(self, event: Event) -> None:
        payload = self._serialize_event(event)
        logger.info("Broadcast event: %s", event.event_type)
        with self._lock:
            clients = list(self._clients.values())

        failed = False
        for state in clients:
            try:
                await state.websocket.send_json(payload)
            except Exception:
                failed = True
                logger.warning("Broken websocket")
                await self._remove_client(state.websocket)

        if failed:
            logger.error("Broadcast failed")

    def _handle_event(self, event: Event) -> None:
        with self._lock:
            loop = self._loop
            queue = self._event_queue
        if loop is None or queue is None:
            return
        loop.call_soon_threadsafe(queue.put_nowait, event)

    def _ensure_runtime(self) -> None:
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        if self._event_queue is None:
            self._event_queue = asyncio.Queue()
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker())

    async def _worker(self) -> None:
        assert self._event_queue is not None
        while True:
            event = await self._event_queue.get()
            try:
                await self.broadcast(event)
            finally:
                self._event_queue.task_done()

    async def _heartbeat(self, websocket: WebSocket) -> None:
        try:
            while True:
                await asyncio.sleep(self.heartbeat_interval)
                await websocket.send_json(
                    {
                        "event": "heartbeat",
                        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                        "payload": {"ping": True},
                    }
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Broken websocket")
            await self._remove_client(websocket)

    async def _remove_client(self, websocket: WebSocket) -> None:
        key = id(websocket)
        heartbeat_task: asyncio.Task[None] | None = None
        with self._lock:
            state = self._clients.pop(key, None)
            if state is not None:
                heartbeat_task = state.heartbeat_task
        if heartbeat_task is not None and heartbeat_task is not asyncio.current_task():
            heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task
        self._stop_worker_if_idle()

    def _stop_worker_if_idle(self) -> None:
        with self._lock:
            if self._clients:
                return
            worker = self._worker_task
            self._worker_task = None
        if worker is not None:
            worker.cancel()

    @staticmethod
    def _serialize_event(event: Event) -> dict[str, Any]:
        return {
            "event": event.event_type,
            "timestamp": event.timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "payload": event.payload,
        }


manager = WebSocketManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)
