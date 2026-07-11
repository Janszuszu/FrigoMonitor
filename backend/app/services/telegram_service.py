from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional
from urllib import error, parse, request

from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.logger import logger
from app.models.telegram_settings import TelegramSettings
from app.models.sensor import Sensor
from app.models.device import Device
# Track which alarm events have already sent a Telegram notification
# to prevent duplicate notifications while an alarm remains active.
# Key: "sensor_id:alarm_type" -> True when notification was sent
_sent_notifications: dict[str, bool] = {}


def _notification_key(sensor_id: int, alarm_type: str) -> str:
    return f"{sensor_id}:{alarm_type}"


def _load_settings_from_db(session) -> Optional[TelegramSettings]:
    """Load the first row of telegram settings from DB."""
    settings = session.query(TelegramSettings).first()
    return settings


def _get_settings() -> tuple[bool, str, str]:
    """Get telegram settings from database.
    
    Returns (enabled, bot_token, chat_id).
    Falls back to env vars if no DB row exists.
    """
    try:
        with SessionLocal() as session:
            row = _load_settings_from_db(session)
            if row is not None:
                return row.enabled, row.bot_token or "", row.chat_id or ""
    except SQLAlchemyError:
        logger.exception("Failed to load Telegram settings from DB")

    # Fallback to env vars
    from app.config import settings as app_settings
    return (
        app_settings.TELEGRAM_ENABLED,
        app_settings.TELEGRAM_BOT_TOKEN,
        app_settings.TELEGRAM_CHAT_ID,
    )


def send_telegram_message(text: str, bot_token: str, chat_id: str, timeout_seconds: int = 10) -> tuple[bool, str]:
    """Send a message via Telegram Bot API.
    
    Returns (success, error_message).
    """
    if not bot_token or not chat_id:
        return False, "Bot Token and Chat ID are required"

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = parse.urlencode({
        "chat_id": chat_id.strip(),
        "text": text,
        "parse_mode": "HTML",
    }).encode("utf-8")
    req = request.Request(url, data=data, method="POST")

    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            if getattr(response, "status", 200) >= 400:
                body = response.read().decode("utf-8", errors="replace")
                logger.error("Telegram API returned error status %s: %s", response.status, body)
                return False, f"Telegram API returned status {response.status}"
        return True, "Telegram test notification sent successfully."
    except error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        logger.error("Telegram HTTP error: %s", body)
        if e.code == 401:
            return False, "Invalid Bot Token. Please check your token."
        elif e.code == 400:
            return False, f"Bad request: {body}"
        return False, f"Telegram API HTTP error {e.code}"
    except error.URLError as e:
        logger.error("Telegram URL/network error: %s", e.reason)
        return False, f"Network error: {e.reason}. Check your internet connection."
    except TimeoutError:
        logger.error("Telegram API timeout")
        return False, "Telegram API timed out. Please try again."
    except Exception as e:
        logger.exception("Telegram API error")
        return False, f"Unexpected error: {str(e)}"


def send_test_notification(bot_token: str, chat_id: str) -> tuple[bool, str]:
    """Send a test notification to verify Telegram configuration."""
    now = datetime.now(UTC).astimezone()
    timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")
    text = (
        "FrigoMonitor test notification\n\n"
        f"System: FrigoMonitor\n"
        f"Status: Telegram notifications are working correctly.\n"
        f"Time: {timestamp_str}"
    )
    return send_telegram_message(text, bot_token, chat_id)


