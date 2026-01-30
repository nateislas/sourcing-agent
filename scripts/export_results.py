import asyncio
import csv
import sys
import os
from sqlalchemy import select
from sqlalchemy.orm import selectinload

# Add project root to sys.path
sys.path.append(os.getcwd())

from backend.db.connection import AsyncSessionLocal
from backend.db.models import EntityModel

OUTPUT_FILE = "research_results.csv"


async def export_to_csv(output_file: str = "research_results.csv"):
    print("Starting export...")
    async with AsyncSessionLocal() as session:
        # Fetch all entities with their evidence eagerly loaded
        stmt = select(EntityModel).options(selectinload(EntityModel.evidence))
        result = await session.execute(stmt)
        entities = result.scalars().all()

        print(f"Found {len(entities)} entities.")

        with open(output_file, mode="w", newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "Canonical Label",
                "Aliases",
                "Target",
                "Modality",
                "Stage",
                "Indication",
                "Geography",
                "Owner",
                "Evidence Package",
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for entity in entities:
                # 1. Aliases
                aliases_str = "; ".join(entity.aliases) if entity.aliases else ""

                # 2. Metadata
                # Default to "Unknown" if missing, or empty string? User said "unknown allowed".
                # I'll use empty string for cleaner look, or "Unknown" if explicitly requested.
                # "Best-supported metadata ... with 'unknown' allowed" -> usually implies explicit "Unknown" or just blank.
                # I'll use get() with default None and convert to string.
                attrs = entity.attributes or {}

                # 3. Evidence Package
                # Format: "[YYYY-MM-DD] url - excerpt" per line
                evidence_lines = []
                for ev in entity.evidence:
                    # Clean content/excerpt
                    content_preview = (
                        ev.content[:200].replace("\n", " ").strip() + "..."
                        if len(ev.content) > 200
                        else ev.content.replace("\n", " ")
                    )
                    line = f"[{ev.timestamp[:10]}] {ev.source_url} - {content_preview}"
                    evidence_lines.append(line)

                evidence_package = "\n".join(evidence_lines)

                row = {
                    "Canonical Label": entity.canonical_name,
                    "Aliases": aliases_str,
                    "Target": attrs.get("target") or "Unknown",
                    "Modality": attrs.get("modality") or "Unknown",
                    "Stage": attrs.get("product_stage") or "Unknown",
                    "Indication": attrs.get("indication") or "Unknown",
                    "Geography": attrs.get("geography") or "Unknown",
                    "Owner": attrs.get("owner") or "Unknown",
                    "Evidence Package": evidence_package,
                }
                writer.writerow(row)

    print(f"Export complete. Saved to {output_file}")


if __name__ == "__main__":
    asyncio.run(export_to_csv())
