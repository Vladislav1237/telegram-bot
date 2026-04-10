"""
Database session and engine management.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from sqlalchemy.orm import selectinload
from typing import AsyncGenerator

from app.config import config
from app.models import Base


class Database:
    """Database manager class."""
    
    def __init__(self):
        self.engine = None
        self.async_session_maker = None
    
    async def connect(self):
        """Initialize database connection."""
        self.engine = create_async_engine(
            config.DATABASE_URL,
            echo=False,  # Set to True for SQL debugging
            future=True,
        )
        
        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        # Create tables
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def disconnect(self):
        """Close database connection."""
        if self.engine:
            await self.engine.dispose()
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session."""
        async with self.async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    def get_session_sync(self) -> AsyncSession:
        """Get database session (synchronous context)."""
        return self.async_session_maker()


# Global database instance
db = Database()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session."""
    async with db.get_session() as session:
        yield session
