from __future__ import annotations

import threading

from app.config import settings
from app.drivers.nt57b08 import NT57B08Driver, load_nt57b08_config
from app.logger import logger


class NT57B08Service:
    """Manages one or more NT57B08 driver instances.

    Each NT57B08 module runs in its own daemon thread.
    Multiple modules are supported via indexed configuration
    (NT57B08_0_*, NT57B08_1_*, etc.).
    """

    def __init__(self) -> None:
        self._drivers: list[NT57B08Driver] = []
        self._threads: list[threading.Thread] = []
        self._lock = threading.RLock()

    def start(self) -> None:
        with self._lock:
            if not settings.NT57B08_ENABLED:
                logger.info("NT57B08 service disabled")
                return

            module_count = settings.NT57B08_MODULE_COUNT
            if module_count < 1:
                module_count = 1

            for index in range(module_count):
                try:
                    config = load_nt57b08_config(index)
                    driver = NT57B08Driver(config)
                    thread = threading.Thread(target=driver.run_forever, daemon=True)
                    self._drivers.append(driver)
                    self._threads.append(thread)
                    thread.start()
                    logger.info(
                        "NT57B08 module %d started: port=%s slave=%d",
                        index + 1,
                        config.port,
                        config.slave_id,
                    )
                except Exception:
                    logger.exception(
                        "Failed to start NT57B08 module %d", index + 1
                    )

    def stop(self) -> None:
        with self._lock:
            drivers = list(self._drivers)
            threads = list(self._threads)
            self._drivers.clear()
            self._threads.clear()

        for driver in drivers:
            try:
                driver.stop()
            except Exception:
                logger.warning("NT57B08 driver stop warning")

        for thread in threads:
            try:
                thread.join(timeout=2.0)
            except Exception:
                pass


nt57b08_service = NT57B08Service()
