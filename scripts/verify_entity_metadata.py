import asyncio
import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from backend.db.init_db import init_db
from backend.research.state_manager import DatabaseStateManager
from backend.db.connection import AsyncSessionLocal
from backend.db.models import EntityModel
from sqlalchemy import select


async def main():
    print("Initializing DB...")
    await init_db()

    mgr = DatabaseStateManager()
    canonical_name = "TestDrug-123"
    attributes = {
        "target": "TEST-TARGET",
        "modality": "Small Molecule",
        "product_stage": "Phase 1",
        "indication": "Cancer",
        "geography": "Global",
        "owner": "TestPharma",
    }

    print(f"Marking entity {canonical_name} as known with attributes...")
    success = await mgr.mark_entity_known(canonical_name, attributes=attributes)

    if success:
        print("Successfully marked entity (created new).")
    else:
        print("Entity mark returned False (already exists?). Checking DB anyway...")

    print("Verifying attributes in DB...")
    async with AsyncSessionLocal() as session:
        stmt = select(EntityModel).where(EntityModel.canonical_name == canonical_name)
        result = await session.execute(stmt)
        entity = result.scalar_one_or_none()

        if not entity:
            print("ERROR: Entity not found in DB!")
            sys.exit(1)

        print(f"Found entity: {entity.canonical_name}")
        print(f"Attributes: {entity.attributes}")

        # Verify fields
        errors = 0
        for k, v in attributes.items():
            if entity.attributes.get(k) != v:
                print(
                    f"ERROR: Attribute mismatch! {k}: expected {v}, got {entity.attributes.get(k)}"
                )
                errors += 1
            else:
                print(f"Verified {k}: {v}")

        # cleanup
        print("Cleaning up...")
        await session.delete(entity)
        await session.commit()
        print("Cleaned up.")

        if errors > 0:
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
