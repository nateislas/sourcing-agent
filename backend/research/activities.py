import os
import re
from typing import List, Optional, Any
from temporalio import activity
from backend.db.connection import AsyncSessionLocal
from backend.db.repository import ResearchRepository
from backend.research.agent import ResearchAgent
from backend.research.state import ResearchState, ResearchPlan, WorkerState
from backend.research.client_search import (
    PerplexitySearchClient,
    TavilySearchClient,
)
from backend.research.extraction import EntityExtractor


import logging

logger = logging.getLogger(__name__)


def safe_get_logger():
    """Returns the Temporal activity logger if in context, otherwise the standard logger."""
    try:
        return activity.logger
    except RuntimeError:
        return logger


@activity.defn
async def generate_initial_plan(
    topic: str, research_id: Optional[str] = None
) -> ResearchPlan:
    """
    Generates the initial research plan using the Research Agent.
    """
    safe_get_logger().info(f"Generating initial plan for: {topic}")
    agent = ResearchAgent()
    return await agent.generate_initial_plan(topic, research_id=research_id)


@activity.defn
async def execute_worker_iteration(worker_state: WorkerState) -> dict:
    """
    Executes a single iteration for a specific worker.
    Includes: Search -> Fetch -> Extract -> Queue Management.
    """
    safe_get_logger().info(
        f"Worker {worker_state.id} executing iteration with strategy {worker_state.strategy}"
    )

    # Initialize clients
    perp_client = PerplexitySearchClient(research_id=worker_state.research_id)
    tav_client = TavilySearchClient(research_id=worker_state.research_id)
    entity_extractor = EntityExtractor(research_id=worker_state.research_id)

    try:
        # Metrics for this iteration
        pages_fetched = 0
        new_entities_found = []
        discovered_links = []

        # 1. Search Phase
        # Use round-robin query selection based on iteration
        page_budget = int(os.getenv("WORKER_PAGE_BUDGET", 50))
        iteration_index = worker_state.pages_fetched // page_budget
        query_index = (
            iteration_index % len(worker_state.queries) if worker_state.queries else 0
        )
        query = (
            worker_state.queries[query_index]
            if worker_state.queries
            else worker_state.strategy
        )

        # Track query execution in history
        query_record = {
            "query": query,
            "iteration": iteration_index,
            "results_count": 0,
            "new_entities": 0,
        }

        search_results = await perp_client.search(query, max_results=5)
        query_record["results_count"] = len(search_results)

        # URLs to process in this iteration
        url_queue = [res.url for res in search_results]

        # 2. Add from personal queue if budget allows
        while len(url_queue) < page_budget and worker_state.personal_queue:
            url_queue.append(worker_state.personal_queue.pop(0))

        # 3. Fetch & Extract Phase
        for current_url in url_queue:
            if pages_fetched >= page_budget:
                break

            safe_get_logger().info(
                f"Worker {worker_state.id} processing URL: {current_url}"
            )

            # For each URL, we try to get high-fidelity markdown via Tavily Extract
            try:
                tav_res = await tav_client.search(
                    current_url, max_results=1, include_raw_content=True
                )
                if tav_res and tav_res[0].raw_content:
                    raw_content = tav_res[0].raw_content
                    text_content = tav_res[0].snippet or raw_content
                else:
                    # Fallback or empty
                    raw_content = None
                    text_content = ""
            except Exception as e:
                safe_get_logger().warning(
                    f"Tavily extraction failed for {current_url}: {e}"
                )
                raw_content = None
                text_content = ""

            if not text_content:
                continue

            pages_fetched += 1

            # Extract entities AND links
            extraction_res = await entity_extractor.extract_entities(
                text_content, current_url, raw_html=raw_content
            )

            for entry in extraction_res.get("entities", []):
                new_entities_found.append(entry)

            for link in extraction_res.get("links", []):
                discovered_links.append(link)

        # Update query record with results
        query_record["new_entities"] = len(new_entities_found)
        worker_state.query_history.append(query_record)

        novelty_rate = len(new_entities_found) / max(pages_fetched, 1)

        return {
            "worker_id": worker_state.id,
            "pages_fetched": pages_fetched,
            "entities_found": len(new_entities_found),
            "new_entities": len(new_entities_found),
            "novelty_rate": novelty_rate,
            "status": "PRODUCTIVE" if novelty_rate > 0.1 else "DECLINING",
            "extracted_data": new_entities_found,  # For orchestrator to merge into state
            "discovered_links": discovered_links,  # For orchestrator to add to queues
        }
    finally:
        await entity_extractor.close()


@activity.defn
async def update_plan(state: ResearchState) -> ResearchPlan:
    """
    Updates the research plan based on the current state.
    Calls LLM to analyze discoveries and make adaptive decisions.
    """
    safe_get_logger().info("Updating research plan based on discoveries.")

    # Extract discovered code names from entity aliases
    for entity in state.known_entities.values():
        for alias in entity.aliases:
            # Pattern: BMS-123456, ABC-1234, etc.
            if re.match(r"^[A-Z]{2,4}-\d{4,6}$", alias):
                state.discovered_code_names.add(alias)

    # Call adaptive planning
    agent = ResearchAgent()
    updated_plan = await agent.update_plan_adaptive(state)

    return updated_plan


@activity.defn
async def save_state(state: ResearchState) -> bool:
    """
    Persists the current global research state.
    Args:
        state: The ResearchState to save.
    Returns:
        True if successful.
    """
    safe_get_logger().info(f"Saving state for topic: {state.topic}")
    async with AsyncSessionLocal() as session:
        repo = ResearchRepository(session)
        await repo.save_session(state)
    return True
