"""
Verifies evidence persistence and deduplication in the database and CSV export.
Checks that multiple saves of the same entity with new evidence append correctly and that CSV export reflects the data.
"""

import asyncio
import csv
import os
import sys
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

# Add project root to sys.path
sys.path.append(os.getcwd())

from backend.db.connection import AsyncSessionLocal
from backend.db.init_db import init_db
from backend.db.models import EntityModel
from backend.db.repository import ResearchRepository
from backend.research.state import Entity, EvidenceSnippet

OUTPUT_FILE = "research_results.csv"


async def main():
    print("Initializing DB...")
    await init_db()

    canonical_name = "Verify persistence drug"

    # 1. Create initial entity with 1 evidence
    ev1 = EvidenceSnippet(
        source_url="http://example.com/1",
        content="Evidence 1 content",
        timestamp=datetime.utcnow().isoformat(),
    )
    entity = Entity(
        canonical_name=canonical_name,
        aliases={"VP-001"},
        attributes={"target": "T1", "modality": "M1"},
        evidence=[ev1],
    )

    print("Saving entity (Pass 1)...")
    async with AsyncSessionLocal() as session:
        repo = ResearchRepository(session)
        await repo.save_entity(entity)

    # 2. Add new evidence and save again
    ev2 = EvidenceSnippet(
        source_url="http://example.com/2",
        content="Evidence 2 content",
        timestamp=datetime.utcnow().isoformat(),
    )
    entity.evidence.append(ev2)
    # Also add a duplicate of ev1 to check deduplication
    entity.evidence.append(ev1)

    print("Saving entity (Pass 2 - Appending)...")
    async with AsyncSessionLocal() as session:
        repo = ResearchRepository(session)
        await repo.save_entity(entity)

    # 3. Verify DB state
    print("Verifying DB state...")
    async with AsyncSessionLocal() as session:
        stmt = (
            select(EntityModel)
            .options(selectinload(EntityModel.evidence))
            .where(EntityModel.canonical_name == canonical_name)
        )
        result = await session.execute(stmt)
        db_entity = result.scalar_one()

        print(f"Entity: {db_entity.canonical_name}")
        print(f"Evidence count: {len(db_entity.evidence)}")

        # Expect 2 evidence items (ev1, ev2). Duplicate ev1 should be ignored.
        if len(db_entity.evidence) != 2:
            print(f"ERROR: Expected 2 evidence items, got {len(db_entity.evidence)}")
            for e in db_entity.evidence:
                print(f" - {e.source_url}: {e.content}")
            sys.exit(1)
        else:
            print("Verified evidence count (deduplication worked).")

    # 4. Run Export
    print("Running export...")
    # Import the export function dynamically or just run it via subprocess if generic,
    # but here I'll just run the script file using os.system or similar for simplicity
    # OR better, import the function from scripts.export_results if I made it importable.
    # I wrote it as a script with __main__. I can just import it.
    from scripts.export_results import export_to_csv

    await export_to_csv()

    # 5. Check CSV
    print("Checking CSV...")
    with open(OUTPUT_FILE) as f:
        reader = csv.DictReader(f)
        found = False
        for row in reader:
            if row["Canonical Label"] == canonical_name:
                found = True
                print("Found row in CSV.")
                pkg = row["Evidence Package"]
                print(f"Evidence Package:\n{pkg}")
                if "Evidence 1 content" in pkg and "Evidence 2 content" in pkg:
                    print("Verified evidence content in CSV.")
                else:
                    print("ERROR: Missing evidence content in CSV!")
                    sys.exit(1)

                if row["Target"] == "T1" and row["Modality"] == "M1":
                    print("Verified metadata.")
                else:
                    print(f"ERROR: Metadata mismatch: {row}")
                    sys.exit(1)

        if not found:
            print("ERROR: Entity not found in CSV!")
            sys.exit(1)

    print("Cleanup...")
    async with AsyncSessionLocal() as session:
        stmt = select(EntityModel).where(EntityModel.canonical_name == canonical_name)
        res = await session.execute(stmt)
        ent = res.scalar_one()
        await session.delete(ent)
        await session.commit()

    print("Verification Successful!")


if __name__ == "__main__":
    asyncio.run(main())
