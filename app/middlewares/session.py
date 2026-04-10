"""
Database session middleware for aiogram.
"""
import logging
from typing import Any, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.database import db

logger = logging.getLogger(__name__)


class DatabaseSessionMiddleware(BaseMiddleware):
    """Middleware to provide database session to handlers."""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Any],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        event_type = type(event).__name__
        user_id = getattr(getattr(event, 'from_user', None), 'id', 'unknown')
        
        logger.info(f"[SESSION_MW] {event_type} from {user_id}")
        
        # Get session - don't commit here, let handler commit if needed
        async with db.async_session_maker() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
                # Don't commit here - handlers should commit themselves
                logger.info(f"[SESSION_MW] Handler done for {user_id}")
                return result
            except Exception as e:
                logger.error(f"[SESSION_MW] Handler error: {e}", exc_info=True)
                await session.rollback()
                raise
            finally:
                await session.close()


def setup_session_middleware(dp):
    """Setup session middleware on dispatcher."""
    dp.message.middleware(DatabaseSessionMiddleware())
    dp.callback_query.middleware(DatabaseSessionMiddleware())
