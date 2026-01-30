import asyncio
import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from backend.db.connection import AsyncSessionLocal
from backend.db.repository import ResearchRepository

async def debug_db():
    print("Listing all sessions in DB:")
    async with AsyncSessionLocal() as session:
        repo = ResearchRepository(session)
        sessions = await repo.list_sessions(limit=50)
        for s in sessions:
            print(f"Topic: '{s['topic']}' | Status: {s['status']}")

if __name__ == "__main__":
    asyncio.run(debug_db())
