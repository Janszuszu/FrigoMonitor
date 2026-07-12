from pydantic import BaseModel, Field, field_validator, field_serializer
from typing import Optional
from datetime import datetime, timezone


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
	online: bool = True

	@field_serializer("last_seen", "created_at")
	def serialize_datetime_utc(self, value: Optional[datetime]) -> Optional[str]:
		if value is None:
			return None
		if value.tzinfo is None:
			value = value.replace(tzinfo=timezone.utc)
		return value.isoformat().replace("+00:00", "Z")

	class Config:
		orm_mode = True
