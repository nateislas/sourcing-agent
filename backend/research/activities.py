"""
Temporal activities for the Deep Research Application.
Handles external interactions like searching and fetching content.
"""

from temporalio import activity
from backend.db.connection import AsyncSessionLocal
from backend.db.repository import ResearchRepository
from backend.research.agent import ResearchAgent
from backend.research.state import ResearchState, ResearchPlan, WorkerState


@activity.defn
async def generate_initial_plan(topic: str) -> ResearchPlan:
    """
    Generates the initial research plan using the Research Agent.
    """
    activity.logger.info(f"Generating initial plan for: {topic}")
    agent = ResearchAgent()
    return await agent.generate_initial_plan(topic)


@activity.defn
async def execute_worker_iteration(worker_state: WorkerState) -> dict:
    """
    Executes a single iteration for a specific worker.
    Includes: Search -> Fetch -> Extract -> Queue Management.
    """
    activity.logger.info(
        f"Worker {worker_state.id} executing iteration with strategy {worker_state.strategy}"
    )

    # Stub implementation suitable for Orchestrator testing
    # In reality, this would contain the complex inner loop

    import random
    import asyncio

    # Simulate work
    await asyncio.sleep(1)

    new_entities_count = random.randint(0, 5)
    pages = 10
    novelty_rate = new_entities_count / pages

    return {
        "worker_id": worker_state.id,
        "pages_fetched": pages,
        "entities_found": new_entities_count + 2,  # Total mentions
        "new_entities": new_entities_count,
        "novelty_rate": novelty_rate,
        "status": "PRODUCTIVE" if novelty_rate > 0.05 else "DECLINING",
    }


@activity.defn
async def update_plan(state: ResearchState) -> ResearchPlan:
    """
    Updates the research plan based on the current state.
    """
    activity.logger.info("Updating research plan based on discoveries.")
    # Stub - just return existing plan
    return state.plan


@activity.defn
async def save_state(state: ResearchState) -> bool:
    """
    Persists the current global research state.
    Args:
        state: The ResearchState to save.
    Returns:
        True if successful.
    """
    activity.logger.info(f"Saving state for topic: {state.topic}")
    async with AsyncSessionLocal() as session:
        repo = ResearchRepository(session)
        await repo.save_session(state)
    return True
