"""
Temporal activities for the Deep Research Application.
Handles external interactions like searching and fetching content.
"""

from typing import List, Optional, Any
from temporalio import activity
from backend.db.connection import AsyncSessionLocal
from backend.db.repository import ResearchRepository
from backend.research.agent import ResearchAgent
from backend.research.state import ResearchState, ResearchPlan, WorkerState


@activity.defn
async def generate_initial_plan(
    topic: str, research_id: Optional[str] = None
) -> ResearchPlan:
    """
    Generates the initial research plan using the Research Agent.
    """
    activity.logger.info(f"Generating initial plan for: {topic}")
    agent = ResearchAgent()
    return await agent.generate_initial_plan(topic, research_id=research_id)


@activity.defn
async def execute_worker_iteration(worker_state: WorkerState) -> dict:
    """
    Executes a single iteration for a specific worker.
    Includes: Search -> Fetch -> Extract -> Queue Management.
    """
    activity.logger.info(
        f"Worker {worker_state.id} executing iteration with strategy {worker_state.strategy}"
    )

    from backend.research.client_search import (
        PerplexitySearchClient,
        TavilySearchClient,
    )
    from backend.research.extraction import EntityExtractor

    # Initialize clients
    perp_client = PerplexitySearchClient(research_id=worker_state.research_id)
    tav_client = TavilySearchClient(research_id=worker_state.research_id)
    entity_extractor = EntityExtractor(research_id=worker_state.research_id)

    try:
        # Metrics for this iteration
        pages_fetched = 0
        new_entities_found = []

        # 1. Search Phase
        # We use Perplexity for broad discovery
        # Use the first query from the worker's query list
        query = (
            worker_state.queries[0] if worker_state.queries else worker_state.strategy
        )
        search_results = await perp_client.search(query, max_results=5)

        # 2. Fetch & Extract Phase
        for result in search_results:
            activity.logger.info(
                f"Worker {worker_state.id} processing URL: {result.url}"
            )

            # For each URL, we try to get high-fidelity markdown via Tavily Extract
            try:
                tav_res = await tav_client.search(
                    result.url, max_results=1, include_raw_content=True
                )
                if tav_res:
                    content = tav_res[0].raw_content or result.snippet
                else:
                    content = result.snippet
            except Exception as e:
                activity.logger.warning(
                    f"Tavily extraction failed for {result.url}: {e}"
                )
                content = result.snippet

            pages_fetched += 1

            # Extract entities
            extracted = await entity_extractor.extract_entities(content, result.url)
            for entry in extracted:
                new_entities_found.append(entry)

        novelty_rate = len(new_entities_found) / max(pages_fetched, 1)

        return {
            "worker_id": worker_state.id,
            "pages_fetched": pages_fetched,
            "entities_found": len(new_entities_found) + 2,  # total mentions placeholder
            "new_entities": len(new_entities_found),
            "novelty_rate": novelty_rate,
            "status": "PRODUCTIVE" if novelty_rate > 0.1 else "DECLINING",
            "extracted_data": new_entities_found,  # For orchestrator to merge into state
        }
    finally:
        await entity_extractor.close()


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