def send_alarm_notification(
    sensor: Sensor,
    device: Optional[Device],
    alarm_type: str,
    current_value: Optional[float],
    threshold: Optional[float],
    activated_at: Optional[datetime],
) -> None:
    """Send a Telegram notification for an alarm activation.
    
    Only sends when the alarm transitions from non-active to ACTIVE.
    Prevents duplicate notifications while the alarm remains active.
    """
    # Lazy import to avoid circular dependency
    from app.services.alarm_service import AlarmState

    enabled, bot_token, chat_id = _get_settings()
    if not enabled or not bot_token or not chat_id:
        return

    # Determine the alarm type key for deduplication
    if alarm_type == AlarmState.NO_DATA:
        dedup_key = _notification_key(sensor.id, AlarmState.NO_DATA)
    elif alarm_type == AlarmState.ALARM_HIGH:
        dedup_key = _notification_key(sensor.id, AlarmState.ALARM_HIGH)
    elif alarm_type == AlarmState.ALARM_LOW:
        dedup_key = _notification_key(sensor.id, AlarmState.ALARM_LOW)
    else:
        return  # Only send for active alarms, not pending

    # Check if we already sent a notification for this active alarm
    if _sent_notifications.get(dedup_key):
        logger.debug("Telegram notification already sent for %s, skipping", dedup_key)
        return

    device_name = device.display_name or device.name if device else "Unknown"
    sensor_name = sensor.name

    if activated_at and activated_at.tzinfo is None:
        activated_at = activated_at.replace(tzinfo=UTC)
    timestamp_str = activated_at.astimezone().strftime("%d.%m.%Y %H:%M:%S") if activated_at else "N/A"

    if alarm_type == AlarmState.NO_DATA:
        timeout_minutes = sensor.alarm_no_data_timeout or 15
        text = (
            f"ALARM: NO DATA\n\n"
            f"Device: {device_name}\n"
            f"Sensor: {sensor_name}\n"
            f"No measurements received for: {timeout_minutes} minutes\n"
            f"Alarm active since: {timestamp_str}"
        )
    elif alarm_type == AlarmState.ALARM_HIGH:
        current_str = f"{current_value:.1f}°C" if current_value is not None else "N/A"
        threshold_str = f"{threshold:.1f}°C" if threshold is not None else "N/A"
        text = (
            f"ALARM: HIGH TEMPERATURE\n\n"
            f"Device: {device_name}\n"
            f"Sensor: {sensor_name}\n"
            f"Current temperature: {current_str}\n"
            f"Maximum threshold: {threshold_str}\n"
            f"Alarm active since: {timestamp_str}"
        )
    elif alarm_type == AlarmState.ALARM_LOW:
        current_str = f"{current_value:.1f}°C" if current_value is not None else "N/A"
        threshold_str = f"{threshold:.1f}°C" if threshold is not None else "N/A"
        text = (
            f"ALARM: LOW TEMPERATURE\n\n"
            f"Device: {device_name}\n"
            f"Sensor: {sensor_name}\n"
            f"Current temperature: {current_str}\n"
            f"Minimum threshold: {threshold_str}\n"
            f"Alarm active since: {timestamp_str}"
        )
    else:
        return

    success, err_msg = send_telegram_message(text, bot_token, chat_id)
    if success:
        _sent_notifications[dedup_key] = True
        logger.info("Telegram alarm notification sent for %s", dedup_key)
    else:
        logger.error("Failed to send Telegram alarm notification for %s: %s", dedup_key, err_msg)


def clear_notification_tracking(sensor_id: int, alarm_type: str) -> None:
    """Clear the notification tracking for a resolved alarm.
    
    This allows a new notification to be sent if the alarm becomes active again.
    """
    # Lazy import to avoid circular dependency
    from app.services.alarm_service import AlarmState

    if alarm_type in (AlarmState.NO_DATA, "NO_DATA"):
        keys_to_clear = [
            _notification_key(sensor_id, AlarmState.NO_DATA),
        ]
    elif alarm_type in (AlarmState.ALARM_HIGH, AlarmState.ALARM_LOW):
        keys_to_clear = [
            _notification_key(sensor_id, AlarmState.ALARM_HIGH),
            _notification_key(sensor_id, AlarmState.ALARM_LOW),
        ]
    else:
        keys_to_clear = [
            _notification_key(sensor_id, AlarmState.ALARM_HIGH),
            _notification_key(sensor_id, AlarmState.ALARM_LOW),
            _notification_key(sensor_id, AlarmState.NO_DATA),
        ]

    for key in keys_to_clear:
        _sent_notifications.pop(key, None)
    logger.debug("Cleared Telegram notification tracking for sensor %s", sensor_id)


def clear_all_notification_tracking() -> None:
    """Clear all notification tracking (e.g., on bulk reset)."""
    _sent_notifications.clear()
    logger.debug("Cleared all Telegram notification tracking")
