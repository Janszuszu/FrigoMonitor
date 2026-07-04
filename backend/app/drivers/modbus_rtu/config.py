from __future__ import annotations

import json
from typing import Any

from app.config import settings
from app.drivers.modbus_rtu.models import ModbusRTUConfig, RegisterMapping
from app.logger import logger


def _parse_register_type(value: Any) -> str:
    raw = str(value or "holding").strip().lower()
    if raw in {"holding", "hr", "holding_register", "holding_registers"}:
        return "holding"
    if raw in {"input", "ir", "input_register", "input_registers"}:
        return "input"
    raise ValueError(f"unsupported register type: {value}")


def _parse_mappings(raw: str) -> list[RegisterMapping]:
    if not raw.strip():
        return []

    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError("MODBUS_RTU_REGISTER_MAP must be a JSON array")

    mappings: list[RegisterMapping] = []
    for item in parsed:
        if not isinstance(item, dict):
            logger.warning("Skipping invalid Modbus mapping item: not an object")
            continue
        try:
            mapping = RegisterMapping(
                address=int(item["address"]),
                register_type=_parse_register_type(item.get("register_type")),
                sensor_uid=str(item["sensor_uid"]),
                name=str(item.get("name") or item["sensor_uid"]),
                unit=str(item.get("unit") or ""),
                scale=float(item.get("scale", 1.0)),
                offset=float(item.get("offset", 0.0)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Skipping invalid Modbus mapping item: %s", exc)
            continue

        mappings.append(mapping)

    return mappings


def load_modbus_rtu_config() -> ModbusRTUConfig:
    mappings = _parse_mappings(settings.MODBUS_RTU_REGISTER_MAP)
    return ModbusRTUConfig(
        port=settings.MODBUS_RTU_PORT,
        baudrate=settings.MODBUS_RTU_BAUDRATE,
        parity=settings.MODBUS_RTU_PARITY,
        stopbits=settings.MODBUS_RTU_STOPBITS,
        bytesize=settings.MODBUS_RTU_BYTESIZE,
        slave_id=settings.MODBUS_RTU_SLAVE_ID,
        timeout=settings.MODBUS_RTU_TIMEOUT,
        poll_interval_seconds=settings.MODBUS_RTU_POLL_INTERVAL,
        retry_interval_seconds=settings.MODBUS_RTU_RETRY_INTERVAL,
        device_serial=settings.MODBUS_RTU_DEVICE_SERIAL,
        device_name=settings.MODBUS_RTU_DEVICE_NAME,
        register_mappings=mappings,
    )
