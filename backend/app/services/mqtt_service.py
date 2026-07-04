"""MQTT service wrapper using paho-mqtt.

Provides connect, disconnect, publish, subscribe and callback hooks.
Reads broker configuration from `app.config`.
"""
from __future__ import annotations

import threading
from typing import Optional, Callable

import paho.mqtt.client as mqtt

from app.config import settings
from app.logger import logger


class MQTTService:
    def __init__(self) -> None:
        self._client: Optional[mqtt.Client] = None
        self._lock = threading.RLock()

        # callbacks that external code can set
        self.on_connect_cb: Optional[Callable[[mqtt.Client, dict, dict, int], None]] = None
        self.on_disconnect_cb: Optional[Callable[[mqtt.Client, dict, int], None]] = None
        self.on_message_cb: Optional[Callable[[mqtt.Client, dict, mqtt.MQTTMessage], None]] = None

    def _create_client(self) -> mqtt.Client:
        client_id = f"frigomonitor-{threading.get_ident()}"
        client = mqtt.Client(client_id=client_id, userdata=None)

        # assign internal callbacks
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message

        # enable automatic reconnect backoff
        try:
            client.reconnect_delay_set(min_delay=1, max_delay=120)
        except Exception:
            # older paho versions may not implement this
            pass

        return client

    def connect(self, host: Optional[str] = None, port: Optional[int] = None, keepalive: int = 60) -> None:
        """Connect to the MQTT broker using config from `app.config` by default."""
        with self._lock:
            if self._client is not None:
                logger.debug("MQTT client already created, disconnecting first")
                try:
                    self._client.disconnect()
                except Exception:
                    pass

            self._client = self._create_client()

            host = host or settings.MQTT_HOST
            port = port or settings.MQTT_PORT

            # set credentials if provided
            if getattr(settings, "MQTT_USER", "") and getattr(settings, "MQTT_PASSWORD", ""):
                try:
                    self._client.username_pw_set(settings.MQTT_USER, settings.MQTT_PASSWORD)
                except Exception:
                    logger.exception("Failed to set MQTT username/password")

            # start network loop in background thread
            self._client.loop_start()

            try:
                self._client.connect(host, port, keepalive)
                logger.info(f"Connecting to MQTT broker at {host}:{port}")
            except Exception:
                logger.exception("MQTT connect failed")

    def disconnect(self) -> None:
        """Gracefully disconnect the client and stop the network loop."""
        with self._lock:
            if not self._client:
                return
            try:
                self._client.disconnect()
            except Exception:
                logger.exception("Error while disconnecting MQTT client")
            try:
                self._client.loop_stop()
            except Exception:
                logger.exception("Error while stopping MQTT loop")
            self._client = None

    def publish(self, topic: str, payload: str | bytes, qos: int = 0, retain: bool = False) -> None:
        """Publish a message to a topic."""
        if not self._client:
            logger.warning("Publish called but MQTT client is not connected")
            return
        try:
            self._client.publish(topic, payload, qos=qos, retain=retain)
        except Exception:
            logger.exception("Failed to publish MQTT message")

    def subscribe(self, topic: str, qos: int = 0) -> None:
        """Subscribe to a topic."""
        if not self._client:
            logger.warning("Subscribe called but MQTT client is not connected")
            return
        try:
            self._client.subscribe(topic, qos=qos)
        except Exception:
            logger.exception("Failed to subscribe to MQTT topic")

    # Internal paho callbacks
    def _on_connect(self, client: mqtt.Client, userdata, flags, rc: int) -> None:
        logger.info(f"MQTT connected with result code {rc}")
        if self.on_connect_cb:
            try:
                self.on_connect_cb(client, userdata, flags, rc)
            except Exception:
                logger.exception("on_connect callback raised an exception")

    def _on_disconnect(self, client: mqtt.Client, userdata, rc: int) -> None:
        logger.warning(f"MQTT disconnected with result code {rc}")
        if self.on_disconnect_cb:
            try:
                self.on_disconnect_cb(client, userdata, rc)
            except Exception:
                logger.exception("on_disconnect callback raised an exception")

        # paho with loop_start will attempt automatic reconnect if reconnect_delay_set is used

    def _on_message(self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage) -> None:
        logger.debug(f"MQTT message received on {msg.topic}")
        if self.on_message_cb:
            try:
                self.on_message_cb(client, userdata, msg)
            except Exception:
                logger.exception("on_message callback raised an exception")


# module-level default service instance
mqtt_service = MQTTService()
