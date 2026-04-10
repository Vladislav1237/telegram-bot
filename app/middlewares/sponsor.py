from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable, Union
import logging

logger = logging.getLogger(__name__)

class SponsorSubscribeMiddleware(BaseMiddleware):
    """
    Middleware-заглушка для проверки подписки на спонсоров.
    Основная логика проверки перенесена в хендлер /start и кнопку check_subscription.
    Этот мидлварь можно использовать для дополнительной защиты других хендлеров в будущем.
    """
    
    async def __call__(
        self,
        handler: Callable[[Union[Message, CallbackQuery], Dict[str, Any]], Awaitable[Any]],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any]
    ) -> Any:
        # Пока просто пропускаем все события
        # В будущем здесь можно добавить проверку для всех сообщений кроме /start
        return await handler(event, data)
