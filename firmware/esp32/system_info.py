"""Hardware and system information access for ESP32-C3 firmware."""

try:
    import machine
except ImportError:  # pragma: no cover - host syntax checks
    machine = None

try:
    import network
except ImportError:  # pragma: no cover - host syntax checks
    network = None

import gc
import os
import time

try:
    import ubinascii
except ImportError:  # pragma: no cover - host syntax checks
    ubinascii = None


class SystemInfo:
    """Provide read-only hardware/system data for firmware modules."""

    def _get_wlan(self):
        """Return STA WLAN instance when available."""
        if network is None:
            return None
        try:
            wlan = network.WLAN(network.STA_IF)
            if not wlan.active():
                wlan.active(True)
            return wlan
        except Exception:
            return None

    def get_chip_id(self):
        """Return chip unique ID as uppercase hex string."""
        if machine is None or ubinascii is None:
            return None
        try:
            unique_id = machine.unique_id()
            return ubinascii.hexlify(unique_id).decode().upper()
        except Exception:
            return None

    def get_mac(self):
        """Return MAC address as colon-separated uppercase hex."""
        wlan = self._get_wlan()
        if wlan is None:
            return None
        try:
            mac_bytes = wlan.config("mac")
            return ":".join("%02X" % byte for byte in mac_bytes)
        except Exception:
            return None

    def get_hostname(self):
        """Return configured hostname."""
        wlan = self._get_wlan()
        if wlan is not None:
            try:
                return str(wlan.config("hostname"))
            except Exception:
                pass

        if network is not None and hasattr(network, "hostname"):
            try:
                return str(network.hostname())
            except Exception:
                return None
        return None

    def get_ip(self):
        """Return current station IPv4 address."""
        wlan = self._get_wlan()
        if wlan is None:
            return None
        try:
            if not wlan.isconnected():
                return None
            return wlan.ifconfig()[0]
        except Exception:
            return None

    def get_rssi(self):
        """Return RSSI in dBm."""
        wlan = self._get_wlan()
        if wlan is None:
            return None
        try:
            if not wlan.isconnected():
                return None
            return int(wlan.status("rssi"))
        except Exception:
            return None

    def get_uptime(self):
        """Return uptime in seconds based on ticks_ms."""
        ticks_fn = getattr(time, "ticks_ms", None)
        if ticks_fn is None:
            return None
        try:
            return int(ticks_fn() // 1000)
        except Exception:
            return None

    def get_free_memory(self):
        """Return free heap memory in bytes."""
        try:
            return gc.mem_free()
        except Exception:
            return None

    def get_reset_cause(self):
        """Return reset cause as a human-readable string."""
        if machine is None:
            return None
        try:
            cause = machine.reset_cause()
        except Exception:
            return None

        mapping = {
            getattr(machine, "PWRON_RESET", -1): "power_on",
            getattr(machine, "HARD_RESET", -1): "hard_reset",
            getattr(machine, "WDT_RESET", -1): "watchdog_reset",
            getattr(machine, "DEEPSLEEP_RESET", -1): "deepsleep_reset",
            getattr(machine, "SOFT_RESET", -1): "soft_reset",
            getattr(machine, "BROWN_OUT_RESET", -1): "brownout_reset",
        }
        return mapping.get(cause, "unknown")

    def get_flash_size(self):
        """Return flash size in bytes."""
        if machine is not None and hasattr(machine, "flash_size"):
            try:
                return int(machine.flash_size())
            except Exception:
                pass

        try:
            stat = os.statvfs("/")
            block_size = stat[1]
            total_blocks = stat[2]
            return int(block_size * total_blocks)
        except Exception:
            return None

    def get_cpu_freq(self):
        """Return CPU frequency in MHz."""
        if machine is None:
            return None
        try:
            frequency = machine.freq()
            if isinstance(frequency, tuple):
                frequency = frequency[0]
            if frequency is None:
                return None
            if frequency >= 1000000:
                return int(frequency // 1000000)
            return int(frequency)
        except Exception:
            return None

    def get_board_name(self):
        """Return board name from runtime when available."""
        try:
            return str(os.uname().machine)
        except Exception:
            return None

    def snapshot(self):
        """Return a full system snapshot using existing getter methods."""
        return {
            "chip_id": self.get_chip_id(),
            "mac": self.get_mac(),
            "hostname": self.get_hostname(),
            "ip": self.get_ip(),
            "rssi": self.get_rssi(),
            "uptime": self.get_uptime(),
            "free_memory": self.get_free_memory(),
            "reset_cause": self.get_reset_cause(),
            "flash_size": self.get_flash_size(),
            "cpu_freq": self.get_cpu_freq(),
        }
