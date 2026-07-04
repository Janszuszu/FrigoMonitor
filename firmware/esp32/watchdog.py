"""Watchdog wrapper for MicroPython machine.WDT."""

try:
    import machine
except ImportError:  # pragma: no cover - host syntax checks
    machine = None


class Watchdog:
    """Thin wrapper around machine.WDT."""

    def __init__(self, timeout_ms: int) -> None:
        self._timeout_ms = timeout_ms
        self._wdt = None

    def start(self) -> None:
        """Start watchdog when machine.WDT is available."""
        if machine is None:
            return
        self._wdt = machine.WDT(timeout=self._timeout_ms)

    def feed(self) -> None:
        """Feed watchdog if it has been started."""
        if self._wdt is not None:
            self._wdt.feed()
