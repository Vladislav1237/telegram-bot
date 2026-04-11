"""
Database engine and session management.
"""
import asyncio
import logging
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import OperationalError

from app.config import config

logger = logging.getLogger(__name__)

# Create async engine with proper settings for SQLite
engine = create_async_engine(
    config.DATABASE_URL,
    echo=False,
    future=True,
    poolclass=StaticPool,  # Use StaticPool for SQLite to avoid locking issues
    connect_args={"check_same_thread": False} if "sqlite" in config.DATABASE_URL else {},
)

# Create session maker
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db():
    """Initialize database - create all tables."""
    from app.models import Base
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    await migrate_check_type()


async def migrate_check_type():
    """Add check_type column if not exists."""
    from sqlalchemy import text
    
    async with engine.begin() as conn:
        try:
            await conn.execute(text(
                "ALTER TABLE tasks ADD COLUMN check_type VARCHAR(20) DEFAULT 'auto'"
            ))
        except Exception:
            pass  # Column already exists


async def close_db():
    """Close database connections."""
    await engine.dispose()


async def execute_with_retry(func, max_retries=3, delay=0.5):
    """Execute database operation with retry on lock errors."""
    for attempt in range(max_retries):
        try:
            return await func()
        except OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                logger.warning(f"Database locked, retrying ({attempt + 1}/{max_retries})...")
                await asyncio.sleep(delay * (attempt + 1))
            else:
                raise
