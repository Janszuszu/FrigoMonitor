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
	created_at: Optional[datetime]
	last_value: Optional[float]
	last_measurement: Optional[datetime]

	class Config:
		orm_mode = True
