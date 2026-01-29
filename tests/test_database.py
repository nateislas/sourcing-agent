"""
Script to verify database connectivity and Repository pattern.
Uses SQLite by default for testing without external dependencies.
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from backend.db.connection import Base
from backend.db.repository import ResearchRepository
from backend.research.state import Entity, EvidenceSnippet, ResearchState

# Use in-memory SQLite for testing
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


async def main():
    """
    Main test execution loop. Sets up an in-memory database and tests the Repository.
    """
    print("Setting up test database...")
    # Use StaticPool and check_same_thread=False for stable in-memory SQLite testing
    engine = create_async_engine(
        TEST_DB_URL,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Session factory
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        repo = ResearchRepository(session)

        # 1. Test Session Creation
        print("Testing Session Persistence...")
        state = ResearchState(topic="Verification Check", status="running")
        await repo.create_session(state)

        saved_state = await repo.get_session("Verification Check")
        assert saved_state is not None
        assert saved_state.topic == "Verification Check"
        print("✅ Session persistence verified")

        # 2. Test Entity and Evidence Persistence
        print("Testing Entity Persistence...")
        entity = Entity(
            canonical_name="Test Entity",
            attributes={"type": "test"},
            evidence=[
                EvidenceSnippet(
                    source_url="http://test",
                    content="proof",
                    timestamp="2023-10-27T10:00:00Z",
                )
            ],
        )
        await repo.save_entity(entity)

        saved_entity = await repo.get_entity("Test Entity")
        assert saved_entity is not None
        assert saved_entity.canonical_name == "Test Entity"
        assert saved_entity.attributes["type"] == "test"
        # Note: Evidence hydration check would go here if implemented in get_entity
        print("✅ Entity persistence verified")

    print("\n🎉 All database tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
