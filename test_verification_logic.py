
import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from backend.research.verification import VerificationAgent
from backend.research.state import Entity, EvidenceSnippet
from backend.db.connection import AsyncSessionLocal
from backend.db.repository import ResearchRepository
from backend.db.init_db import init_db
from backend.research import activities

# Dummy Entity Data
MOCK_ENTITY = Entity(
    canonical_name="CDK12-IN-1",
    aliases={"Compound A"},
    attributes={
        "target": "CDK12", 
        "modality": "Small molecule",
        "product_stage": "Preclinical",
        "owner": "Unknown" 
    },
    evidence=[
        EvidenceSnippet(
            source_url="http://example.com",
            content="CDK12-IN-1 is a potent small molecule inhibitor of CDK12 demonstrating antitumor activity in preclinical TNBC models.",
            timestamp=datetime.utcnow().isoformat()
        )
    ]
)

MOCK_CONSTRAINTS = {
    "target": "CDK12",
    "modality": "Small molecule",
    "indication": "TNBC",
    "geography": "China", # This should cause uncertainty or rejection if strict
    "required_metadata": ["owner", "product_stage"]
}

async def test_verification_agent():
    print("\n--- Testing Verification Agent ---")
    agent = VerificationAgent()
    print("Verifying entity...")
    result = await agent.verify_entity(MOCK_ENTITY, MOCK_CONSTRAINTS)
    print(f"Result Status: {result.status}")
    print(f"Reason: {result.explanation}")
    print(f"Missing Fields: {result.missing_fields}")
    return result

async def test_persistence(verification_result):
    print("\n--- Testing Persistence ---")
    
    # Init DB ensures tables exist (not nuking anymore, assuming migrated or fresh)
    await init_db()
    
    async with AsyncSessionLocal() as session:
        repo = ResearchRepository(session)
        
        # 1. Update Mock Entity with result
        MOCK_ENTITY.verification_status = verification_result.status
        MOCK_ENTITY.rejection_reason = verification_result.rejection_reason
        MOCK_ENTITY.confidence_score = verification_result.confidence
        
        # 2. Save
        print("Saving entity...")
        await repo.save_entity(MOCK_ENTITY)
        
        # 3. Retrieve
        print("Retrieving entity...")
        retrieved = await repo.get_entity(MOCK_ENTITY.canonical_name)
        
        print(f"Retrieved Status: {retrieved.verification_status}")
        print(f"Retrieved Reason: {retrieved.rejection_reason}")
        
        assert retrieved.verification_status == verification_result.status
        print("Persistence Check Passed!")

async def test_gap_analysis(verification_result):
    print("\n--- Testing Gap Analysis ---")
    entity_dict = MOCK_ENTITY.model_dump()
    result_dict = verification_result.model_dump()
    
    queries = await activities.analyze_gaps(entity_dict, result_dict)
    print("Generated Gap Fill Queries:")
    for q in queries:
        print(f"- {q}")
        
    # Validation
    if "owner" in verification_result.missing_fields:
        assert any("owner" in q for q in queries)
    
    print("Gap Analysis Check Passed!")

async def main():
    result = await test_verification_agent()
    await test_persistence(result)
    await test_gap_analysis(result)

if __name__ == "__main__":
    asyncio.run(main())
