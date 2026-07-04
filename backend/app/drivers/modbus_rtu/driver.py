from __future__ import annotations

import time
from typing import Callable, Protocol

from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException

from app.drivers.modbus_rtu.models import ModbusRTUConfig, RegisterMapping
from app.drivers.modbus_rtu.parser import parse_register_value
from app.logger import logger
from app.services.device_manager import DeviceManager, device_manager
from app.services.measurement_service import MeasurementService, measurement_service


class _ModbusClient(Protocol):
    def connect(self) -> bool: ...

    def close(self) -> None: ...

    def read_holding_registers(self, *args, **kwargs): ...

    def read_input_registers(self, *args, **kwargs): ...


class ModbusRTUDriver:
    def __init__(
        self,
        config: ModbusRTUConfig,
        *,
        measurement_service_obj: MeasurementService = measurement_service,
        device_manager_obj: DeviceManager = device_manager,
        client_factory: Callable[[ModbusRTUConfig], _ModbusClient] | None = None,
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
    def _default_client_factory(config: ModbusRTUConfig) -> _ModbusClient:
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
        logger.info("Driver started")

    def stop(self) -> None:
        self._running = False
        self._disconnect()

    def run_forever(self) -> None:
        self.start()
        while self._running:
            ok = self.poll_once()
            delay = self.config.poll_interval_seconds if ok else self.config.retry_interval_seconds
            self._sleep(delay)

    def poll_once(self) -> bool:
        if not self._ensure_connected():
            return False

        if not self._registered:
            self._ensure_registration()

        values_written = 0
        for mapping in self.config.register_mappings:
            value = self._read_mapping(mapping)
            if value is None:
                continue

            self._measurement_service.save_measurement(
                self.config.device_serial,
                mapping.sensor_uid,
                value,
            )
            values_written += 1

        logger.info("Registers read: %s", values_written)
        return True

    def _ensure_connected(self) -> bool:
        if self._connected and self._client is not None:
            return True

        try:
            self._client = self._client_factory(self.config)
            self._connected = bool(self._client.connect())
            if self._connected:
                logger.info("Connected")
            else:
                logger.error("Communication failed")
            return self._connected
        except ModbusException:
            logger.error("Communication failed", exc_info=True)
            self._connected = False
            self._client = None
            return False
        except Exception:
            logger.error("Communication failed", exc_info=True)
            self._connected = False
            self._client = None
            return False

    def _disconnect(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                logger.warning("Disconnected")
        if self._connected:
            logger.info("Disconnected")
        self._connected = False
        self._client = None

    def _ensure_registration(self) -> None:
        sensor_payloads = [
            {
                "sensor_id": mapping.sensor_uid,
                "name": mapping.name,
                "unit": mapping.unit,
                "type": "MODBUS_REGISTER",
                "rom": mapping.sensor_uid,
            }
            for mapping in self.config.register_mappings
        ]
        self._device_manager.ensure_registered(
            self.config.device_serial,
            {
                "board": self.config.device_name,
                "firmware": "modbus-rtu",
                "build": "driver",
                "chip_id": self.config.port,
            },
            sensor_payloads,
        )
        self._registered = True

    def _read_mapping(self, mapping: RegisterMapping) -> float | None:
        if self._client is None:
            return None

        reader_name = "read_holding_registers" if mapping.register_type == "holding" else "read_input_registers"
        reader = getattr(self._client, reader_name)

        try:
            response = self._read_with_slave(reader, mapping.address)
        except TimeoutError:
            logger.warning("Timeout")
            self._disconnect()
            return None
        except ModbusException:
            logger.warning("CRC error")
            return None
        except Exception:
            logger.error("Communication failed", exc_info=True)
            self._disconnect()
            return None

        if response is None:
            logger.warning("Timeout")
            return None

        if hasattr(response, "isError") and response.isError():
            message = str(response)
            lower = message.lower()
            if "crc" in lower:
                logger.warning("CRC error")
            elif "timeout" in lower:
                logger.warning("Timeout")
            elif "illegal" in lower or "address" in lower:
                logger.warning("Invalid register")
            elif "offline" in lower:
                logger.warning("Device offline")
            else:
                logger.error("Communication failed")
            return None

        registers = getattr(response, "registers", None)
        if not registers:
            logger.warning("Invalid register")
            return None

        return parse_register_value(registers, mapping)

    def _read_with_slave(self, reader: Callable[..., object], address: int) -> object:
        try:
            return reader(address=address, count=1, slave=self.config.slave_id)
        except TypeError:
            return reader(address=address, count=1, unit=self.config.slave_id)
