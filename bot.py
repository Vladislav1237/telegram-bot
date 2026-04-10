import asyncio
import logging
from contextlib import asynccontextmanager

import aiosqlite
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram_i18n import I18nMiddleware
from aiogram_i18n.middlewares import FluentRuntimeMiddleware
from aiogram_i18n.utils import get_locale

from config_reader import settings
from database.engine import engine, BaseModel
from handlers import admin, economy, tasks, user
from middlewares.db import DbSessionMiddleware
from utils.scheduler import scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(dispatcher: Dispatcher):
    # Startup
    await engine.begin()
    await BaseModel.metadata.create_all(bind=engine.sync_engine)
    
    scheduler.start()
    logger.info("Bot started")
    
    yield
    
    # Shutdown
    scheduler.shutdown()
    await engine.dispose()
    logger.info("Bot stopped")


async def main() -> None:
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    
    dp = Dispatcher(
        lifespan=lifespan,
        db_url=settings.DATABASE_URL,
    )
    
    i18n_middleware = I18nMiddleware(
        middleware=FluentRuntimeMiddleware(
            path="locales/{locale}/messages.ftl",
            locales=["en", "ru"],
            default_locale="en",
        ),
        default_locale="en",
        manager_locator=lambda message: "en",
    )
    
    dp.update.middleware(DbSessionMiddleware(url=settings.DATABASE_URL))
    dp.update.middleware(i18n_middleware)
    
    dp.include_routers(
        user.router,
        economy.router,
        tasks.router,
        admin.router,
    )
    
    try:
        await dp.start_polling(bot, i18n=i18n_middleware)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
