import asyncio

from sqlalchemy import text

from backend.db.connection import engine


async def migrate():
    """
    Adds verification columns to the entities table if they don't exist.
    """
    print("Starting migration: Adding verification columns to 'entities' table...")

    async with engine.begin() as conn:
        # Check if columns exist (SQLite specific pragma)
        result = await conn.execute(text("PRAGMA table_info(entities)"))
        columns = [row.name for row in result.fetchall()]

        if "verification_status" not in columns:
            print("Adding 'verification_status' column...")
            await conn.execute(
                text(
                    "ALTER TABLE entities ADD COLUMN verification_status VARCHAR DEFAULT 'UNVERIFIED'"
                )
            )

        if "rejection_reason" not in columns:
            print("Adding 'rejection_reason' column...")
            await conn.execute(
                text("ALTER TABLE entities ADD COLUMN rejection_reason VARCHAR")
            )

        if "confidence_score" not in columns:
            print("Adding 'confidence_score' column...")
            await conn.execute(
                text(
                    "ALTER TABLE entities ADD COLUMN confidence_score INTEGER DEFAULT 0"
                )
            )

    print("Migration complete.")


if __name__ == "__main__":
    asyncio.run(migrate())
