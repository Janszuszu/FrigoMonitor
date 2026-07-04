"""DS18B20 driver for FrigoMonitor firmware."""

import time

import config
from constants import (
    DS18B20_CONVERSION_TIME_MS,
    DS18B20_INVALID_HIGH_C,
    DS18B20_INVALID_LOW_C,
)
from logger import error, info, warning

try:
    import machine
    import onewire
    import ds18x20
except ImportError:  # pragma: no cover - host syntax checks
    machine = None
    onewire = None
    ds18x20 = None


class DS18B20Driver:
    """Access DS18B20 sensors on a OneWire bus."""

    def __init__(self, pin_number: int) -> None:
        self._pin_number = int(pin_number)
        self._roms = []
        self._bus = None
        self._sensor = None
        self._initialize_bus()

    def _initialize_bus(self) -> None:
        """Initialize OneWire and DS18X20 interfaces when available."""
        if machine is None or onewire is None or ds18x20 is None:
            return
        try:
            pin = machine.Pin(self._pin_number)
            self._bus = onewire.OneWire(pin)
            self._sensor = ds18x20.DS18X20(self._bus)
        except Exception:
            self._bus = None
            self._sensor = None

    def _rom_to_str(self, rom) -> str:
        """Convert ROM bytes to uppercase hex string."""
        try:
            return "".join("%02X" % byte for byte in rom)
        except Exception:
            return ""

    def _rom_from_str(self, rom_str: str):
        """Convert uppercase hex string to ROM bytes."""
        try:
            text = rom_str.replace(":", "").replace("-", "")
            return bytes(int(text[i : i + 2], 16) for i in range(0, len(text), 2))
        except Exception:
            return None

    def _normalize_rom(self, sensor_rom):
        """Normalize ROM value to bytes for DS18X20 calls."""
        if isinstance(sensor_rom, (bytes, bytearray)):
            return bytes(sensor_rom)
        if isinstance(sensor_rom, str):
            return self._rom_from_str(sensor_rom)
        return None

    def _is_invalid_temperature(self, value: float) -> bool:
        """Check if DS18B20 reading is invalid."""
        if value is None:
            return True
        if value != value:
            return True
        if value == DS18B20_INVALID_HIGH_C:
            return True
        if value == DS18B20_INVALID_LOW_C:
            return True
        return False

    def _apply_offset(self, value: float) -> float:
        """Apply configured temperature offset."""
        return float(value) + float(config.TEMPERATURE_OFFSET_C)

    def discover(self) -> list:
        """Discover sensors and return ROM list as strings."""
        info("Searching sensors...")
        if self._sensor is None:
            self._roms = []
            info("Found 0 sensors")
            return []

        try:
            self._roms = list(self._sensor.scan())
        except Exception:
            self._roms = []

        info("Found %s sensors" % len(self._roms))
        return [self._rom_to_str(rom) for rom in self._roms]

    def read(self, sensor_rom):
        """Read a single sensor and return temperature float or None."""
        if self._sensor is None:
            error("Sensor read failed")
            return None

        rom = self._normalize_rom(sensor_rom)
        if rom is None:
            error("Sensor read failed")
            return None

        info("Reading sensor %s" % self._rom_to_str(rom))

        try:
            self._sensor.convert_temp()
            time.sleep_ms(DS18B20_CONVERSION_TIME_MS)
            value = self._sensor.read_temp(rom)
        except Exception:
            error("Sensor read failed")
            return None

        if self._is_invalid_temperature(value):
            warning("Invalid reading")
            return None

        return self._apply_offset(value)

    def read_all(self) -> list:
        """Read all discovered sensors and return structured list."""
        readings = []
        for rom in self._roms:
            rom_text = self._rom_to_str(rom)
            readings.append(
                {
                    "rom": rom_text,
                    "temperature": self.read(rom),
                }
            )
        return readings

    def sensor_count(self) -> int:
        """Return number of discovered sensors."""
        return len(self._roms)
