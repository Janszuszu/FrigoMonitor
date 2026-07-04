"""Device manager: automatically register devices and sensors from MQTT messages.

Responsibilities:
- register device on first message
- register sensor on first message
- update device.last_seen
- ignore duplicate registrations
- integrate with `mqtt_service.mqtt_service` callbacks
"""
from __future__ import annotations

import json
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.database import SessionLocal
from app.logger import logger
from app.services.mqtt_service import mqtt_service
from app.models.device import Device
from app.models.sensor import Sensor


class DeviceManager:
    def __init__(self) -> None:
        # register message callback
        mqtt_service.on_message_cb = self.handle_message
        # ensure we subscribe when the client connects
        mqtt_service.on_connect_cb = self._on_connect
        logger.info("DeviceManager initialized and bound to mqtt_service callbacks")

    def _on_connect(self, client, userdata, flags, rc) -> None:
        try:
            # subscribe to device/sensor topics to learn about devices
            mqtt_service.subscribe('devices/+/sensors/+')
            logger.info("DeviceManager subscribed to devices/+/sensors/+")
        except Exception:
            logger.exception("DeviceManager failed to subscribe on connect")

    def handle_message(self, client, userdata, msg) -> None:
        """Process incoming MQTT message and register device/sensor if needed.

        Expected payload formats (best-effort):
        - JSON with keys: serial_number, device_name, sensor_name, sensor_type
        - Otherwise infer from topic: e.g. devices/<serial>/sensors/<sensor>
        """
        try:
            payload = msg.payload.decode("utf-8") if msg.payload is not None else ""
        except Exception:
            payload = ""

        data = {}
        if payload:
            try:
                data = json.loads(payload)
            except Exception:
                # not JSON, ignore
                data = {}

        topic_parts = [p for p in msg.topic.split("/") if p]

        # heuristics for serial and sensor name
        serial = self._extract_serial(data, topic_parts)
        sensor_name = self._extract_sensor_name(data, topic_parts)
        sensor_type = data.get("sensor_type") or data.get("type")
        device_name = data.get("device_name") or data.get("name") or serial

        if not serial:
            logger.debug("MQTT message without identifiable serial; skipping registration")
            return

        # Use DB session per message
        with SessionLocal() as session:
            device = self._get_or_create_device(session, serial, device_name)
            if sensor_name:
                self._get_or_create_sensor(session, device, sensor_name, sensor_type)
            self._update_last_seen(session, device)

    def _extract_serial(self, data: dict, topic_parts: list[str]) -> Optional[str]:
        # payload keys
        for key in ("serial_number", "serial", "device_serial", "device"):
            if key in data and data[key]:
                return str(data[key])

        # topic heuristics: devices/<serial>/...
        if len(topic_parts) >= 2 and topic_parts[0].lower() in ("devices", "device"):
            return topic_parts[1]

        # fallback: first topic part could be serial
        if topic_parts:
            return topic_parts[0]

        return None

    def _extract_sensor_name(self, data: dict, topic_parts: list[str]) -> Optional[str]:
        for key in ("sensor_name", "sensor", "s"):
            if key in data and data[key]:
                return str(data[key])

        # topic heuristics: .../sensors/<sensor>
        if "sensors" in topic_parts:
            idx = topic_parts.index("sensors")
            if idx + 1 < len(topic_parts):
                return topic_parts[idx + 1]

        # fallback: last topic part may identify sensor
        if topic_parts:
            return topic_parts[-1]

        return None

    def _get_or_create_device(self, session: Session, serial: str, name: Optional[str]) -> Device:
        device = session.query(Device).filter(Device.serial_number == serial).one_or_none()
        if device:
            logger.debug(f"Device already registered: {serial}")
            return device

        device = Device(name=name or serial, serial_number=serial)
        session.add(device)
        session.commit()
        session.refresh(device)
        logger.info(f"Registered new device: serial={serial}, id={device.id}")
        return device

    def _get_or_create_sensor(self, session: Session, device: Device, name: str, sensor_type: Optional[str]) -> Sensor:
        sensor = (
            session.query(Sensor)
            .filter(Sensor.device_id == device.id)
            .filter(Sensor.name == name)
            .one_or_none()
        )
        if sensor:
            logger.debug(f"Sensor already registered: device_id={device.id} name={name}")
            return sensor

        sensor = Sensor(device_id=device.id, name=name, sensor_type=sensor_type)
        session.add(sensor)
        session.commit()
        session.refresh(sensor)
        logger.info(f"Registered new sensor: device_id={device.id} sensor_id={sensor.id} name={name}")
        return sensor

    def _update_last_seen(self, session: Session, device: Device) -> None:
        try:
            session.query(Device).filter(Device.id == device.id).update({"last_seen": func.now()})
            session.commit()
            logger.debug(f"Updated last_seen for device id={device.id}")
        except Exception:
            session.rollback()
            logger.exception("Failed to update last_seen for device")


# module-level manager instance
device_manager = DeviceManager()
