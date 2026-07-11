from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AlarmSettingsRead(BaseModel):
    sensor_id: int
    device_id: int
    sensor_name: str
    device_name: str
    device_display_name: Optional[str]
    current_temperature: Optional[float]
    alarm_enabled: bool
    alarm_low: Optional[float]
    alarm_high: Optional[float]
    alarm_activation_delay: int
    alarm_state: str
    alarm_level: Optional[str]
    alarm_no_data_enabled: bool
    alarm_no_data_timeout: int

    class Config:
        orm_mode = True


class AlarmSettingsUpdate(BaseModel):
    sensor_id: Optional[int] = None
    alarm_enabled: bool = True
    alarm_low: Optional[float] = None
    alarm_high: Optional[float] = None
    alarm_activation_delay: int = 0
    alarm_no_data_enabled: bool = False
    alarm_no_data_timeout: int = 15


class ActiveAlarmRead(BaseModel):
    id: int
    sensor_id: int
    device_id: Optional[int]
    alarm_type: str
    threshold: Optional[float]
    temperature: Optional[float]
    state: str
    pending_start: Optional[datetime]
    activated_at: Optional[datetime]
    cleared_at: Optional[datetime]
    created_at: Optional[datetime]
    sensor_name: str
    device_name: str
    device_display_name: Optional[str]

    class Config:
        orm_mode = True


class AlarmResetResponse(BaseModel):
    success: bool
    message: str
    count: int = 0

    class Config:
        orm_mode = True


class AlarmHistoryRead(BaseModel):

    id: int
    sensor_id: int
    device_id: Optional[int]
    alarm_type: str
    threshold: Optional[float]
    temperature: Optional[float]
    state: str
    pending_start: Optional[datetime]
    activated_at: Optional[datetime]
    cleared_at: Optional[datetime]
    created_at: Optional[datetime]
    sensor_name: str
    device_name: str
    device_display_name: Optional[str]

    class Config:
        orm_mode = True
