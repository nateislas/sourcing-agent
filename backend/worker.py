"""
Entry point for starting the Temporal Worker.
Registers the workflows and activities and connects to the Temporal cluster.
"""

import asyncio
import os

from temporalio.client import Client, TLSConfig
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from backend.config import TASK_QUEUE, TEMPORAL_ADDRESS, TEMPORAL_NAMESPACE
from backend.db.init_db import init_db
from backend.research.activities import (
    analyze_gaps,
    execute_worker_iteration,
    generate_initial_plan,
    save_state,
    update_plan,
    verify_entity,
    perform_initial_search,
)
from backend.research.workflows import DeepResearchOrchestrator


async def main():
    """
    Connects to Temporal and starts the worker process.
    """
    # Load client cert/key if available for mTLS (Cloud)
    # For now assuming API Key or simple connection based on previous context
    # Adjust TLS config based on environment

    # Check for API key in env
    api_key = os.getenv("TEMPORAL_API_KEY")
    tls_config = None
    if api_key:
        # If API key is present, we likely need TLS (Cloud)
        tls_config = TLSConfig()

    print(
        f"Connecting to Temporal at {TEMPORAL_ADDRESS} namespace={TEMPORAL_NAMESPACE}"
    )
    client = await Client.connect(
        TEMPORAL_ADDRESS,
        namespace=TEMPORAL_NAMESPACE,
        api_key=api_key,
        tls=tls_config or False,
        data_converter=pydantic_data_converter,
    )

    # Initialize Database tables before starting worker
    await init_db()

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[DeepResearchOrchestrator],
        activities=[
            generate_initial_plan,
            execute_worker_iteration,
            update_plan,
            save_state,
            verify_entity,
            analyze_gaps,
            perform_initial_search,
        ],
    )

    print("Worker started...")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
