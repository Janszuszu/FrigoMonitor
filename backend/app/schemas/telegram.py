from pydantic import BaseModel


class TelegramSettingsRead(BaseModel):
    enabled: bool
    chat_id: str
    bot_token_configured: bool

    class Config:
        orm_mode = True


class TelegramSettingsUpdate(BaseModel):
    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""


class TelegramTestResult(BaseModel):
    success: bool
    message: str
