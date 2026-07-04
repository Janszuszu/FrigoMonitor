"""MQTT service wrapper using paho-mqtt.

Provides connect, disconnect, publish, subscribe and callback hooks.
Uses centralized MQTT protocol definitions from `app.core.mqtt_protocol`.
"""
from __future__ import annotations

import threading
import json
from typing import Optional, Callable

import paho.mqtt.client as mqtt

from app.config import settings
from app.logger import logger
from app.core import mqtt_protocol
from app.services.measurement_service import measurement_service


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
        client.on_subscribe = self._on_subscribe

        # enable automatic reconnect backoff
        try:
            client.reconnect_delay_set(min_delay=1, max_delay=120)
        except Exception:
            # older paho versions may not implement this
            pass
        # configure Last Will for this driver instance
        try:
            lw_topic = mqtt_protocol.topic_status(f"driver-{client_id}")
            lw_payload = json.dumps({
                "protocol_version": mqtt_protocol.PROTOCOL_VERSION,
                "timestamp": mqtt_protocol.now_iso(),
                "serial_number": f"driver-{client_id}",
                "message_id": "driver-lwt",
                "status": "offline",
            })
            client.will_set(lw_topic, lw_payload, qos=mqtt_protocol.RECOMMENDED_QOS.get("status", 1), retain=mqtt_protocol.RETAINED.get("status", True))
        except Exception:
            logger.exception("Failed to configure MQTT Last Will")
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
            (result, mid) = self._client.subscribe(topic, qos=qos)
            logger.info(f"Subscribe request sent: topic={topic} mid={mid} result={result}")
        except Exception:
            logger.exception("Failed to subscribe to MQTT topic")

    def _on_subscribe(self, client: mqtt.Client, userdata, mid, granted_qos):
        logger.info(f"MQTT subscription acknowledged: mid={mid} qos={granted_qos}")

    # Internal paho callbacks
    def _on_connect(self, client: mqtt.Client, userdata, flags, rc: int) -> None:
        logger.info(f"MQTT connected with result code {rc}")
        # subscribe to protocol topics
        try:
            base = mqtt_protocol.TOPIC_PREFIX
            # use single-level wildcard for serial
            self.subscribe(f"{base}/device/+/heartbeat", qos=mqtt_protocol.RECOMMENDED_QOS.get("heartbeat", 0))
            self.subscribe(f"{base}/device/+/measurement", qos=mqtt_protocol.RECOMMENDED_QOS.get("measurement", 1))
            self.subscribe(f"{base}/device/+/alarm", qos=mqtt_protocol.RECOMMENDED_QOS.get("alarm", 1))
            self.subscribe(f"{base}/device/+/status", qos=mqtt_protocol.RECOMMENDED_QOS.get("status", 1))
        except Exception:
            logger.exception("Failed to subscribe to protocol topics on connect")

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
        logger.info(f"MQTT message received on {msg.topic}")

        # decode payload
        try:
            payload_raw = msg.payload.decode("utf-8") if msg.payload is not None else ""
        except Exception:
            payload_raw = ""

        data = {}
        if payload_raw:
            try:
                data = json.loads(payload_raw)
            except Exception:
                logger.warning("Invalid payload: not JSON")
                if self.on_message_cb:
                    try:
                        self.on_message_cb(client, userdata, msg)
                    except Exception:
                        logger.exception("on_message callback raised an exception")
                return

        # basic protocol validation
        pv = data.get("protocol_version")
        if pv and pv != mqtt_protocol.PROTOCOL_VERSION:
            logger.warning("Unknown protocol version: %s", pv)
            return

        # route by topic structure: frigomonitor/device/{serial}/{type}
        parts = [p for p in msg.topic.split("/") if p]
        if len(parts) >= 4 and parts[0] == mqtt_protocol.TOPIC_PREFIX and parts[1] == "device":
            serial = parts[2]
            mtype = parts[3]

            if mtype == "heartbeat":
                logger.info("Heartbeat received from %s", serial)
                # allow device_manager to register/update last_seen
                if self.on_message_cb:
                    try:
                        self.on_message_cb(client, userdata, msg)
                    except Exception:
                        logger.exception("on_message callback raised an exception")
                return

            if mtype == "measurement":
                logger.info("Measurement received from %s", serial)
                # Expect measurement payload fields: sensor_id, value, measured_at(optional)
                sensor_id = data.get("sensor_id") or data.get("sensor")
                value = data.get("value")
                if sensor_id is None or value is None:
                    logger.warning("Invalid payload: missing sensor_id or value")
                    return
                # call measurement service
                try:
                    # measurement_service expects timestamp as datetime; it can accept None
                    measurement_service.save_measurement(serial, sensor_id, float(value), timestamp=None)
                except Exception:
                    logger.exception("Error while calling MeasurementService.save_measurement")
                # also allow device_manager to register device if needed
                if self.on_message_cb:
                    try:
                        self.on_message_cb(client, userdata, msg)
                    except Exception:
                        logger.exception("on_message callback raised an exception")
                return

            if mtype == "alarm":
                logger.info("Alarm received from %s", serial)
                # stub: no business logic yet
                # allow device_manager to process if needed
                if self.on_message_cb:
                    try:
                        self.on_message_cb(client, userdata, msg)
                    except Exception:
                        logger.exception("on_message callback raised an exception")
                return

        # fallback: call registered callback
        if self.on_message_cb:
            try:
                self.on_message_cb(client, userdata, msg)
            except Exception:
                logger.exception("on_message callback raised an exception")


# module-level default service instance
mqtt_service = MQTTService()
