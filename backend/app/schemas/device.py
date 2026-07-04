from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DeviceRead(BaseModel):
	id: int
	name: str
	serial_number: Optional[str]
	location: Optional[str]
	created_at: Optional[datetime]
	last_seen: Optional[datetime]

	class Config:
		orm_mode = True
