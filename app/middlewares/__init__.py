"""
Middleware initialization.
"""
from aiogram import Dispatcher

from app.middlewares.i18n import setup_i18n_middleware
from app.middlewares.session import setup_session_middleware
from app.middlewares.auth import setup_auth_middleware


def setup_middlewares(dp: Dispatcher):
    """Setup all middlewares on dispatcher."""
    setup_i18n_middleware(dp)
    setup_session_middleware(dp)
    setup_auth_middleware(dp)
