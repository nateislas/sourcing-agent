
import asyncio
import json
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from backend.db.connection import AsyncSessionLocal
from backend.db.models import EntityModel, EvidenceModel

async def inspect():
    async with AsyncSessionLocal() as session:
        # Get entities with more than 1 mention or many evidence pieces
        stmt = (
            select(EntityModel)
            .options(selectinload(EntityModel.evidence))
            .where(EntityModel.mention_count > 0)
            .order_by(EntityModel.mention_count.desc())
            .limit(10)
        )
        result = await session.execute(stmt)
        entities = result.scalars().all()
        
        print(f"--- Found {len(entities)} active entities ---\n")
        for ent in entities:
            print(f"ENTITY: {ent.canonical_name}")
            print(f"  Mention Count: {ent.mention_count}")
            print(f"  Aliases: {ent.aliases}")
            print(f"  Attributes: {json.dumps(ent.attributes, indent=4)}")
            print(f"  Evidence count: {len(ent.evidence)}")
            for i, ev in enumerate(ent.evidence[:3]):
                print(f"    [{i}] {ev.source_url}")
            if len(ent.evidence) > 3:
                print(f"    ... and {len(ent.evidence)-3} more")
            print("-" * 30)

if __name__ == "__main__":
    asyncio.run(inspect())
