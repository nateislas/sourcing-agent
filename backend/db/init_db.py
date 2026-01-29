"""
Utility to initialize the database schema.
Creates all tables defined in models.py if they don't already exist.
"""

import asyncio
from backend.db.connection import engine, Base

# Import models to ensure they are registered with Base.metadata
# pylint: disable=unused-import
import backend.db.models


async def init_db():
    """
    Creates all tables in the database asynchronously.
    """
    print(f"Initializing database at: {engine.url}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database initialization complete.")


if __name__ == "__main__":
    asyncio.run(init_db())
