from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class SensorCreate(BaseModel):
	name: str = Field(min_length=1, max_length=100)
	sensor_type: Optional[str] = Field(default="temperature", max_length=50)
	address: Optional[str] = Field(default=None, max_length=100)
	correction: float = 0.0


class SensorUpdate(BaseModel):
	name: Optional[str] = Field(default=None, min_length=1, max_length=100)
	sensor_type: Optional[str] = Field(default=None, max_length=50)
	address: Optional[str] = Field(default=None, max_length=100)
	correction: Optional[float] = None

	@field_validator("name")
	@classmethod
	def name_not_blank(cls, v: Optional[str]) -> Optional[str]:
		if v is not None and v.strip() == "":
			raise ValueError("Name must not be blank")
		return v


class SensorAlarmUpdate(BaseModel):
	alarm_enabled: bool = True
	alarm_low: Optional[float] = None
	alarm_high: Optional[float] = None
	alarm_hysteresis: float = Field(default=0.0, ge=0)
	alarm_activation_delay: int = Field(default=0, ge=0)
	alarm_no_data_enabled: bool = False
	alarm_no_data_timeout: int = Field(default=15, ge=1, le=1440)


class SensorRead(BaseModel):
	id: int
	device_id: int
	name: str
	sensor_id: Optional[str]
	sensor_type: Optional[str]
	address: Optional[str]
	rom: Optional[str]
	unit: Optional[str]
	correction: Optional[float]
	alarm_enabled: bool
	alarm_low: Optional[float]
	alarm_high: Optional[float]
	alarm_hysteresis: float
	alarm_activation_delay: int
	alarm_state: str
	alarm_level: Optional[str]
	alarm_pending_since: Optional[datetime]
	alarm_no_data_enabled: bool
	alarm_no_data_timeout: int
	created_at: Optional[datetime]
	last_value: Optional[float]
	last_measurement: Optional[datetime]

	class Config:
		orm_mode = True
