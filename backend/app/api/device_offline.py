"""API endpoints for device offline alarm configuration."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.logger import logger
from app.models.device_offline_settings import DeviceOfflineSettings

router = APIRouter(tags=["Device Offline Alarm"])


class DeviceOfflineAlarmSettingsRead(BaseModel):
    enabled: bool
    offline_timeout_minutes: int = Field(ge=1)
    severity: str
    notifications_enabled: bool

    class Config:
        orm_mode = True


class DeviceOfflineAlarmSettingsUpdate(BaseModel):
    enabled: bool = True
    offline_timeout_minutes: int = Field(default=5, ge=1)
    severity: str = Field(default="CRITICAL")
    notifications_enabled: bool = True


VALID_SEVERITIES = {"INFO", "WARNING", "CRITICAL"}


def _get_or_create_settings(db: Session) -> DeviceOfflineSettings:
    """Get the device offline settings row, creating one if it doesn't exist."""
    settings = db.query(DeviceOfflineSettings).first()
    if settings is None:
        settings = DeviceOfflineSettings(
            enabled=True,
            offline_timeout_minutes=5,
            severity="CRITICAL",
            notifications_enabled=True,
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.get(
    "/settings/device-offline-alarm",
    response_model=DeviceOfflineAlarmSettingsRead,
)
def get_device_offline_settings(db: Session = Depends(get_db)):
    """Get the current device offline alarm configuration."""
    settings = _get_or_create_settings(db)
    return DeviceOfflineAlarmSettingsRead(
        enabled=settings.enabled,
        offline_timeout_minutes=settings.offline_timeout_minutes,
        severity=settings.severity,
        notifications_enabled=settings.notifications_enabled,
    )


@router.put(
    "/settings/device-offline-alarm",
    response_model=DeviceOfflineAlarmSettingsRead,
)
def update_device_offline_settings(
    payload: DeviceOfflineAlarmSettingsUpdate,
    db: Session = Depends(get_db),
):
    """Update the device offline alarm configuration.

    Validates:
    - offline_timeout_minutes must be >= 1
    - severity must be one of: INFO, WARNING, CRITICAL
    """
    severity_upper = payload.severity.upper().strip()
    if severity_upper not in VALID_SEVERITIES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid severity '{payload.severity}'. Must be one of: {', '.join(sorted(VALID_SEVERITIES))}",
        )

    if payload.offline_timeout_minutes < 1:
        raise HTTPException(
            status_code=422,
            detail="offline_timeout_minutes must be >= 1",
        )

    settings = _get_or_create_settings(db)

    settings.enabled = payload.enabled
    settings.offline_timeout_minutes = payload.offline_timeout_minutes
    settings.severity = severity_upper
    settings.notifications_enabled = payload.notifications_enabled

    db.commit()
    db.refresh(settings)

    logger.info(
        "Device offline alarm settings updated: enabled=%s, timeout=%smin, "
        "severity=%s, notifications=%s",
        settings.enabled,
        settings.offline_timeout_minutes,
        settings.severity,
        settings.notifications_enabled,
    )

    return DeviceOfflineAlarmSettingsRead(
        enabled=settings.enabled,
        offline_timeout_minutes=settings.offline_timeout_minutes,
        severity=settings.severity,
        notifications_enabled=settings.notifications_enabled,
    )
