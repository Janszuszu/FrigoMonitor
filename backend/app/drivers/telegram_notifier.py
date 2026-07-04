from __future__ import annotations

from datetime import UTC, datetime
from urllib import error, parse, request

from app.config import settings
from app.logger import logger
from app.models.notification import Notification
from app.services.notification_service import Notifier

SEVERITY_ICONS = {
    "INFO": "ℹ️",
    "WARNING": "⚠️",
    "CRITICAL": "🚨",
}


class TelegramNotifier(Notifier):
    def __init__(self, timeout_seconds: int = 10) -> None:
        self.timeout_seconds = timeout_seconds

    def send(self, notification: Notification) -> bool:
        if not settings.TELEGRAM_ENABLED:
            logger.warning("Telegram disabled")
            return False

        token = settings.TELEGRAM_BOT_TOKEN.strip()
        chat_id = settings.TELEGRAM_CHAT_ID.strip()
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
