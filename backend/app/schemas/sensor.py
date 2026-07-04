from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SensorRead(BaseModel):
	id: int
	device_id: int
	name: str
	sensor_type: Optional[str]
	address: Optional[str]
	correction: Optional[float]
	alarm_enabled: bool
	alarm_low: Optional[float]
	alarm_high: Optional[float]
	alarm_state: str
	alarm_level: Optional[str]
	alarm_pending_since: Optional[datetime]
	created_at: Optional[datetime]
	last_value: Optional[float]
	last_measurement: Optional[datetime]

	class Config:
		orm_mode = True
