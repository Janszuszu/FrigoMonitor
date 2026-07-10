from __future__ import annotations

import math

from app.drivers.nt57b08.models import ConversionMode, is_disconnected, signed_int16


def convert_register_value(
    raw_value: int,
    mode: ConversionMode,
) -> float | None:
    """Convert a raw register value according to the specified mode.

    Args:
        raw_value: Raw 16-bit register value from the NT57B08.
        mode: Conversion mode to apply.

    Returns:
        Converted float value, or None if conversion fails or value is invalid.

    Note:
        TEMPERATURE_DIRECT_SCALED mode has been verified with physical hardware:
        - Register value is signed int16, divide by 10 for °C.
        - 0xF555 (-2731 signed = -273.1°C) = disconnected NTC channel.
    """
    if mode == ConversionMode.RAW:
        return float(raw_value)

    if mode == ConversionMode.RESISTANCE_OHMS:
        return float(raw_value)

    if mode == ConversionMode.TEMPERATURE_DIRECT_SCALED:
        # Verified with physical NT57B08 hardware:
        # Register value is signed int16, temperature = signed_int16 / 10.0
        # 0xF555 = -2731 = -273.1°C = disconnected channel
        if is_disconnected(raw_value):
            return None
        return signed_int16(raw_value) / 10.0

    if mode == ConversionMode.NTC_10K_B3950:
        return _ntc_10k_b3950(raw_value)

    return float(raw_value)


def _ntc_10k_b3950(resistance_ohms: float) -> float | None:
    """Convert NTC thermistor resistance to temperature using Beta equation.

    Beta parameter equation:
        1/T = 1/T0 + (1/B) * ln(R/R0)

    where:
        T  = temperature in Kelvin
        T0 = 298.15 K  (25°C)
        R0 = 10000 Ω   (nominal resistance at 25°C)
        B  = 3950      (Beta coefficient)
        R  = measured resistance in ohms

    Args:
        resistance_ohms: Measured resistance in ohms.

    Returns:
        Temperature in degrees Celsius, or None if the resistance value
        is invalid (zero or negative).

    Note:
        This conversion is ONLY valid when the register value is confirmed
        to represent resistance in ohms. Do not apply automatically.
    """
    if resistance_ohms <= 0:
        return None

    T0 = 298.15  # 25°C in Kelvin
    R0 = 10000.0
    B = 3950.0

    try:
        inv_T = 1.0 / T0 + (1.0 / B) * math.log(resistance_ohms / R0)
        temperature_k = 1.0 / inv_T
        temperature_c = temperature_k - 273.15
        return temperature_c
    except (ValueError, ArithmeticError, OverflowError):
        return None
