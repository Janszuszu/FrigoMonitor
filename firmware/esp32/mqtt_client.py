"""MQTT manager for FrigoMonitor firmware."""

try:
    import ujson as json
except ImportError:  # pragma: no cover - host syntax checks
    import json

from constants import (
    MQTT_HEARTBEAT_TOPIC_TEMPLATE,
    MQTT_STATUS_OFFLINE,
    MQTT_STATUS_ONLINE,
    MQTT_STATUS_TOPIC_TEMPLATE,
)
from logger import error, info, warning
from system_info import SystemInfo
from umqtt.simple import MQTTClient as UMQTTClient
from version import BUILD_DATE, VERSION


class MQTTManager:
    """Manage MQTT connectivity and publishing for firmware."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        client_id: str,
        keepalive: int = 60,
    ) -> None:
        self._host = host
        self._port = int(port)
        self._username = username
        self._password = password
        self._client_id = client_id
        self._keepalive = int(keepalive)
        self._client = None
        self._connected = False
        self._system_info = SystemInfo()

    def _status_topic(self) -> str:
        """Return device status topic."""
        return MQTT_STATUS_TOPIC_TEMPLATE.format(device_id=self._client_id)

    def _heartbeat_topic(self) -> str:
        """Return device heartbeat topic."""
        return MQTT_HEARTBEAT_TOPIC_TEMPLATE.format(device_id=self._client_id)

    def _register_topic(self) -> str:
        """Return device registration topic."""
        return "frigomonitor/device/%s/register" % self._client_id

    def _sensor_register_topic(self) -> str:
        """Return sensor registration topic."""
        return "frigomonitor/device/%s/sensor/register" % self._client_id

    def _measurement_topic(self) -> str:
        """Return measurement publishing topic."""
        return "frigomonitor/device/%s/measurement" % self._client_id

    def _sensor_id(self, rom: str) -> str:
        """Build deterministic sensor ID from ROM address."""
        return "%s:%s" % (self._client_id, rom)

    def _create_client(self):
        """Create umqtt.simple client instance."""
        user = self._username if self._username else None
        password = self._password if self._password else None
        return UMQTTClient(
            client_id=self._client_id,
            server=self._host,
            port=self._port,
            user=user,
            password=password,
            keepalive=self._keepalive,
        )

    def _payload_to_text(self, payload) -> str:
        """Normalize payload to MQTT text payload."""
        if isinstance(payload, str):
            return payload
        if isinstance(payload, bytes):
            return payload.decode("utf-8")
        return json.dumps(payload)

    def connect(self) -> bool:
        """Connect MQTT client."""
        info("Connecting MQTT...")
        try:
            client = self._create_client()
            client.set_last_will(
                self._status_topic(),
                MQTT_STATUS_OFFLINE,
                retain=True,
                qos=1,
            )
            client.connect()
            self._client = client
            self._connected = True
            info("MQTT Connected")
            return True
        except Exception:
            self._connected = False
            self._client = None
            error("Connection failed")
            return False

    def disconnect(self) -> None:
        """Disconnect MQTT client."""
        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception:
                pass
        self._connected = False
        self._client = None
        info("Disconnected")

    def is_connected(self) -> bool:
        """Return current MQTT connection state."""
        return bool(self._connected)

    def publish(self, topic: str, payload, retain: bool = False, qos: int = 1) -> bool:
        """Publish payload to topic."""
        if self._client is None or not self._connected:
            error("Publish failed")
            return False

        message = self._payload_to_text(payload)
        try:
            self._client.publish(topic, message, retain=retain, qos=qos)
            return True
        except Exception:
            error("MQTT publish failed")
            return False

    def subscribe(self, topic: str, callback=None, qos: int = 1) -> bool:
        """Subscribe to topic with optional callback."""
        if self._client is None or not self._connected:
            return False
        try:
            if callback is not None:
                self._client.set_callback(callback)
            self._client.subscribe(topic, qos=qos)
            return True
        except Exception:
            return False

    def check_messages(self) -> None:
        """Process pending MQTT messages once."""
        if self._client is None or not self._connected:
            return
        try:
            self._client.check_msg()
        except Exception:
            self._connected = False

    def reconnect(self) -> bool:
        """Reconnect once without retry loop."""
        warning("Reconnect requested")
        self.disconnect()
        return self.connect()

    def publish_heartbeat(self) -> bool:
        """Publish one heartbeat payload from SystemInfo snapshot."""
        system_snapshot = self._system_info.snapshot()
        payload = {
            "device_id": self._client_id,
            "firmware": VERSION,
            "build": BUILD_DATE,
            "ip": system_snapshot.get("ip"),
            "mac": system_snapshot.get("mac"),
            "rssi": system_snapshot.get("rssi"),
            "uptime": system_snapshot.get("uptime"),
            "free_memory": system_snapshot.get("free_memory"),
        }
        info("Publishing HEARTBEAT")
        return self.publish(self._heartbeat_topic(), payload, retain=False, qos=1)

    def publish_online(self) -> bool:
        """Publish ONLINE device status."""
        info("Publishing ONLINE")
        return self.publish(
            self._status_topic(),
            MQTT_STATUS_ONLINE,
            retain=True,
            qos=1,
        )

    def publish_device_registration(self) -> bool:
        """Publish one device registration payload."""
        system_snapshot = self._system_info.snapshot()
        payload = {
            "device_id": self._client_id,
            "firmware": VERSION,
            "build": BUILD_DATE,
            "board": self._system_info.get_board_name(),
            "chip_id": system_snapshot.get("chip_id"),
            "mac": system_snapshot.get("mac"),
        }
        published = self.publish(self._register_topic(), payload, retain=False, qos=1)
        if published:
            info("Device registered")
        return published

    def publish_sensor_registration(self, rom: str) -> bool:
        """Publish registration payload for a discovered sensor ROM."""
        payload = {
            "device_id": self._client_id,
            "sensor_id": self._sensor_id(rom),
            "rom": rom,
            "type": "DS18B20",
            "unit": "C",
        }
        published = self.publish(
            self._sensor_register_topic(),
            payload,
            retain=False,
            qos=1,
        )
        if published:
            info("Sensor registered")
        return published

    def publish_measurements(self, measurements: list) -> bool:
        """Publish measurement payload for available sensor readings."""
        prepared = []
        for item in measurements:
            rom = item.get("rom")
            temperature = item.get("temperature")
            if rom is None or temperature is None:
                continue
            prepared.append(
                {
                    "sensor_id": self._sensor_id(str(rom)),
                    "rom": rom,
                    "temperature": temperature,
                }
            )

        if not prepared:
            return False

        payload = {
            "device_id": self._client_id,
            "measurements": prepared,
        }
        published = self.publish(self._measurement_topic(), payload, retain=False, qos=1)
        if published:
            info("Measurement published")
        return published
