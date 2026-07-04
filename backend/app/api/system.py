from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.config import settings

router = APIRouter(tags=["System"])


@router.get('/system/health')
def health():
    return {"status": "ok", "app": settings.APP_NAME}


class NetworkSettingsRead(BaseModel):
    mqtt_host: str
    mqtt_port: int
    mqtt_user: str
    mqtt_password_configured: bool
    frontend_origins: list[str]


class NetworkSettingsUpdate(BaseModel):
    mqtt_host: str = Field(min_length=1, max_length=255)
    mqtt_port: int = Field(ge=1, le=65535)
    mqtt_user: str = ""
    mqtt_password: str = ""
    frontend_origins: list[str] = Field(default_factory=list)


@router.get('/system/network', response_model=NetworkSettingsRead)
def get_network_settings():
    return NetworkSettingsRead(
        mqtt_host=settings.MQTT_HOST,
        mqtt_port=settings.MQTT_PORT,
        mqtt_user=settings.MQTT_USER,
        mqtt_password_configured=bool(settings.MQTT_PASSWORD),
        frontend_origins=settings.frontend_origins,
    )


@router.put('/system/network', response_model=NetworkSettingsRead)
def update_network_settings(payload: NetworkSettingsUpdate):
    settings.MQTT_HOST = payload.mqtt_host
    settings.MQTT_PORT = payload.mqtt_port
    settings.MQTT_USER = payload.mqtt_user
    settings.MQTT_PASSWORD = payload.mqtt_password
    settings.FRONTEND_ORIGINS = ",".join(payload.frontend_origins)

    return get_network_settings()
