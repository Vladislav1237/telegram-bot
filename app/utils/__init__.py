"""
Utility functions for the Telegram bot.
"""
import hashlib
from datetime import datetime, timedelta
from typing import Optional

from app.config import config


def generate_referral_link(bot_username: str, user_id: int) -> str:
    """Generate a referral link for a user."""
    return f"https://t.me/{bot_username}?start={user_id}"


def format_balance(amount: float, currency: str = "TON") -> str:
    """Format balance with currency."""
    return f"{amount:.4f} {currency}"


async def check_telegram_subscription(bot, channel_id: int, user_id: int) -> bool:
    """Check if user subscribed to channel."""
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        return member.status in ('member', 'administrator', 'creator')
    except:
        return False


async def can_claim_reward(bot, user_id, channel_id, user_last_claim, freeze_hours: int = None) -> tuple[bool, Optional[datetime]]:
    """
    Check if user can claim reward.
    """
    if freeze_hours is None:
        freeze_hours = config.FREEZE_PERIOD_HOURS
    
    if not await is_subscription_active(bot, user_id, channel_id):
        return False, None
    
    if not user_last_claim:
        return True, None
    
    next_claim_time = user_last_claim + timedelta(hours=freeze_hours)
    
    if datetime.utcnow() >= next_claim_time:
        return True, None
    
    return False, next_claim_time


def calculate_early_unsubscribe_penalty(
    subscription_start: datetime,
    subscription_end: datetime,
    total_amount: float,
) -> float:
    """
    Calculate penalty for early unsubscribe.
    Penalty is proportional to remaining time.
    """
    total_duration = subscription_end - subscription_start
    remaining_duration = subscription_end - datetime.utcnow()
    
    if remaining_duration <= timedelta(0):
        return 0.0
    
    penalty_ratio = remaining_duration.total_seconds() / total_duration.total_seconds()
    penalty = total_amount * penalty_ratio
    
    return min(penalty, total_amount)


def validate_wallet_address(address: str) -> bool:
    """Validate TON wallet address format."""
    # Basic validation - TON addresses are typically 48 characters
    # This can be enhanced with proper TON address validation
    if not address:
        return False
    
    # UQ/ EQ format or raw format
    if address.startswith("UQ") or address.startswith("EQ"):
        return len(address) >= 46
    
    # Raw format (hex)
    if all(c in "0123456789abcdefABCDEF" for c in address):
        return len(address) in [48, 64]
    
    return False


def generate_promo_code(length: int = 8) -> str:
    """Generate a random promo code."""
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    hash_input = f"{datetime.utcnow().isoformat()}{length}"
    hash_bytes = hashlib.sha256(hash_input.encode()).hexdigest()
    
    code = ""
    for i in range(length):
        code += chars[int(hash_bytes[i], 16) % len(chars)]
    
    return code


def format_datetime(dt: datetime, locale: str = "en") -> str:
    """Format datetime for display."""
    if locale == "ru":
        return dt.strftime("%d.%m.%Y %H:%M")
    return dt.strftime("%Y-%m-%d %H:%M")


def get_time_until(dt: datetime) -> str:
    """Get human-readable time until datetime."""
    now = datetime.utcnow()
    diff = dt - now
    
    if diff.total_seconds() <= 0:
        return "now"
    
    hours = int(diff.total_seconds() // 3600)
    minutes = int((diff.total_seconds() % 3600) // 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"
