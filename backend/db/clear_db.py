"""
Utility to clear the database by dropping all tables and recreating them.
This will delete all data but maintain the schema.
"""

import asyncio

from sqlalchemy.exc import DBAPIError

# Import models to ensure they are registered with Base.metadata
# pylint: disable=unused-import
from backend.db import models  # noqa: F401
from backend.db.connection import Base, engine


async def clear_db():
    """
    Drops all tables and recreates them, effectively clearing all data.
    """
    print(f"Clearing database at: {engine.url}")
    
    try:
        async with engine.begin() as conn:
            # Drop all tables
            print("Dropping all tables...")
            await conn.run_sync(Base.metadata.drop_all)
            print("All tables dropped.")
            
            # Recreate all tables
            print("Recreating tables...")
            await conn.run_sync(Base.metadata.create_all)
            print("Database cleared and reinitialized successfully.")
    except DBAPIError as e:
        print(f"Error clearing database: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(clear_db())
