from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class MeasurementRead(BaseModel):
	id: int
	sensor_id: int
	measured_at: Optional[datetime]
	value: float
	unit: Optional[str]
	created_at: Optional[datetime]

	class Config:
		orm_mode = True


class MeasurementHistoryQuery(BaseModel):
	sensor_id: Optional[int] = None
	start: Optional[datetime] = None
	end: Optional[datetime] = None
	skip: int = 0
	limit: int = 100
