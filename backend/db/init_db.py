"""
Utility to initialize the database schema.
Creates all tables defined in models.py if they don't already exist.
"""

import asyncio

# Import models to ensure they are registered with Base.metadata
# pylint: disable=unused-import
from backend.db.connection import Base, engine


async def init_db():
    """
    Creates all tables in the database asynchronously.
    """
    print(f"Initializing database at: {engine.url}")
    
    # Retry loop for Postgres startup
    for i in range(5):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            print("Database initialization complete.")
            return
        except Exception as e:
            print(f"Database not ready yet, retrying... ({e})")
            await asyncio.sleep(2)
            
    print("Failed to initialize database after multiple retries.")


if __name__ == "__main__":
    asyncio.run(init_db())
