from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Sensor(Base):
    __tablename__ = "sensors"

    id = Column(Integer, primary_key=True, index=True)

    device_id = Column(Integer, ForeignKey("devices.id"))

    name = Column(String(100))
    sensor_type = Column(String(50))
    address = Column(String(100))
    correction = Column(Float, default=0.0)

    device = relationship("Device")