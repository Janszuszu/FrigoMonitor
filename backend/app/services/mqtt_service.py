"""MQTT service wrapper using paho-mqtt.

Provides connect, disconnect, publish, subscribe and callback hooks.
Uses centralized MQTT protocol definitions from `app.core.mqtt_protocol`.
"""
from __future__ import annotations

import threading
import json
from datetime import datetime
from typing import Any, Optional, Callable

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
            # legacy compatibility topics; remove in FrigoMonitor v1.0
            self.subscribe("devices/+/sensors/+", qos=mqtt_protocol.RECOMMENDED_QOS.get("measurement", 1))
            self.subscribe("devices/+/heartbeat", qos=mqtt_protocol.RECOMMENDED_QOS.get("heartbeat", 0))
            self.subscribe("devices/+/status", qos=mqtt_protocol.RECOMMENDED_QOS.get("status", 1))
            self.subscribe("devices/+/alarm", qos=mqtt_protocol.RECOMMENDED_QOS.get("alarm", 1))
            # TODO: Remove legacy topics in FrigoMonitor v1.0
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

    def _normalize_message(self, msg: mqtt.MQTTMessage) -> dict[str, Any] | None:
        try:
            payload_raw = msg.payload.decode("utf-8") if msg.payload is not None else ""
        except Exception:
            payload_raw = ""

        data: dict[str, Any] = {}
        if payload_raw:
            try:
                data = json.loads(payload_raw)
            except Exception:
                logger.warning("Invalid payload: not JSON")
                return {"raw_msg": msg, "invalid_json": True}

        topic_parts = [p for p in msg.topic.split("/") if p]
        normalized: dict[str, Any] = {
            "topic": msg.topic,
            "data": data,
            "legacy": False,
        }

        if len(topic_parts) >= 4 and topic_parts[0] == mqtt_protocol.TOPIC_PREFIX and topic_parts[1] == "device":
            normalized.update(
                {
                    "serial": topic_parts[2],
                    "type": topic_parts[3],
                    "protocol_version": data.get("protocol_version"),
                    "sensor_id": data.get("sensor_id") or data.get("sensor"),
                    "value": data.get("value"),
                    "measurements": data.get("measurements"),
                    "timestamp": data.get("measured_at") or data.get("timestamp"),
                    "status": data.get("status"),
                }
            )
            return normalized

        if len(topic_parts) >= 4 and topic_parts[0].lower() == "devices" and topic_parts[2].lower() == "sensors":
            # Legacy topic format: devices/<serial>/sensors/<sensor_id>
            normalized.update(
                {
                    "serial": topic_parts[1],
                    "type": "measurement",
                    "sensor_id": topic_parts[3],
                    "value": data.get("value") or data.get("val") or data.get("measurement"),
                    "timestamp": data.get("measured_at") or data.get("timestamp"),
                    "protocol_version": data.get("protocol_version") or mqtt_protocol.PROTOCOL_VERSION,
                    "legacy": True,
                }
            )
            return normalized

        if len(topic_parts) >= 3 and topic_parts[0].lower() == "devices" and topic_parts[2].lower() in {"heartbeat", "status", "alarm"}:
            normalized.update(
                {
                    "serial": topic_parts[1],
                    "type": topic_parts[2].lower(),
                    "protocol_version": data.get("protocol_version"),
                    "status": data.get("status"),
                }
            )
            return normalized

        return normalized

    def _validate_protocol(self, normalized: dict[str, Any]) -> bool:
        pv = normalized.get("protocol_version")
        if pv and pv != mqtt_protocol.PROTOCOL_VERSION:
            logger.warning("Unknown protocol version: %s", pv)
            return False
        return True

    def _process_measurement(self, normalized: dict[str, Any]) -> None:
        serial = normalized.get("serial")
        if serial is None:
            logger.warning("Invalid normalized measurement payload: %s", normalized)
            return

        batch = normalized.get("measurements")
        if isinstance(batch, list):
            for item in batch:
                if not isinstance(item, dict):
                    continue
                sensor_id = item.get("sensor_id") or item.get("rom")
                value = item.get("temperature")
                timestamp = None
                ts_value = item.get("measured_at") or item.get("timestamp")
                if ts_value:
                    try:
                        timestamp = datetime.fromisoformat(str(ts_value).replace("Z", "+00:00"))
                    except Exception:
                        logger.warning("Invalid measurement timestamp: %s", ts_value)
                        timestamp = None

                if sensor_id is None or value is None:
                    logger.warning("Invalid normalized measurement payload: %s", normalized)
                    continue

                try:
                    value_f = float(value)
                except (TypeError, ValueError):
                    logger.warning("Invalid measurement value type: %s", value)
                    continue

                try:
                    measurement_service.save_measurement(serial, str(sensor_id), value_f, timestamp=timestamp)
                except Exception:
                    logger.exception("Error while calling MeasurementService.save_measurement")
            return

        sensor_id = normalized.get("sensor_id")
        value = normalized.get("value")
        if sensor_id is None or value is None:
            logger.warning("Invalid normalized measurement payload: %s", normalized)
            return

        try:
            value = float(value)
        except (TypeError, ValueError):
            logger.warning("Invalid measurement value type: %s", normalized.get("value"))
            return

        timestamp = None
        ts_value = normalized.get("timestamp")
        if ts_value:
            try:
                timestamp = datetime.fromisoformat(ts_value.replace("Z", "+00:00"))
            except Exception:
                logger.warning("Invalid measurement timestamp: %s", ts_value)
                timestamp = None

        try:
            measurement_service.save_measurement(serial, sensor_id, value, timestamp=timestamp)
        except Exception:
            logger.exception("Error while calling MeasurementService.save_measurement")

    def _on_message(self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage) -> None:
        logger.info(f"MQTT message received on {msg.topic}")

        normalized = self._normalize_message(msg)
        if normalized is None:
            if self.on_message_cb:
                try:
                    self.on_message_cb(client, userdata, msg)
                except Exception:
                    logger.exception("on_message callback raised an exception")
            return

        if normalized.get("invalid_json"):
            if self.on_message_cb:
                try:
                    self.on_message_cb(client, userdata, msg)
                except Exception:
                    logger.exception("on_message callback raised an exception")
            return

        if not self._validate_protocol(normalized):
            return

        event_type = normalized.get("type")
        serial = normalized.get("serial")

        if event_type == "heartbeat":
            logger.info("Heartbeat received from %s", serial)
            if self.on_message_cb:
                try:
                    self.on_message_cb(client, userdata, msg)
                except Exception:
                    logger.exception("on_message callback raised an exception")
            return

        if event_type == "measurement":
            logger.info("Measurement received from %s", serial)
            self._process_measurement(normalized)
            if self.on_message_cb:
                try:
                    self.on_message_cb(client, userdata, msg)
                except Exception:
                    logger.exception("on_message callback raised an exception")
            return

        if event_type == "alarm":
            logger.info("Alarm received from %s", serial)
            if self.on_message_cb:
                try:
                    self.on_message_cb(client, userdata, msg)
                except Exception:
                    logger.exception("on_message callback raised an exception")
            return

        if self.on_message_cb:
            try:
                self.on_message_cb(client, userdata, msg)
            except Exception:
                logger.exception("on_message callback raised an exception")


# module-level default service instance
mqtt_service = MQTTService()
