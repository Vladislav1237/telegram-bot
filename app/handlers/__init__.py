"""
Handler registration module.
"""
import logging
from aiogram import Dispatcher

logger = logging.getLogger(__name__)

from app.handlers import (
    start,
    balance,
    referral,
    tasks,
    withdraw,
    promo,
    admin,
)


def register_handlers(dp: Dispatcher):
    """Register all handlers with the dispatcher."""
    logger.info("Registering handlers...")
    
    # User handlers
    dp.include_router(start.router)
    logger.info("Registered start router")
    
    dp.include_router(balance.router)
    logger.info("Registered balance router")
    
    dp.include_router(referral.router)
    logger.info("Registered referral router")
    
    dp.include_router(tasks.router)
    logger.info("Registered tasks router")
    
    dp.include_router(withdraw.router)
    logger.info("Registered withdraw router")
    
    dp.include_router(promo.router)
    logger.info("Registered promo router")
    
    # Admin handlers
    dp.include_router(admin.router)
    logger.info("Registered admin router")
    
    logger.info("All handlers registered successfully")

