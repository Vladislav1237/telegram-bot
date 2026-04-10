"""
Database engine and session management.
"""
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool

from app.config import config


# Create async engine
engine = create_async_engine(
    config.DATABASE_URL,
    echo=False,
    future=True,
    poolclass=NullPool,
)

# Create session maker
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
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
