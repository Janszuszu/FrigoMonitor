from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class DeviceCreate(BaseModel):
	name: str = Field(min_length=1, max_length=100)
	serial_number: str = Field(min_length=1, max_length=100)
	location: Optional[str] = Field(default=None, max_length=200)


class DeviceUpdate(BaseModel):
	name: Optional[str] = Field(default=None, min_length=1, max_length=100)
	display_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
	serial_number: Optional[str] = Field(default=None, min_length=1, max_length=100)
	location: Optional[str] = Field(default=None, max_length=200)

	@field_validator("display_name")
	@classmethod
	def display_name_not_blank(cls, v: Optional[str]) -> Optional[str]:
		if v is not None and v.strip() == "":
			raise ValueError("Display name must not be blank")
		return v


class DeviceRead(BaseModel):
	id: int
	name: str
	display_name: Optional[str]
	serial_number: Optional[str]
	location: Optional[str]
	created_at: Optional[datetime]
	last_seen: Optional[datetime]

	class Config:
		orm_mode = True
