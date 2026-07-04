from sqlalchemy import Column, Integer, Float, String, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class Measurement(Base):
    __tablename__ = "measurements"

    id = Column(Integer, primary_key=True, index=True)

    sensor_id = Column(Integer, ForeignKey("sensors.id"), index=True, nullable=False)

    # measured timestamp (from sensor) and stored created_at
    measured_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    value = Column(Float, nullable=False)
    unit = Column(String(20))

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    sensor = relationship("Sensor", back_populates="measurements")
