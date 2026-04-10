"""
Authentication middleware - simplified.
"""
import logging
from typing import Any, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseMiddleware):
    """Middleware to ensure user is registered in DB."""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Any],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Skip if no session - let handler handle it
        session = data.get("session")
        if not session:
            logger.warning("[AUTH_MW] No session - skipping auth")
            return await handler(event, data)
        
        user_obj = None
        if isinstance(event, Message):
            user_obj = event.from_user
        elif isinstance(event, CallbackQuery):
            user_obj = event.from_user
        
        if not user_obj:
            logger.warning("[AUTH_MW] No user object")
            data["user"] = None
            return await handler(event, data)
        
        try:
            from app.database.repositories import UserRepository
            user_repo = UserRepository(session)
            db_user = await user_repo.get_by_telegram_id(user_obj.id)
            
            if not db_user:
                db_user = await user_repo.create(
                    telegram_id=user_obj.id,
                    username=user_obj.username,
                    first_name=user_obj.first_name,
                    last_name=user_obj.last_name,
                    language_code=user_obj.language_code or "en",
                )
            
            data["user"] = db_user
        except Exception as e:
            logger.error(f"[AUTH_MW] Error: {e}", exc_info=True)
            data["user"] = None
        
        return await handler(event, data)


def setup_auth_middleware(dp):
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

