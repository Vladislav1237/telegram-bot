from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    BOT_TOKEN: str
    ADMIN_IDS: str = ""
    CHANNEL_ID: int = -1001234567890
    CHANNEL_LINK: str = "https://t.me/your_channel"
    REFERRAL_REWARD: float = 0.025
    MIN_WITHDRAWAL: float = 0.2
    SUBSCRIPTION_REWARD: float = 0.05
    DATABASE_URL: str = "sqlite+aiosqlite:///bot.db"


settings = Settings()
ADMIN_IDS = [int(id.strip()) for id in settings.ADMIN_IDS.split(",") if id.strip()]
