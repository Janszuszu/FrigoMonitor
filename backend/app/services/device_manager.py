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
from datetime import datetime, UTC
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

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
            mqtt_service.subscribe("frigomonitor/device/+/register")
            mqtt_service.subscribe("frigomonitor/device/+/sensor/register")
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

        if self._is_device_register_topic(topic_parts):
            device_id = topic_parts[2]
            self._handle_device_register(device_id, data)
            return

        if self._is_sensor_register_topic(topic_parts):
            device_id = topic_parts[2]
            self._handle_sensor_register(device_id, data)
            return

        # heuristics for serial and sensor name
        serial = self._extract_serial(data, topic_parts)
        sensor_name = self._extract_sensor_name(data, topic_parts)
        sensor_type = data.get("sensor_type") or data.get("type")
        device_name = data.get("device_name") or data.get("name") or serial

        if not serial:
            logger.debug("MQTT message without identifiable serial; skipping registration")
            return

        if str(serial).startswith("driver-"):
            logger.debug("Ignoring internal driver message for serial=%s", serial)
            return

        # Use DB session per message
        try:
            with SessionLocal() as session:
                device = self._get_or_create_device(session, serial, device_name)
                if sensor_name:
                    self._get_or_create_sensor(session, device, sensor_name, sensor_type)
                self._update_last_seen(session, device)
        except SQLAlchemyError:
            logger.error("Database error")

    def _is_device_register_topic(self, topic_parts: list[str]) -> bool:
        return (
            len(topic_parts) == 4
            and topic_parts[0] == "frigomonitor"
            and topic_parts[1] == "device"
            and topic_parts[3] == "register"
        )

    def _is_sensor_register_topic(self, topic_parts: list[str]) -> bool:
        return (
            len(topic_parts) == 5
            and topic_parts[0] == "frigomonitor"
            and topic_parts[1] == "device"
            and topic_parts[3] == "sensor"
            and topic_parts[4] == "register"
        )

    def _handle_device_register(self, device_id: str, data: dict) -> None:
        now = datetime.now(UTC)
        try:
            with SessionLocal() as session:
                device, created, duplicate = self._upsert_device_registration(session, device_id, data, now)
                session.commit()
                if created:
                    logger.info("Device created")
                else:
                    logger.info("Device updated")

                if duplicate:
                    logger.warning("Duplicate registration ignored")
        except SQLAlchemyError:
            logger.error("Database error")

    def _handle_sensor_register(self, device_id: str, data: dict) -> None:
        rom = data.get("rom")
        if not rom:
            logger.warning("Duplicate registration ignored")
            return

        now = datetime.now(UTC)
        try:
            with SessionLocal() as session:
                device, _, _ = self._upsert_device_registration(session, device_id, {}, now)
                sensor, created, duplicate = self._upsert_sensor_registration(session, device, data, now)
                if sensor is None:
                    session.rollback()
                    return
                session.commit()
                if created:
                    logger.info("Sensor created")
                else:
                    logger.info("Sensor updated")

                if duplicate:
                    logger.warning("Duplicate registration ignored")
        except SQLAlchemyError:
            logger.error("Database error")

    def _upsert_device_registration(
        self,
        session: Session,
        device_id: str,
        data: dict,
        now: datetime,
    ) -> tuple[Device, bool, bool]:
        device = session.query(Device).filter(Device.device_id == device_id).one_or_none()
        if device is None:
            device = session.query(Device).filter(Device.serial_number == device_id).one_or_none()

        created = False
        metadata_changed = False
        if device is None:
            device = Device(name=str(data.get("board") or device_id), serial_number=device_id, device_id=device_id)
            session.add(device)
            created = True
            metadata_changed = True
        else:
            if device.device_id != device_id:
                device.device_id = device_id
            if device.serial_number != device_id:
                device.serial_number = device_id

        metadata_changed = self._update_device_metadata(device, data) or metadata_changed
        device.last_seen = now
        return device, created, (not created and not metadata_changed)

    def _update_device_metadata(self, device: Device, data: dict) -> bool:
        changed = False
        mappings = {
            "firmware": "firmware",
            "build": "build",
            "board": "board",
            "chip_id": "chip_id",
            "mac": "mac",
            "ip": "ip",
        }
        for payload_key, attr_name in mappings.items():
            if payload_key in data and data[payload_key] is not None:
                value = str(data[payload_key])
                if getattr(device, attr_name) != value:
                    setattr(device, attr_name, value)
                    changed = True
        return changed

    def _upsert_sensor_registration(
        self,
        session: Session,
        device: Device,
        data: dict,
        now: datetime,
    ) -> tuple[Optional[Sensor], bool, bool]:
        rom = str(data.get("rom"))
        sensor = (
            session.query(Sensor)
            .filter(Sensor.device_id == device.id)
            .filter(Sensor.rom == rom)
            .one_or_none()
        )

        created = False
        duplicate = False

        if sensor is None:
            sensor = Sensor(
                device_id=device.id,
                name=str(data.get("name") or data.get("sensor_id") or rom),
                sensor_id=str(data.get("sensor_id") or ""),
                sensor_type=str(data.get("type") or "DS18B20"),
                unit=str(data.get("unit") or "C"),
                rom=rom,
            )
            session.add(sensor)
            created = True
        else:
            changed = False

            if "sensor_id" in data and data.get("sensor_id") is not None:
                value = str(data.get("sensor_id"))
                if sensor.sensor_id != value:
                    sensor.sensor_id = value
                    changed = True

            if "name" in data and data.get("name") is not None:
                value = str(data.get("name"))
                if sensor.name != value:
                    sensor.name = value
                    changed = True

            if "unit" in data and data.get("unit") is not None:
                value = str(data.get("unit"))
                if sensor.unit != value:
                    sensor.unit = value
                    changed = True

            duplicate = not changed

        sensor.last_seen = now
        device.last_seen = now
        return sensor, created, duplicate

    def _extract_serial(self, data: dict, topic_parts: list[str]) -> Optional[str]:
        # payload keys
        for key in ("serial_number", "serial", "device_serial", "device"):
            if key in data and data[key]:
                return str(data[key])

        # topic format: frigomonitor/device/<serial>/...
        if len(topic_parts) >= 3 and topic_parts[0].lower() == "frigomonitor" and topic_parts[1].lower() == "device":
            return topic_parts[2]

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
            session.query(Device).filter(Device.id == device.id).update({"last_seen": datetime.now(UTC)})
            session.commit()
            logger.debug(f"Updated last_seen for device id={device.id}")
        except Exception:
            session.rollback()
            logger.exception("Failed to update last_seen for device")


# module-level manager instance
device_manager = DeviceManager()
