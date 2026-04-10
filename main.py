"""Main.py - with debug logging."""
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import config
from app.database import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("=== Starting Bot ===")
    
    await db.connect()
    logger.info("DB connected")
    
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    me = await bot.get_me()
    logger.info(f"Bot: @{me.username}")
    
    await bot.get_updates(offset=-1)
    logger.info("Updates flushed")
    
    dp = Dispatcher()
    
    # Setup middlewares FIRST
    from app.middlewares import setup_middlewares
    setup_middlewares(dp)
    logger.info("Middlewares setup complete")
    
    # Register handlers AFTER middlewares
    from app.handlers import register_handlers
    register_handlers(dp)
    logger.info("Handlers registered")
    
    logger.info("Starting polling...")
    await dp.start_polling(bot, handle_as_tasks=False)
    logger.info("Polling stopped")
    
    await bot.session.close()
    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())