from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.logger import logger
from app.models.telegram_settings import TelegramSettings
from app.schemas.telegram import (
    TelegramSettingsRead,
    TelegramSettingsUpdate,
    TelegramTestResult,
)
from app.services.telegram_service import send_test_notification

router = APIRouter(tags=["Telegram"])


def _mask_token(token: str) -> str:
    """Mask the bot token for display, showing only first 4 and last 4 chars."""
    if not token:
        return ""
    if len(token) <= 8:
        return "*" * len(token)
    return token[:4] + "*" * (len(token) - 8) + token[-4:]


def _get_or_create_settings(db: Session) -> TelegramSettings:
    """Get the first telegram settings row, creating one if it doesn't exist."""
    settings = db.query(TelegramSettings).first()
    if settings is None:
        settings = TelegramSettings(enabled=False, bot_token="", chat_id="")
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.get("/telegram/settings", response_model=TelegramSettingsRead)
def get_telegram_settings(db: Session = Depends(get_db)):
    """Get Telegram notification settings.
    
    The bot_token is never returned in full - only a boolean indicating
    whether a token is configured.
    """
    settings = _get_or_create_settings(db)
    return TelegramSettingsRead(
        enabled=settings.enabled,
        chat_id=settings.chat_id,
        bot_token_configured=bool(settings.bot_token),
    )


@router.put("/telegram/settings", response_model=TelegramSettingsRead)
def update_telegram_settings(payload: TelegramSettingsUpdate, db: Session = Depends(get_db)):
    """Update Telegram notification settings.
    
    The bot_token is stored securely in the database.
    It is never returned in full through this API.
    """
    settings = _get_or_create_settings(db)

    settings.enabled = payload.enabled
    settings.chat_id = payload.chat_id.strip() if payload.chat_id else ""

    # Only update the token if a non-empty value is provided
    # This allows updating other fields without re-sending the token
    if payload.bot_token and payload.bot_token.strip():
        settings.bot_token = payload.bot_token.strip()

    db.commit()
    db.refresh(settings)

    logger.info("Telegram settings updated (token configured: %s)", bool(settings.bot_token))

    return TelegramSettingsRead(
        enabled=settings.enabled,
        chat_id=settings.chat_id,
        bot_token_configured=bool(settings.bot_token),
    )


@router.post("/telegram/test", response_model=TelegramTestResult)
def test_telegram(payload: TelegramSettingsUpdate, db: Session = Depends(get_db)):
    """Send a test Telegram notification.
    
    Uses the provided credentials (or saved ones if fields are empty).
    Never logs the full bot token.
    """
    settings = _get_or_create_settings(db)

    # Use provided values, falling back to saved values
    bot_token = payload.bot_token.strip() if payload.bot_token and payload.bot_token.strip() else settings.bot_token
    chat_id = payload.chat_id.strip() if payload.chat_id and payload.chat_id.strip() else settings.chat_id

    if not bot_token:
        raise HTTPException(status_code=400, detail="Bot Token is required")
    if not chat_id:
        raise HTTPException(status_code=400, detail="Chat ID is required")

    # Log only that we're sending, never the actual token
    logger.info("Sending Telegram test notification to chat_id=%s", chat_id)

    success, message = send_test_notification(bot_token, chat_id)

    if success:
        logger.info("Telegram test notification sent successfully")
        return TelegramTestResult(success=True, message=message)
    else:
        logger.error("Telegram test notification failed: %s", message)
        return TelegramTestResult(success=False, message=message)
