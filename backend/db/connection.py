"""
Database connection configuration using SQLAlchemy AsyncEngine.
"""

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

# Get DB URL from env, default to sqlite for local dev (users should provide PG url)
# Example PG URL: postgresql+asyncpg://user:password@localhost/dbname
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")


# pylint: disable=too-few-public-methods
class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db():
    """Dependency for getting async DB session."""
    async with AsyncSessionLocal() as session:
        yield session
