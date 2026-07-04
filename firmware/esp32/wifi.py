"""WiFi manager for ESP32-C3 MicroPython firmware."""

import time

from constants import DEFAULT_WIFI_TIMEOUT, WIFI_POLL_INTERVAL_MS
from exceptions import WiFiConnectionTimeoutError
from logger import error, info, warning

try:
    import network
except ImportError:  # pragma: no cover - host syntax checks
    network = None


class WiFiManager:
    """Manage STA WiFi connectivity using network.WLAN."""

    def __init__(
        self,
        ssid: str,
        password: str,
        timeout_s: int = DEFAULT_WIFI_TIMEOUT,
    ) -> None:
        self._ssid = ssid
        self._password = password
        self.timeout = timeout_s
        self._wlan = None

        if network is not None:
            self._wlan = network.WLAN(network.STA_IF)

    def _require_wlan(self):
        """Return WLAN instance or raise if network module is unavailable."""
        if self._wlan is None:
            raise RuntimeError("network.WLAN is unavailable on this platform")
        return self._wlan

    def _ensure_active(self) -> None:
        """Ensure STA interface is active."""
        wlan = self._require_wlan()
        if not wlan.active():
            wlan.active(True)

    def connect(self) -> None:
        """Connect to WiFi or raise WiFiConnectionTimeoutError on timeout."""
        wlan = self._require_wlan()
        self._ensure_active()

        if wlan.isconnected():
            warning("Reconnect attempt")
            self.disconnect()
            self._ensure_active()

        info("Connecting WiFi...")
        wlan.connect(self._ssid, self._password)

        start = time.ticks_ms()

        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), start) >= self.timeout * 1000:
                error("Connection timeout")
                raise WiFiConnectionTimeoutError(
                    "WiFi connection timed out after %s seconds" % self.timeout
                )
            time.sleep_ms(WIFI_POLL_INTERVAL_MS)

        info("Connected")

    def disconnect(self) -> None:
        """Disconnect WiFi interface."""
        wlan = self._require_wlan()
        wlan.disconnect()
        info("Disconnected")

    def is_connected(self) -> bool:
        """Return current WiFi connection state."""
        wlan = self._require_wlan()
        return bool(wlan.isconnected())

    def ip(self) -> str:
        """Return current IPv4 address or 0.0.0.0 when disconnected."""
        wlan = self._require_wlan()
        if not wlan.isconnected():
            return "0.0.0.0"
        return wlan.ifconfig()[0]

    def rssi(self) -> int:
        """Return signal strength in dBm when available."""
        wlan = self._require_wlan()
        try:
            return int(wlan.status("rssi"))
        except Exception:
            return -1

    def mac(self) -> str:
        """Return MAC address as colon-separated uppercase hex."""
        wlan = self._require_wlan()
        mac_bytes = wlan.config("mac")
        return ":".join("%02X" % byte for byte in mac_bytes)

    def hostname(self) -> str:
        """Return configured hostname when available."""
        wlan = self._require_wlan()
        try:
            return str(wlan.config("hostname"))
        except Exception:
            if network is not None and hasattr(network, "hostname"):
                try:
                    return str(network.hostname())
                except Exception:
                    return ""
            return ""
