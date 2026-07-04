from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func

from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(50), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    message = Column(String(2000), nullable=False)
    severity = Column(String(20), nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    sent_at = Column(DateTime(timezone=True), nullable=True, index=True)
    status = Column(String(20), nullable=False, default="QUEUED", index=True)
    retry_count = Column(Integer, nullable=False, default=0)
