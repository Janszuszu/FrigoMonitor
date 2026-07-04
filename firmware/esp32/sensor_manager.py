"""Sensor manager for firmware sensors."""

import config
from drivers.ds18b20 import DS18B20Driver


class SensorManager:
    """Manage firmware sensor drivers."""

    def __init__(self) -> None:
        self._ds18b20 = DS18B20Driver(config.DS18B20_PIN)
        self._device_id = config.DEVICE_ID

    def _sensor_id(self, rom: str) -> str:
        """Build deterministic sensor ID from ROM address."""
        return "%s:%s" % (self._device_id, rom)

    def discover(self) -> list:
        """Discover sensors via DS18B20 driver."""
        roms = self._ds18b20.discover()
        sensors = []
        for rom in roms:
            sensors.append(
                {
                    "sensor_id": self._sensor_id(rom),
                    "rom": rom,
                    "type": "DS18B20",
                    "unit": "C",
                }
            )
        return sensors

    def read_all(self) -> list:
        """Read all sensors via DS18B20 driver."""
        raw = self._ds18b20.read_all()
        readings = []
        for item in raw:
            rom = item.get("rom")
            readings.append(
                {
                    "sensor_id": self._sensor_id(rom),
                    "rom": rom,
                    "temperature": item.get("temperature"),
                }
            )
        return readings
