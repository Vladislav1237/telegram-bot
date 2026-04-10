"""
Configuration loader for the Telegram bot.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """Bot configuration class."""
    
    # Bot settings
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    _env_admins = [
        int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
    ]
    ADMIN_IDS: list[int] = _env_admins if _env_admins else [807120521]
    
    # Telethon settings (for subscription check) - deprecated, use aiogram
    TELETHON_API_ID: str = os.getenv("TELETHON_API_ID", "")
    TELETHON_API_HASH: str = os.getenv("TELETHON_API_HASH", "")
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "sqlite+aiosqlite:///bot_database.db"
    )
    
    # TON settings
    TON_WALLET_ADDRESS: str = os.getenv("TON_WALLET_ADDRESS", "")
    TON_WALLET_SECRET: str = os.getenv("TON_WALLET_SECRET", "")
    MIN_WITHDRAWAL_AMOUNT: float = float(os.getenv("MIN_WITHDRAWAL_AMOUNT", "0.2"))
    REFERRAL_REWARD: float = float(os.getenv("REFERRAL_REWARD", "0.025"))
    
    # Subscription
    SUBSCRIPTION_CHANNEL_ID: int = int(os.getenv("SUBSCRIPTION_CHANNEL_ID", "0"))
    FREEZE_PERIOD_HOURS: int = int(os.getenv("FREEZE_PERIOD_HOURS", "24"))
    
    # Locales
    DEFAULT_LOCALE: str = os.getenv("DEFAULT_LOCALE", "en")
    AVAILABLE_LOCALES: list[str] = [
        x.strip() for x in os.getenv("AVAILABLE_LOCALES", "en,ru").split(",")
    ]
    
    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration."""
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required")
        if not cls.DATABASE_URL:
            raise ValueError("DATABASE_URL is required")
        return True


config = Config()
