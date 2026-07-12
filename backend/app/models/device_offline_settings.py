from sqlalchemy import Column, Integer, String, Boolean

from app.database import Base


class DeviceOfflineSettings(Base):
    """Persistent configuration for device offline alarm detection.

    This table stores a single row of global settings for the
    device offline alarm feature.
    """
    __tablename__ = "device_offline_settings"

    id = Column(Integer, primary_key=True, index=True)
    enabled = Column(Boolean, default=True, nullable=False)
    offline_timeout_minutes = Column(Integer, default=5, nullable=False)
    severity = Column(String(20), default="CRITICAL", nullable=False)
    notifications_enabled = Column(Boolean, default=True, nullable=False)
