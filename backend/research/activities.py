"""
Temporal activities for the Deep Research Application.
Handles external interactions like searching and fetching content.
"""

import os
import re
import logging
from typing import Optional
from temporalio import activity
from backend.db.connection import AsyncSessionLocal
from backend.db.repository import ResearchRepository
from backend.research.agent import ResearchAgent
from backend.research.state import ResearchState, ResearchPlan, WorkerState
from backend.research.client_search import PerplexitySearchClient
from backend.research.extraction import EntityExtractor
from backend.research.extraction import EntityExtractor
from backend.research.state_manager import DatabaseStateManager
from backend.research.verification import VerificationAgent, VerificationResult



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
    safe_get_logger().info("Generating initial plan for: %s", topic)
    agent = ResearchAgent()
    return await agent.generate_initial_plan(topic, research_id=research_id)


@activity.defn
async def execute_worker_iteration(worker_state: WorkerState) -> dict:
    """
    Executes a single iteration for a specific worker.
    Includes: Search -> Fetch -> Extract -> Queue Management.
    """
    safe_get_logger().info(
        "Worker %s executing iteration with strategy %s",
        worker_state.id,
        worker_state.strategy,
    )

    # Initialize clients
    perp_client = PerplexitySearchClient(research_id=worker_state.research_id)
    entity_extractor = EntityExtractor(research_id=worker_state.research_id)
    state_manager = DatabaseStateManager()

    try:
        # Metrics for this iteration
        pages_fetched = 0
        new_entities_found = []  # Holds ALL extracted entities (evidence)
        discovered_links = []
        globally_new_count = 0  # Metric: truly new entities

        # 1. Search Phase
        # Use round-robin query selection based on iteration
        page_budget = int(os.getenv("WORKER_PAGE_BUDGET", "50"))
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

            # --- Global Deduplication Check ---
            is_visited = await state_manager.is_url_visited(
                current_url, research_id=worker_state.research_id
            )
            if is_visited:
                safe_get_logger().info("Skipping visited URL: %s", current_url)
                continue

            # Mark visited immediately (optimistic concurrency)
            await state_manager.mark_url_visited(
                current_url, research_id=worker_state.research_id
            )

            safe_get_logger().info(
                "Worker %s processing URL: %s", worker_state.id, current_url
            )

            # Smart Content Routing:
            # 1. Always try Crawl4AI first (handles JS, clicks buttons, finds PDFs)
            # 2. If PDF content is detected, fallback to LlamaExtract
            # 3. Otherwise use Crawl4AI's extraction results

            try:
                # Step 1: Try Crawl4AI (works for most cases)
                safe_get_logger().info("Attempting Crawl4AI for %s", current_url)
                from backend.research.extraction_crawl4ai import Crawl4AIExtractor

                crawl_extractor = Crawl4AIExtractor(
                    research_id=worker_state.research_id
                )
                extraction_res = await crawl_extractor.extract_from_html(
                    url=current_url,
                    research_query=query,  # Topic context for late binding
                )

                # Step 2: Check if PDF content was detected
                if extraction_res.get("is_pdf", False):
                    # Fallback to LlamaExtract for PDF content
                    pdf_path = extraction_res.get("pdf_path")
                    if pdf_path and os.path.exists(pdf_path):
                        safe_get_logger().info(
                            "PDF downloaded to %s, routing to LlamaExtract: %s", pdf_path, current_url
                        )
                        try:
                            # Extract using LlamaExtract
                            pdf_extraction = await entity_extractor.extract_entities(
                                pdf_path, current_url, raw_html=None
                            )
                            extraction_res = pdf_extraction
                        finally:
                            # Cleanup temporary PDF file
                            try:
                                os.remove(pdf_path)
                            except Exception as e:
                                safe_get_logger().warning("Failed to cleanup PDF %s: %s", pdf_path, e)

                pages_fetched += 1

            except Exception as e:
                safe_get_logger().error("Extraction failed for %s: %s", current_url, e)
                continue

            # Entity Deduplication Logic
            for entry in extraction_res.get("entities", []):
                canonical = entry.get("canonical")
                if not canonical:
                    continue

                # Always add to extracted_data so we capture the evidence
                new_entities_found.append(entry)

                # Attempt to mark as known. If it returns True, it's a NEW entity.
                # Even if it's already known, mark_entity_known will handle metadata merging.
                if await state_manager.mark_entity_known(
                    canonical, attributes=entry.get("attributes")
                ):
                    globally_new_count += 1

            # Phase 1 Link Filtering
            for link in extraction_res.get("links", []):
                # Check visited before adding to discovered list
                if not await state_manager.is_url_visited(
                    link, research_id=worker_state.research_id
                ):
                    discovered_links.append(link)

        # Update query record with results
        query_record["new_entities"] = globally_new_count
        worker_state.query_history.append(query_record)

        novelty_rate = globally_new_count / max(pages_fetched, 1)

        return {
            "worker_id": worker_state.id,
            "pages_fetched": pages_fetched,
            "entities_found": len(new_entities_found),  # Total extracted this run
            "new_entities": globally_new_count,  # Globally new
            "novelty_rate": novelty_rate,
            "status": "PRODUCTIVE" if novelty_rate > 0.1 else "DECLINING",
            "extracted_data": new_entities_found,  # For orchestrator to merge into state
            "discovered_links": discovered_links,  # For orchestrator to add to queues
            "consumed_urls": url_queue,  # URLs processed in this iteration (from search + personal queue)
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
    safe_get_logger().info("Saving state for topic: %s", state.topic)
    async with AsyncSessionLocal() as session:
        repo = ResearchRepository(session)
        await repo.save_session(state)
    return True


@activity.defn
async def verify_entity(entity_data: dict, constraints: dict) -> dict:
    """
    Verifies a single entity against constraints using the VerificationAgent.
    Args:
        entity_data: Dict representation of the Entity object.
        constraints: Dictionary of hard constraints from the plan.
    Returns:
        Dict representation of VerificationResult.
    """
    safe_get_logger().info("Verifying entity: %s", entity_data.get("canonical_name"))

    # Reconstruct Entity object from dict
    # We use Entity.model_validate or similar if Pydantic v2, or just constructor
    from backend.research.state import Entity
    entity = Entity(**entity_data)

    agent = VerificationAgent()
    result = await agent.verify_entity(entity, constraints)

    return result.model_dump()


@activity.defn
async def analyze_gaps(entity_data: dict, verification_result: dict) -> list[str]:
    """
    Analyzes verification results to generate gap-filling search queries.
    Args:
        entity_data: Dict representation of the Entity.
        verification_result: Dict representation of VerificationResult.
    Returns:
        List of specific search queries to fill the gaps.
    """
    canonical_name = entity_data.get("canonical_name")
    missing_fields = verification_result.get("missing_fields", [])
    
    queries = []
    
    if "owner" in missing_fields:
        queries.append(f'"{canonical_name}" developer owner company')
        queries.append(f'who developed "{canonical_name}"')
        
    if "product_stage" in missing_fields or "clinical_phase" in missing_fields:
        queries.append(f'"{canonical_name}" clinical trial stage phase')
        
    if "indication" in missing_fields:
        queries.append(f'"{canonical_name}" therapeutic indication disease')
        
    safe_get_logger().info("Generated %d gap-filling queries for %s", len(queries), canonical_name)
    return queries

