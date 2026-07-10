from __future__ import annotations

import time
from typing import Callable, Protocol

from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException

from app.drivers.nt57b08.conversion import convert_register_value
from app.drivers.nt57b08.models import NT57B08Config, NT57B08Channel, ConversionMode
from app.logger import logger
from app.services.device_manager import DeviceManager, device_manager
from app.services.measurement_service import MeasurementService, measurement_service


class _ModbusClient(Protocol):
    """Protocol for a Modbus serial client."""

    def connect(self) -> bool: ...
    def close(self) -> None: ...
    def read_holding_registers(self, *args, **kwargs): ...
    def read_input_registers(self, *args, **kwargs): ...


class NT57B08Driver:
    """Modbus RTU driver for the NT57B08 8-channel NTC module.

    Reads all 8 input registers in a single Modbus request,
    converts raw values according to the configured conversion mode,
    and forwards measurements through the existing FrigoMonitor pipeline.
    """

    def __init__(
        self,
        config: NT57B08Config,
        *,
        measurement_service_obj: MeasurementService = measurement_service,
        device_manager_obj: DeviceManager = device_manager,
        client_factory: Callable[[NT57B08Config], _ModbusClient] | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self._measurement_service = measurement_service_obj
        self._device_manager = device_manager_obj
        self._client_factory = client_factory or self._default_client_factory
        self._sleep = sleep_fn
        self._client: _ModbusClient | None = None
        self._connected = False
        self._running = False
        self._registered = False

    @staticmethod
    def _default_client_factory(config: NT57B08Config) -> _ModbusClient:
        return ModbusSerialClient(
            port=config.port,
            baudrate=config.baudrate,
            parity=config.parity,
            stopbits=config.stopbits,
            bytesize=config.bytesize,
            timeout=config.timeout,
        )

    def start(self) -> None:
        self._running = True
        logger.info(
            "NT57B08 driver started: port=%s slave=%s channels=%d",
            self.config.port,
            self.config.slave_id,
            self.config.channel_count,
        )

    def stop(self) -> None:
        self._running = False
        self._disconnect()

    def run_forever(self) -> None:
        """Main polling loop. Runs until stop() is called."""
        self.start()
        while self._running:
            ok = self.poll_once()
            delay = self.config.poll_interval_seconds if ok else self.config.retry_interval_seconds
            self._sleep(delay)

    def poll_once(self) -> bool:
        """Perform a single poll cycle: read all channels and store measurements.

        Returns:
            True if communication succeeded, False on failure.
        """
        if not self._ensure_connected():
            return False

        if not self._registered:
            self._ensure_registration()

        raw_registers = self._read_all_channels()
        if raw_registers is None:
            return False

        values_stored = 0
        for channel in self.config.channels:
            channel_index = channel.channel_number - 1
            if channel_index < 0 or channel_index >= len(raw_registers):
                logger.warning(
                    "Channel %d out of range (0-%d), skipping",
                    channel.channel_number,
                    len(raw_registers) - 1,
                )
                continue

            raw_value = raw_registers[channel_index]
            converted = self._convert_channel(raw_value, channel)

            if converted is None:
                logger.info(
                    "Channel %s (%s): raw=%d -> invalid, skipped",
                    channel.name,
                    channel.conversion_mode.value,
                    raw_value,
                )
                continue

            self._measurement_service.save_measurement(
                self.config.device_serial,
                self._sensor_uid(channel),
                converted,
            )
            values_stored += 1

        logger.info(
            "NT57B08 poll: %d/%d channels stored",
            values_stored,
            len(self.config.channels),
        )
        return True

    def _read_all_channels(self) -> list[int] | None:
        """Read all configured channels in a single Modbus request.

        Returns:
            List of raw register values, or None on failure.
        """
        if self._client is None:
            return None

        reader_name = (
            "read_holding_registers"
            if self.config.function_code == 3
            else "read_input_registers"
        )
        reader = getattr(self._client, reader_name)

        try:
            response = self._read_with_slave(
                reader, self.config.start_register, self.config.channel_count
            )
        except TimeoutError:
            logger.warning("NT57B08 timeout")
            self._disconnect()
            return None
        except ModbusException:
            logger.warning("NT57B08 CRC error")
            return None
        except Exception:
            logger.error("NT57B08 communication failed", exc_info=True)
            self._disconnect()
            return None

        if response is None:
            logger.warning("NT57B08 timeout (no response)")
            return None

        if hasattr(response, "isError") and response.isError():
            message = str(response)
            lower = message.lower()
            if "crc" in lower:
                logger.warning("NT57B08 CRC error")
            elif "timeout" in lower:
                logger.warning("NT57B08 timeout")
            elif "illegal" in lower or "address" in lower:
                logger.warning("NT57B08 invalid register address")
            elif "offline" in lower:
                logger.warning("NT57B08 device offline")
            else:
                logger.error("NT57B08 communication error: %s", message)
            return None

        registers = getattr(response, "registers", None)
        if not registers:
            logger.warning("NT57B08 empty register response")
            return None

        if len(registers) < self.config.channel_count:
            logger.warning(
                "NT57B08 partial response: got %d registers, expected %d",
                len(registers),
                self.config.channel_count,
            )

        return list(registers)

    def _convert_channel(self, raw_value: int, channel: NT57B08Channel) -> float | None:
        """Convert a raw register value for a single channel.

        Applies the configured conversion mode and validates
        against invalid thresholds.

        Returns:
            Converted float value, or None if invalid.
        """
        converted = convert_register_value(raw_value, channel.conversion_mode)
        if converted is None:
            return None

        # Check invalid thresholds
        if channel.invalid_low_threshold is not None and converted < channel.invalid_low_threshold:
            logger.debug(
                "Channel %s: value %s below low threshold %s",
                channel.name,
                converted,
                channel.invalid_low_threshold,
            )
            return None

        if channel.invalid_high_threshold is not None and converted > channel.invalid_high_threshold:
            logger.debug(
                "Channel %s: value %s above high threshold %s",
                channel.name,
                converted,
                channel.invalid_high_threshold,
            )
            return None

        return converted

    def _sensor_uid(self, channel: NT57B08Channel) -> str:
        """Generate a stable, deterministic sensor UID for a channel.

        Format: nt57b08-{device_serial}-ch{channel_number}
        This ensures the same physical channel always maps to the same
        sensor record, even across backend restarts.
        """
        return f"nt57b08-{self.config.device_serial}-ch{channel.channel_number}"

    def _ensure_connected(self) -> bool:
        if self._connected and self._client is not None:
            return True

        try:
            self._client = self._client_factory(self.config)
            self._connected = bool(self._client.connect())
            if self._connected:
                logger.info("NT57B08 connected on %s", self.config.port)
            else:
                logger.error("NT57B08 connection failed on %s", self.config.port)
            return self._connected
        except ModbusException:
            logger.error("NT57B08 connection failed", exc_info=True)
            self._connected = False
            self._client = None
            return False
        except Exception:
            logger.error("NT57B08 connection failed", exc_info=True)
            self._connected = False
            self._client = None
            return False

    def _disconnect(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                logger.warning("NT57B08 disconnect warning")
        if self._connected:
            logger.info("NT57B08 disconnected")
        self._connected = False
        self._client = None

    def _ensure_registration(self) -> None:
        """Register device and sensors via DeviceManager."""
        sensor_payloads = [
            {
                "sensor_id": self._sensor_uid(ch),
                "name": f"{self.config.device_name} {ch.name}",
                "unit": ch.unit or self._unit_for_mode(ch.conversion_mode),
                "type": "NT57B08",
                "rom": self._sensor_uid(ch),
            }
            for ch in self.config.channels
        ]
        self._device_manager.ensure_registered(
            self.config.device_serial,
            {
                "board": self.config.device_name,
                "firmware": "modbus-rtu",
                "build": "nt57b08-driver",
                "chip_id": self.config.port,
            },
            sensor_payloads,
        )
        self._registered = True

    @staticmethod
    def _unit_for_mode(mode: ConversionMode) -> str:
        if mode == ConversionMode.RAW:
            return ""
        if mode == ConversionMode.RESISTANCE_OHMS:
            return "ohm"
        if mode == ConversionMode.TEMPERATURE_DIRECT_SCALED:
            return "C"
        if mode == ConversionMode.NTC_10K_B3950:
            return "C"
        return ""

    def _read_with_slave(
        self,
        reader: Callable[..., object],
        address: int,
        count: int,
    ) -> object:
        try:
            return reader(address=address, count=count, slave=self.config.slave_id)
        except TypeError:
            return reader(address=address, count=count, unit=self.config.slave_id)
