from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    APP_NAME: str = "FrigoMonitor"
    APP_VERSION: str = "0.1.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DATABASE_URL: str = "sqlite:///frigomonitor.db"
    MQTT_HOST: str = "localhost"
    MQTT_PORT: int = 1883
    MQTT_USER: str = ""
    MQTT_PASSWORD: str = ""
    MODBUS_RTU_ENABLED: bool = False
    MODBUS_RTU_PORT: str = "COM1"
    MODBUS_RTU_BAUDRATE: int = 9600
    MODBUS_RTU_PARITY: str = "N"
    MODBUS_RTU_STOPBITS: int = 1
    MODBUS_RTU_BYTESIZE: int = 8
    MODBUS_RTU_SLAVE_ID: int = 1
    MODBUS_RTU_TIMEOUT: float = 1.0
    MODBUS_RTU_POLL_INTERVAL: float = 5.0
    MODBUS_RTU_RETRY_INTERVAL: float = 2.0
    MODBUS_RTU_DEVICE_SERIAL: str = "MODBUS-RTU-1"
    MODBUS_RTU_DEVICE_NAME: str = "Modbus RTU Device"
    MODBUS_RTU_REGISTER_MAP: str = "[]"
    LOG_LEVEL: str = "INFO"
    TELEGRAM_ENABLED: bool = False
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    FRONTEND_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Measurement limits (defaults in degrees Celsius)
    MEASUREMENT_MIN: float = -100.0
    MEASUREMENT_MAX: float = 100.0

    @property
    def frontend_origins(self) -> list[str]:
        return [origin.strip() for origin in self.FRONTEND_ORIGINS.split(",") if origin.strip()]

@lru_cache
def get_settings():
    return Settings()

settings = get_settings()
