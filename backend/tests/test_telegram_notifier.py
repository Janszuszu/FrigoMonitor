import sys
import os
from datetime import datetime, UTC
from types import SimpleNamespace
from urllib import error
from unittest.mock import Mock

sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

import pytest

from app.config import settings
from app.models.notification import Notification
from app.services.notification_service import NotificationService, NotificationStatus
from app.drivers.telegram_notifier import TelegramNotifier


@pytest.fixture(autouse=True)
def reset_telegram_settings():
    original = SimpleNamespace(
        enabled=settings.TELEGRAM_ENABLED,
        token=settings.TELEGRAM_BOT_TOKEN,
        chat_id=settings.TELEGRAM_CHAT_ID,
    )
    yield
    settings.TELEGRAM_ENABLED = original.enabled
    settings.TELEGRAM_BOT_TOKEN = original.token
    settings.TELEGRAM_CHAT_ID = original.chat_id


def build_notification(severity: str = "CRITICAL") -> Notification:
    notification = Notification(
        type="alarm.active",
        title="Freezer alert",
        message="Temperature is above threshold",
        severity=severity,
    )
    notification.created_at = datetime(2026, 7, 4, 10, 30, tzinfo=UTC)
    notification.device = "Device-12"
    notification.sensor = "Sensor-A"
    return notification


def test_disabled_mode(caplog):
    settings.TELEGRAM_ENABLED = False
    settings.TELEGRAM_BOT_TOKEN = "token"
    settings.TELEGRAM_CHAT_ID = "chat"
    notifier = TelegramNotifier()

    with caplog.at_level("WARNING"):
        result = notifier.send(build_notification())

    assert result is False
    assert any("Telegram disabled" in record.message for record in caplog.records)


def test_formatting():
    notifier = TelegramNotifier()
    notification = build_notification("WARNING")

    text = notifier.format_notification(notification)

    assert "⚠️ WARNING" in text
    assert "Timestamp: 2026-07-04 10:30:00 UTC" in text
    assert "Device: Device-12" in text
    assert "Sensor: Sensor-A" in text
    assert "Message: Temperature is above threshold" in text


def test_successful_send_mock(monkeypatch, caplog):
    settings.TELEGRAM_ENABLED = True
    settings.TELEGRAM_BOT_TOKEN = "bot-token"
    settings.TELEGRAM_CHAT_ID = "chat-id"
    notifier = TelegramNotifier()
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.status = 200
    response.read = Mock(return_value=b"{}")
    urlopen = Mock(return_value=response)
    monkeypatch.setattr("app.drivers.telegram_notifier.request.urlopen", urlopen)

    with caplog.at_level("INFO"):
        result = notifier.send(build_notification())

    assert result is True
    urlopen.assert_called_once()
    assert any("Telegram sent" in record.message for record in caplog.records)


def test_failed_send_mock(monkeypatch, caplog):
    settings.TELEGRAM_ENABLED = True
    settings.TELEGRAM_BOT_TOKEN = "bot-token"
    settings.TELEGRAM_CHAT_ID = "chat-id"
    notifier = TelegramNotifier()
    monkeypatch.setattr("app.drivers.telegram_notifier.request.urlopen", Mock(side_effect=error.URLError("boom")))

    with caplog.at_level("ERROR"):
        result = notifier.send(build_notification())

    assert result is False
    assert any("Telegram API error" in record.message for record in caplog.records)


def test_retry_integration(monkeypatch, caplog):
    settings.TELEGRAM_ENABLED = True
    settings.TELEGRAM_BOT_TOKEN = "bot-token"
    settings.TELEGRAM_CHAT_ID = "chat-id"
    service = NotificationService(max_retries=3)

    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.status = 200
    response.read = Mock(return_value=b"{}")
    urlopen = Mock(side_effect=[error.URLError("boom"), response])
    monkeypatch.setattr("app.drivers.telegram_notifier.request.urlopen", urlopen)

    notification = build_notification()

    with caplog.at_level("WARNING"):
        first = service.send(notification)
        retried = service.retry_failed()

    assert first is False
    assert retried == 1
    assert notification.status == NotificationStatus.SENT
    assert notification.retry_count == 1
    assert any("Retry notification" in record.message for record in caplog.records)
