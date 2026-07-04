"""Centralized MQTT protocol constants and helpers for FrigoMonitor v1.0.

Contains topic builders, QoS/retain recommendations, and Pydantic payload models describing
the expected JSON payloads for heartbeat, measurement, alarm, registration, and config messages.
"""
from __future__ import annotations

from typing import Any, Dict
from pydantic import BaseModel, Field
from datetime import datetime, timezone

# Protocol version
PROTOCOL_VERSION = "1.0"

# Topic templates
TOPIC_PREFIX = "frigomonitor"
TOPIC_DEVICE_STATUS = f"{TOPIC_PREFIX}/device/{{serial}}/status"
TOPIC_DEVICE_HEARTBEAT = f"{TOPIC_PREFIX}/device/{{serial}}/heartbeat"
TOPIC_DEVICE_MEASUREMENT = f"{TOPIC_PREFIX}/device/{{serial}}/measurement"
TOPIC_DEVICE_ALARM = f"{TOPIC_PREFIX}/device/{{serial}}/alarm"
TOPIC_DEVICE_CONFIG = f"{TOPIC_PREFIX}/device/{{serial}}/config"

# Last Will topic
LAST_WILL_TOPIC = TOPIC_DEVICE_STATUS

# QoS constants
QOS_AT_MOST_ONCE = 0
QOS_AT_LEAST_ONCE = 1
QOS_EXACTLY_ONCE = 2

# Recommended QoS per topic
RECOMMENDED_QOS = {
    "status": QOS_AT_LEAST_ONCE,
    "heartbeat": QOS_AT_MOST_ONCE,
    "measurement": QOS_AT_LEAST_ONCE,
    "alarm": QOS_AT_LEAST_ONCE,
    "config": QOS_AT_LEAST_ONCE,
}

# Retain policy per topic (True/False)
RETAINED = {
    "status": True,
    "heartbeat": False,
    "measurement": False,
    "alarm": False,
    "config": True,
}


def topic_status(serial: str) -> str:
    return TOPIC_DEVICE_STATUS.format(serial=serial)


def topic_heartbeat(serial: str) -> str:
    return TOPIC_DEVICE_HEARTBEAT.format(serial=serial)


def topic_measurement(serial: str) -> str:
    return TOPIC_DEVICE_MEASUREMENT.format(serial=serial)


def topic_alarm(serial: str) -> str:
    return TOPIC_DEVICE_ALARM.format(serial=serial)


def topic_config(serial: str) -> str:
    return TOPIC_DEVICE_CONFIG.format(serial=serial)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# Payload schemas (Pydantic models)
class BasePayload(BaseModel):
    protocol_version: str = Field(PROTOCOL_VERSION)
    timestamp: str = Field(default_factory=now_iso)
    serial_number: str
    message_id: str


class HeartbeatPayload(BasePayload):
    status: str = Field("online")  # online/offline
    uptime_seconds: int | None = None
    firmware: str | None = None


class MeasurementPayload(BasePayload):
    sensor_id: str
    measured_at: str
    value: float
    unit: str | None = None


class AlarmPayload(BasePayload):
    sensor_id: str | None = None
    alarm_type: str
    severity: str | None = None
    details: str | None = None


class RegistrationPayload(BasePayload):
    device_name: str | None = None
    sensors: list[Dict[str, Any]] | None = None


class ConfigPayload(BasePayload):
    config: Dict[str, Any]


__all__ = [
    "PROTOCOL_VERSION",
    "topic_status",
    "topic_heartbeat",
    "topic_measurement",
    "topic_alarm",
    "topic_config",
    "LAST_WILL_TOPIC",
    "RECOMMENDED_QOS",
    "RETAINED",
    "HeartbeatPayload",
    "MeasurementPayload",
    "AlarmPayload",
    "RegistrationPayload",
    "ConfigPayload",
]
