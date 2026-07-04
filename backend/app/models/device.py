from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func

from app.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(100), nullable=False)
    serial_number = Column(String(100), unique=True)
    location = Column(String(200))

    created_at = Column(DateTime(timezone=True), server_default=func.now())