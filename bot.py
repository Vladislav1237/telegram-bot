import asyncio
import logging
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram_i18n import I18nMiddleware
from aiogram_i18n.cores import FluentRuntimeCore

from config_reader import settings
from database.engine import engine, BaseModel, async_session_maker
from app.handlers import (
    start,
    balance,
    referral,
    tasks,
    withdraw,
    promo,
    admin,
)
from app.middlewares.session import DatabaseSessionMiddleware
from app.middlewares.sponsor import SponsorSubscribeMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(dispatcher: Dispatcher):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.create_all)
    
    logger.info("Bot started")
    
    yield
    
    # Shutdown
    await engine.dispose()
    logger.info("Bot stopped")


async def main() -> None:
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    
    dp = Dispatcher(
        lifespan=lifespan,
    )
    
    i18n_middleware = I18nMiddleware(
        core=FluentRuntimeCore(
            path="locales/{locale}/messages.ftl",
            locales=["en", "ru"],
            default_locale="en",
        ),
        default_locale="en",
        locale_key="locale",
    )
    
    dp.update.middleware(DatabaseSessionMiddleware())
    dp.update.middleware(SponsorSubscribeMiddleware())
    dp.update.middleware(i18n_middleware)
    
    dp.include_routers(
        start.router,
        balance.router,
        referral.router,
        tasks.router,
        withdraw.router,
        promo.router,
        admin.router,
    )
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
