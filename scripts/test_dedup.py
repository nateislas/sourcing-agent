
import asyncio
import json
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from backend.db.models import Base
from backend.db.repository import ResearchRepository
from backend.research.state import Entity, EvidenceSnippet, ResearchState

# Use in-memory SQLite for testing
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

async def test_dedup():
    print("Setting up test database...")
    engine = create_async_engine(
        TEST_DB_URL,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        repo = ResearchRepository(session)
        
        # Test Case 1: Initial Save with Duplicates
        print("Testing deduplication on initial save...")
        snippet = EvidenceSnippet(
            source_url="http://test.com/page1",
            content="Evidence text 1",
            timestamp="2026-01-31T12:00:00Z"
        )
        
        # Entity with redundant evidence (same source/content)
        entity = Entity(
            canonical_name="Drug A",
            evidence=[snippet, snippet, snippet]
        )
        
        await repo.save_entity(entity)
        
        saved = await repo.get_entity("Drug A")
        print(f"Evidence count after initial save: {len(saved.evidence)}")
        assert len(saved.evidence) == 1, f"Expected 1, got {len(saved.evidence)}"
        
        # Test Case 2: Update with duplicate evidence
        print("Testing deduplication on update...")
        # Add the same evidence again
        await repo.save_entity(entity)
        
        saved_updated = await repo.get_entity("Drug A")
        print(f"Evidence count after update: {len(saved_updated.evidence)}")
        assert len(saved_updated.evidence) == 1, f"Expected 1, got {len(saved_updated.evidence)}"
        
        # Test Case 3: Add new unique evidence
        print("Testing addition of unique evidence...")
        snippet2 = EvidenceSnippet(
            source_url="http://test.com/page2",
            content="Unique evidence text",
            timestamp="2026-01-31T12:01:00Z"
        )
        entity.evidence.append(snippet2)
        await repo.save_entity(entity)
        
        saved_final = await repo.get_entity("Drug A")
        print(f"Evidence count after adding unique snippet: {len(saved_final.evidence)}")
        assert len(saved_final.evidence) == 2, f"Expected 2, got {len(saved_final.evidence)}"

    print("\n✅ Evidence deduplication verified!")

if __name__ == "__main__":
    asyncio.run(test_dedup())
