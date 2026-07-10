from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# Physical NT57B08 verified: 0xF555 = signed -2731 = -273.1°C = disconnected NTC
DISCONNECTED_VALUE: int = 0xF555


class ConversionMode(str, Enum):
    """Supported conversion modes for NT57B08 raw register values.

    Verified with physical hardware: NT57B08 returns signed int16 values
    divided by 10 for temperature. 0xF555 (-2731 / -273.1°C) indicates
    a disconnected/unavailable NTC channel.
    """

    RAW = "raw"
    """Return the raw register value as-is (no conversion)."""

    RESISTANCE_OHMS = "resistance_ohms"
    """Interpret register value as resistance in ohms."""

    TEMPERATURE_DIRECT_SCALED = "temperature_direct_scaled"
    """Interpret register value as signed int16 temperature * 10.

    Verified with physical hardware:
        raw 0x00D4 (212) -> signed 212 -> 21.2°C
        raw 0x00D5 (213) -> signed 213 -> 21.3°C
        raw 0xF555 -> signed -2731 -> -273.1°C (disconnected)
    """

    NTC_10K_B3950 = "ntc_10k_b3950"
    """Apply NTC 10K B3950 Beta equation (Steinhart-Hart approximation).

    Only valid when the register value is confirmed to represent
    resistance in ohms. Uses the Beta parameter equation:

        1/T = 1/T0 + (1/B) * ln(R/R0)

    where:
        T  = temperature in Kelvin
        T0 = 298.15 K
        R0 = 10000 Ω
        B  = 3950
        R  = measured resistance in ohms

    Output: temperature in degrees Celsius.
    """


def signed_int16(raw: int) -> int:
    """Decode a 16-bit unsigned value as signed int16.

    Args:
        raw: Unsigned 16-bit register value (0-65535).

    Returns:
        Signed int16 value (-32768 to 32767).
    """
    if raw & 0x8000:
        return raw - 0x10000
    return raw


def is_disconnected(raw: int) -> bool:
    """Check if a raw register value represents a disconnected NTC channel.

    The physical NT57B08 returns 0xF555 (-2731 signed = -273.1°C)
    for channels with no NTC sensor connected.

    Args:
        raw: Raw 16-bit register value.

    Returns:
        True if the value indicates a disconnected channel.
    """
    return raw == DISCONNECTED_VALUE


@dataclass(slots=True, frozen=True)
class NT57B08Channel:
    """Configuration for a single NT57B08 input channel."""

    channel_number: int
    """Physical channel number (1-8)."""

    register_address: int
    """Modbus register address for this channel."""

    name: str
    """Human-readable name for this channel."""

    conversion_mode: ConversionMode = ConversionMode.RAW
    """How to convert the raw register value."""

    unit: str = ""
    """Measurement unit (e.g., 'C', 'ohm', '' for raw)."""

    invalid_low_threshold: float | None = None
    """Values below this threshold are treated as invalid/disconnected."""

    invalid_high_threshold: float | None = None
    """Values above this threshold are treated as invalid/disconnected."""


@dataclass(slots=True)
class NT57B08Config:
    """Configuration for an NT57B08 Modbus RTU driver instance."""

    port: str
    """Serial port path (e.g., /dev/ttyUSB0 or /dev/serial/by-id/...)."""

    baudrate: int = 9600
    parity: str = "N"
    stopbits: int = 1
    bytesize: int = 8
    slave_id: int = 1
    timeout: float = 1.0
    poll_interval_seconds: float = 5.0
    retry_interval_seconds: float = 2.0

    function_code: int = 4
    """Modbus function code: 3 (holding) or 4 (input)."""

    start_register: int = 0
    """First register address to read (0x0000)."""

    channel_count: int = 8
    """Number of consecutive registers to read (1-8)."""

    device_serial: str = "NT57B08-1"
    """Unique device serial for registration."""

    device_name: str = "NT57B08 Module"
    """Human-readable device name."""

    channels: list[NT57B08Channel] = field(default_factory=list)
    """Per-channel configuration. If empty, defaults are generated."""


def make_default_channels(
    start_register: int = 0,
    channel_count: int = 8,
    conversion_mode: ConversionMode = ConversionMode.TEMPERATURE_DIRECT_SCALED,
) -> list[NT57B08Channel]:
    """Generate default channel configurations for an NT57B08 module.

    Default names use the format "NT57B08 CH1" through "NT57B08 CH8"
    for clear identification in the frontend.
    Default conversion mode is TEMPERATURE_DIRECT_SCALED (signed int16 / 10).
    """
    return [
        NT57B08Channel(
            channel_number=i + 1,
            register_address=start_register + i,
            name=f"NT57B08 CH{i + 1}",
            conversion_mode=conversion_mode,
            unit="C",
        )
        for i in range(channel_count)
    ]
