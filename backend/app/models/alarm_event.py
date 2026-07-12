from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class AlarmEvent(Base):
    __tablename__ = "alarm_events"

    id = Column(Integer, primary_key=True, index=True)

    sensor_id = Column(Integer, ForeignKey("sensors.id"), nullable=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True, index=True)

    alarm_type = Column(String(20), nullable=False)
    threshold = Column(Float, nullable=True)
    temperature = Column(Float, nullable=True)
    state = Column(String(20), nullable=False)

    pending_start = Column(DateTime(timezone=True), nullable=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    cleared_at = Column(DateTime(timezone=True), nullable=True)
    telegram_notification_sent_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    sensor = relationship("Sensor")
    device = relationship("Device")
