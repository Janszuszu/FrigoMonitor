from __future__ import annotations

import json
from typing import Any

from app.config import settings
from app.drivers.nt57b08.models import (
    NT57B08Config,
    NT57B08Channel,
    ConversionMode,
    make_default_channels,
)
from app.logger import logger


def _parse_conversion_mode(value: Any) -> ConversionMode:
    raw = str(value or "temperature_direct_scaled").strip().lower()
    try:
        return ConversionMode(raw)
    except ValueError:
        logger.warning("Unknown conversion mode '%s', falling back to 'temperature_direct_scaled'", raw)
        return ConversionMode.TEMPERATURE_DIRECT_SCALED


def _parse_channels(raw: str, start_register: int) -> list[NT57B08Channel]:
    if not raw.strip():
        return []

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Invalid NT57B08 channel config JSON, using defaults")
        return []

    if not isinstance(parsed, list):
        logger.warning("NT57B08 channel config must be a JSON array, using defaults")
        return []

    channels: list[NT57B08Channel] = []
    for item in parsed:
        if not isinstance(item, dict):
            logger.warning("Skipping invalid NT57B08 channel item: not an object")
            continue
        try:
            channel = NT57B08Channel(
                channel_number=int(item.get("channel_number", 0)),
                register_address=int(item.get("register_address", 0)),
                name=str(item.get("name", "CH?")),
                conversion_mode=_parse_conversion_mode(item.get("conversion_mode")),
                unit=str(item.get("unit", "")),
                invalid_low_threshold=(
                    float(item["invalid_low_threshold"])
                    if item.get("invalid_low_threshold") is not None
                    else None
                ),
                invalid_high_threshold=(
                    float(item["invalid_high_threshold"])
                    if item.get("invalid_high_threshold") is not None
                    else None
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Skipping invalid NT57B08 channel item: %s", exc)
            continue
        channels.append(channel)

    return channels


def load_nt57b08_config(index: int = 0) -> NT57B08Config:
    """Load NT57B08 configuration from environment variables.

    Multiple NT57B08 modules are supported via indexed environment variables.
    Index 0 uses the base variable names (NT57B08_PORT, etc.).
    Index 1+ uses NT57B08_1_PORT, NT57B08_2_PORT, etc.
    """
    suffix = f"_{index}" if index > 0 else ""

    port = getattr(settings, f"NT57B08{suffix}_PORT", None) or settings.NT57B08_PORT
    baudrate = getattr(settings, f"NT57B08{suffix}_BAUDRATE", None) or settings.NT57B08_BAUDRATE
    parity = getattr(settings, f"NT57B08{suffix}_PARITY", None) or settings.NT57B08_PARITY
    stopbits = getattr(settings, f"NT57B08{suffix}_STOPBITS", None) or settings.NT57B08_STOPBITS
    bytesize = getattr(settings, f"NT57B08{suffix}_BYTESIZE", None) or settings.NT57B08_BYTESIZE
    slave_id = getattr(settings, f"NT57B08{suffix}_SLAVE_ID", None) or settings.NT57B08_SLAVE_ID
    timeout = getattr(settings, f"NT57B08{suffix}_TIMEOUT", None) or settings.NT57B08_TIMEOUT
    poll_interval = (
        getattr(settings, f"NT57B08{suffix}_POLL_INTERVAL", None)
        or settings.NT57B08_POLL_INTERVAL
    )
    retry_interval = (
        getattr(settings, f"NT57B08{suffix}_RETRY_INTERVAL", None)
        or settings.NT57B08_RETRY_INTERVAL
    )
    function_code = (
        getattr(settings, f"NT57B08{suffix}_FUNCTION_CODE", None)
        or settings.NT57B08_FUNCTION_CODE
    )
    start_register = (
        getattr(settings, f"NT57B08{suffix}_START_REGISTER", None)
        or settings.NT57B08_START_REGISTER
    )
    channel_count = (
        getattr(settings, f"NT57B08{suffix}_CHANNEL_COUNT", None)
        or settings.NT57B08_CHANNEL_COUNT
    )
    device_serial = (
        getattr(settings, f"NT57B08{suffix}_DEVICE_SERIAL", None)
        or f"{settings.NT57B08_DEVICE_SERIAL}-{index + 1}"
    )
    device_name = (
        getattr(settings, f"NT57B08{suffix}_DEVICE_NAME", None)
        or f"{settings.NT57B08_DEVICE_NAME} #{index + 1}"
    )
    conversion_mode = _parse_conversion_mode(
        getattr(settings, f"NT57B08{suffix}_CONVERSION_MODE", None)
        or settings.NT57B08_CONVERSION_MODE
    )
    channels_raw = getattr(settings, f"NT57B08{suffix}_CHANNELS", None) or ""

    channels = _parse_channels(channels_raw, start_register)
    if not channels:
        channels = make_default_channels(start_register, channel_count, conversion_mode)

    return NT57B08Config(
        port=port,
        baudrate=baudrate,
        parity=parity,
        stopbits=stopbits,
        bytesize=bytesize,
        slave_id=slave_id,
        timeout=timeout,
        poll_interval_seconds=poll_interval,
        retry_interval_seconds=retry_interval,
        function_code=function_code,
        start_register=start_register,
        channel_count=channel_count,
        device_serial=device_serial,
        device_name=device_name,
        channels=channels,
    )
