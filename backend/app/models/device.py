from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(100), nullable=False)
    serial_number = Column(String(100), unique=True, index=True)
    device_id = Column(String(100), unique=True, index=True, nullable=True)
    location = Column(String(200))
    firmware = Column(String(50), nullable=True)
    build = Column(String(50), nullable=True)
    board = Column(String(100), nullable=True)
    chip_id = Column(String(100), nullable=True)
    mac = Column(String(50), nullable=True)
    ip = Column(String(64), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), nullable=True, index=True)

    # Relationships
    sensors = relationship("Sensor", back_populates="device", cascade="all, delete-orphan")