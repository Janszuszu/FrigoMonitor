from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class Sensor(Base):
    __tablename__ = "sensors"

    id = Column(Integer, primary_key=True, index=True)

    device_id = Column(Integer, ForeignKey("devices.id"), index=True)

    name = Column(String(100), nullable=False)
    sensor_type = Column(String(50))
    address = Column(String(100))
    correction = Column(Float, default=0.0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_value = Column(Float, nullable=True, index=False)
    last_measurement = Column(DateTime(timezone=True), nullable=True, index=True)

    # Relationships
    device = relationship("Device", back_populates="sensors")
    measurements = relationship("Measurement", back_populates="sensor", cascade="all, delete-orphan")