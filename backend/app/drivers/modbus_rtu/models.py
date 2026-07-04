from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

RegisterType = Literal["holding", "input"]


@dataclass(slots=True, frozen=True)
class RegisterMapping:
    address: int
    register_type: RegisterType
    sensor_uid: str
    name: str
    unit: str
    scale: float = 1.0
    offset: float = 0.0


@dataclass(slots=True)
class ModbusRTUConfig:
    port: str
    baudrate: int
    parity: str
    stopbits: int
    bytesize: int
    slave_id: int
    timeout: float
    poll_interval_seconds: float = 5.0
    retry_interval_seconds: float = 2.0
    device_serial: str = "MODBUS-RTU-1"
    device_name: str = "Modbus RTU Device"
    register_mappings: list[RegisterMapping] = field(default_factory=list)
