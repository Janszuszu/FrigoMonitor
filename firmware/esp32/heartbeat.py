"""Heartbeat payload builder for firmware skeleton."""

from system_info import SystemInfo
from version import BUILD_DATE, DEVICE_TYPE, VERSION


class HeartbeatBuilder:
    """Build heartbeat payload data without publishing."""

    def __init__(self, device_id: str, timezone: str) -> None:
        self._device_id = device_id
        self._timezone = timezone
        self._system_info = SystemInfo()

    def _uptime_seconds(self) -> int:
        """Return uptime in seconds when available."""
        system_snapshot = self._system_info.snapshot()
        uptime = system_snapshot.get("uptime")
        if uptime is None:
            return 0
        return int(uptime)

    def build(self) -> dict:
        """Build a heartbeat payload dictionary."""
        return {
            "device_id": self._device_id,
            "device_type": DEVICE_TYPE,
            "firmware_version": VERSION,
            "build_date": BUILD_DATE,
            "timezone": self._timezone,
            "uptime_s": self._uptime_seconds(),
        }
