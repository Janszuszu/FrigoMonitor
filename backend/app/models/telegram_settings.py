from sqlalchemy import Column, Integer, String, Boolean

from app.database import Base


class TelegramSettings(Base):
    __tablename__ = "telegram_settings"

    id = Column(Integer, primary_key=True, index=True)
    enabled = Column(Boolean, default=False, nullable=False)
    bot_token = Column(String(255), default="", nullable=False)
    chat_id = Column(String(100), default="", nullable=False)
