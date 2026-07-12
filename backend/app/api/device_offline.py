from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.device_offline_settings import DeviceOfflineSettings
from app.schemas.device_offline import DeviceOfflineSettingsRead, DeviceOfflineSettingsUpdate

router = APIRouter(tags=["Device Offline"])


def _get_or_create_settings(db: Session) -> DeviceOfflineSettings:
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


@router.get("/device-offline/settings", response_model=DeviceOfflineSettingsRead)
def get_device_offline_settings(db: Session = Depends(get_db)):
    return _get_or_create_settings(db)


@router.put("/device-offline/settings", response_model=DeviceOfflineSettingsRead)
def update_device_offline_settings(payload: DeviceOfflineSettingsUpdate, db: Session = Depends(get_db)):
    settings = _get_or_create_settings(db)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(settings, field, value)
    db.commit()
    db.refresh(settings)
    return settings
