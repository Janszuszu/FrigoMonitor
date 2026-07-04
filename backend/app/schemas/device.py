from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class DeviceCreate(BaseModel):
	name: str = Field(min_length=1, max_length=100)
	serial_number: str = Field(min_length=1, max_length=100)
	location: Optional[str] = Field(default=None, max_length=200)


class DeviceUpdate(BaseModel):
	name: Optional[str] = Field(default=None, min_length=1, max_length=100)
	serial_number: Optional[str] = Field(default=None, min_length=1, max_length=100)
	location: Optional[str] = Field(default=None, max_length=200)


class DeviceRead(BaseModel):
	id: int
	name: str
	serial_number: Optional[str]
	location: Optional[str]
	created_at: Optional[datetime]
	last_seen: Optional[datetime]

	class Config:
		orm_mode = True
