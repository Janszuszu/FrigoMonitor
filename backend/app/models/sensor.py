from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean
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

    alarm_enabled = Column(Boolean, default=True, nullable=False, index=True)
    alarm_low = Column(Float, nullable=True)
    alarm_high = Column(Float, nullable=True)
    alarm_hysteresis = Column(Float, default=0.0, nullable=False)
    alarm_activation_delay = Column(Integer, default=0, nullable=False)
    alarm_state = Column(String(20), default="NORMAL", nullable=False, index=True)
    alarm_level = Column(String(20), nullable=True)
    alarm_pending_since = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_value = Column(Float, nullable=True, index=False)
    last_measurement = Column(DateTime(timezone=True), nullable=True, index=True)

    # Relationships
    device = relationship("Device", back_populates="sensors")
    measurements = relationship("Measurement", back_populates="sensor", cascade="all, delete-orphan")