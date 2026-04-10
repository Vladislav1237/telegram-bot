"""
Internationalization (i18n) middleware for aiogram 3.x - simplified version.
"""
from typing import Any, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from app.config import config


class I18nMiddleware(BaseMiddleware):
    """Middleware for internationalization support."""
    
    def __init__(self):
        super().__init__()
    
    def gettext(self, message: str, locale: str) -> str:
        """Simple translation function."""
        return message
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Any],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Process the event and set up i18n context."""
        locale = config.DEFAULT_LOCALE
        
        try:
            if isinstance(event, Message):
                if event.from_user and event.from_user.language_code:
                    user_locale = event.from_user.language_code.split("-")[0]
                    if user_locale in config.AVAILABLE_LOCALES:
                        locale = user_locale
            elif isinstance(event, CallbackQuery):
                if event.from_user and event.from_user.language_code:
                    user_locale = event.from_user.language_code.split("-")[0]
                    if user_locale in config.AVAILABLE_LOCALES:
                        locale = user_locale
        except:
            pass
        
        data["_"] = lambda x: x
        data["locale"] = locale
        
        return await handler(event, data)


def setup_i18n_middleware(dp):
    """Setup i18n middleware on dispatcher."""
    i18n_middleware = I18nMiddleware()
    dp.message.middleware(i18n_middleware)
    dp.callback_query.middleware(i18n_middleware)
    return i18n_middleware
