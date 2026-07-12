from pydantic import BaseModel
from typing import Optional


class DeviceOfflineSettingsRead(BaseModel):
    enabled: bool
    offline_timeout_minutes: int
    severity: str
    notifications_enabled: bool

    class Config:
        orm_mode = True


class DeviceOfflineSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    offline_timeout_minutes: Optional[int] = None
    severity: Optional[str] = None
    notifications_enabled: Optional[bool] = None
