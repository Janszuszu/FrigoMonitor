from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class Alarm(Base):
    __tablename__ = "alarms"

    id = Column(Integer, primary_key=True, index=True)

    device_id = Column(Integer, ForeignKey("devices.id"), index=True, nullable=True)
    sensor_id = Column(Integer, ForeignKey("sensors.id"), index=True, nullable=True)
    measurement_id = Column(Integer, ForeignKey("measurements.id"), index=True, nullable=True)

    level = Column(String(20), nullable=False)
    message = Column(String(255))
    active = Column(Boolean, default=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    device = relationship("Device")
    sensor = relationship("Sensor")
    measurement = relationship("Measurement")
