from __future__ import annotations

import threading

from app.config import settings
from app.drivers.modbus_rtu import ModbusRTUDriver, load_modbus_rtu_config
from app.logger import logger


class ModbusRTUService:
    def __init__(self) -> None:
        self._driver: ModbusRTUDriver | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return

            if not settings.MODBUS_RTU_ENABLED:
                logger.info("Modbus RTU service disabled")
                return

            config = load_modbus_rtu_config()
            if not config.register_mappings:
                logger.info("Modbus RTU service has no register mappings")
                return

            self._driver = ModbusRTUDriver(config)
            self._thread = threading.Thread(target=self._driver.run_forever, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            driver = self._driver
            thread = self._thread
            self._driver = None
            self._thread = None

        if driver is not None:
            driver.stop()

        if thread is not None:
            thread.join(timeout=2.0)


modbus_rtu_service = ModbusRTUService()
