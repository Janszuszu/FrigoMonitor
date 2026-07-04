from __future__ import annotations

from collections.abc import Sequence

from app.drivers.modbus_rtu.models import RegisterMapping


def parse_register_value(registers: Sequence[int], mapping: RegisterMapping) -> float:
    """Return scaled measurement value from raw register list."""
    if not registers:
        raise ValueError("register response is empty")

    raw_value = int(registers[0])
    return (raw_value * mapping.scale) + mapping.offset
