"""
Entry point for running the Deep Research Workflow from the command line.
Loads environment variables, initializes the database, and executes the research process.
"""

import asyncio
import os
import re
import sys
import warnings

from dotenv import load_dotenv

# Suppress warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="google.auth")
warnings.filterwarnings("ignore", category=FutureWarning, module="google.oauth2")
warnings.filterwarnings("ignore", message=".*urllib3 v2 only supports OpenSSL.*")
warnings.filterwarnings("ignore", message=".*Both GOOGLE_API_KEY and GEMINI_API_KEY.*")
warnings.filterwarnings("ignore", category=UserWarning, module="google.genai")

# Ensure the backend is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load env before other imports that might use them
load_dotenv()

import logging
from datetime import datetime

from backend.db.init_db import init_db
from backend.research.orchestrator import DeepResearchWorkflow
from scripts.export_results import export_to_csv


def sanitize_topic(topic: str) -> str:
    """Sanitizes topic for use in filenames/directory names."""
    # Replace non-alphanumeric with underscore, collapse multiple underscores
    s = re.sub(r"[^\w\s-]", "_", topic).strip().lower()
    s = re.sub(r"[-\s_]+", "_", s)
    return s[:30]


async def main():
    """Main execution loop for the research CLI."""
    # 1. Get topic from command line or interactive
    if len(sys.argv) > 1:
        topic = " ".join(sys.argv[1:])
    else:
        topic = input("Enter research topic: ")

    if not topic.strip():
        print("Error: Topic is required.")
        return

    print(f"\n--- Starting Research on: {topic} ---\n")

    # 1.5 Setup Run Logging
    sanitized_topic = sanitize_topic(topic)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + sanitized_topic
    run_dir = os.path.join(os.getcwd(), "logs", run_id)
    os.makedirs(run_dir, exist_ok=True)

    log_file = os.path.join(run_dir, "run.log")

    # Configure root logger to write to file
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logging.getLogger().addHandler(file_handler)
    logging.getLogger().setLevel(logging.INFO)

    print(f"Logging execution to: {log_file}")

    # 2. Initialize Database
    await init_db()

    try:
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

        except (asyncio.TimeoutError, ValueError, RuntimeError) as e:
            print(f"\nError during research: {e}")
        except KeyboardInterrupt:
            print("\nResearch interrupted by user.")

    finally:
        # Export results to CSV regardless of success or failure
        # This ensures we capture partial results if the script is stopped
        csv_file = os.path.join(run_dir, "results.csv")
        print(f"\nExporting results to: {csv_file}")
        try:
            await export_to_csv(csv_file)
        except Exception as e:
            print(f"Failed to export results: {e}")


if __name__ == "__main__":
    asyncio.run(main())
