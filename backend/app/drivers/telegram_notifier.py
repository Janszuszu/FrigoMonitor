from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional
from urllib import error, parse, request

from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.logger import logger
from app.models.notification import Notification
from app.models.telegram_settings import TelegramSettings
from app.services.notification_service import Notifier

SEVERITY_ICONS = {
    "INFO": "ℹ️",
    "WARNING": "⚠️",
    "CRITICAL": "🚨",
}


def _load_telegram_settings() -> tuple[bool, str, str]:
    """Load Telegram settings from database, falling back to env vars."""
    try:
        with SessionLocal() as session:
            row = session.query(TelegramSettings).first()
            if row is not None:
                return row.enabled, row.bot_token or "", row.chat_id or ""
    except SQLAlchemyError:
        logger.exception("Failed to load Telegram settings from DB")

    from app.config import settings as app_settings
    return (
        app_settings.TELEGRAM_ENABLED,
        app_settings.TELEGRAM_BOT_TOKEN,
        app_settings.TELEGRAM_CHAT_ID,
    )


class TelegramNotifier(Notifier):
    def __init__(self, timeout_seconds: int = 10) -> None:
        self.timeout_seconds = timeout_seconds

    def send(self, notification: Notification) -> bool:
        enabled, token, chat_id = _load_telegram_settings()
        if not enabled:
            logger.warning("Telegram disabled")
            return False

        token = token.strip()
        chat_id = chat_id.strip()
        if not token or not chat_id:
            logger.error("Telegram API error")
            return False

        payload = self._build_payload(notification)
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = parse.urlencode({"chat_id": chat_id, "text": payload}).encode("utf-8")
        req = request.Request(url, data=data, method="POST")

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                if getattr(response, "status", 200) >= 400:
                    logger.error("Telegram API error")
                    return False
        except error.HTTPError:
            logger.error("Telegram API error")
            return False
        except error.URLError:
            logger.error("Telegram API error")
            return False
        except Exception:
            logger.exception("Telegram API error")
            return False

        logger.info("Telegram sent")
        return True

    def format_notification(self, notification: Notification) -> str:
        severity = (notification.severity or "INFO").upper()
        icon = SEVERITY_ICONS.get(severity, SEVERITY_ICONS["INFO"])
        timestamp = self._get_timestamp(notification)
        device = getattr(notification, "device", None) or getattr(notification, "device_id", None) or "-"
        sensor = getattr(notification, "sensor", None) or getattr(notification, "sensor_id", None) or "-"
        return (
            f"{icon} {severity}\n"
            f"Timestamp: {timestamp}\n"
            f"Device: {device}\n"
            f"Sensor: {sensor}\n"
            f"Message: {notification.message}"
        )

    def _build_payload(self, notification: Notification) -> str:
        title = notification.title.strip() if notification.title else "Notification"
        return f"{title}\n{self.format_notification(notification)}"

    def _get_timestamp(self, notification: Notification) -> str:
        ts = notification.created_at or notification.sent_at or datetime.now(UTC)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return ts.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


telegram_notifier = TelegramNotifier()
