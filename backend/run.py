import asyncio
import sys
import os
from dotenv import load_dotenv

# Ensure the backend is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load env before other imports that might use them
load_dotenv()

from backend.research.orchestrator import DeepResearchWorkflow
from backend.db.init_db import init_db


async def main():
    # 1. Get topic from command line or interactive
    if len(sys.argv) > 1:
        topic = " ".join(sys.argv[1:])
    else:
        topic = input("Enter research topic: ")

    if not topic.strip():
        print("Error: Topic is required.")
        return

    print(f"\n--- Starting Research on: {topic} ---\n")

    # 2. Initialize Database
    await init_db()

    # 3. Initialize Workflow
    # We use a 10-minute timeout for the entire research task
    workflow = DeepResearchWorkflow(timeout=600, verbose=True)

    # 4. Run Workflow
    try:
        handler = workflow.run(topic=topic)
        result = await handler

        print("\n--- Research Completed ---\n")
        print(f"Status: {result.status}")
        print(f"Entities Found: {len(result.known_entities)}")

        # Print a summary of findings
        if result.known_entities:
            print("\nTop Entities Discovered:")
            # Sort by mention count
            sorted_entities = sorted(
                result.known_entities.values(),
                key=lambda x: x.mention_count,
                reverse=True,
            )[:10]

            for entity in sorted_entities:
                meta = []
                if entity.drug_class:
                    meta.append(f"Class: {entity.drug_class}")
                if entity.clinical_phase:
                    meta.append(f"Phase: {entity.clinical_phase}")

                meta_str = f" ({', '.join(meta)})" if meta else ""
                print(
                    f"- {entity.canonical_name}{meta_str} [Mentions: {entity.mention_count}]"
                )
                if entity.aliases:
                    print(f"  Aliases: {', '.join(list(entity.aliases)[:3])}")

    except Exception as e:
        print(f"\nError during research: {e}")


if __name__ == "__main__":
    asyncio.run(main())
