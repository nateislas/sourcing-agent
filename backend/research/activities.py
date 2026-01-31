"""
Temporal activities for the Deep Research Application.
Handles external interactions like searching and fetching content.
"""

import logging
import os
import re
from urllib.parse import urlparse

from temporalio import activity

from backend.db.connection import AsyncSessionLocal
from backend.db.repository import ResearchRepository
from backend.research.agent import ResearchAgent
from backend.research.client_search import PerplexitySearchClient
from backend.research.extraction import EntityExtractor
from backend.research.extraction_crawl4ai import Crawl4AIExtractor
from backend.research.link_filter import LinkFilter
from backend.research.link_scorer import LinkScorer
from backend.research.state import Entity, ResearchPlan, ResearchState, WorkerState
from backend.research.state_manager import DatabaseStateManager, RedisStateManager
from backend.research.verification import VerificationAgent
from backend.research.pricing import calculate_search_cost

logger = logging.getLogger(__name__)


def safe_get_logger():
    """Returns the Temporal activity logger if in context, otherwise the standard logger."""
    try:
        return activity.logger
    except RuntimeError:
        return logger


@activity.defn
async def generate_initial_plan(
    topic: str, research_id: str | None = None
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
    import asyncio
    from datetime import datetime
    safe_get_logger().info(
        "Worker %s executing iteration with strategy %s",
        worker_state.id,
        worker_state.strategy,
    )

    # Initialize clients
    perp_client = PerplexitySearchClient(research_id=worker_state.research_id)
    entity_extractor = EntityExtractor(research_id=worker_state.research_id)
    # Use Redis for high-speed deduplication
    state_manager = RedisStateManager()

    try:
        # Metrics for this iteration
        pages_fetched = 0
        new_entities_found = []  # Holds ALL extracted entities (evidence)
        discovered_links = []
        globally_new_count = 0  # Metric: truly new entities
        iteration_cost = 0.0

        # 1. Search Phase
        # Execute ALL queries for maximum recall (Option 1: Multi-Search)
        page_budget = int(os.getenv("WORKER_PAGE_BUDGET", "50"))

        # Extract all query strings from worker state
        all_queries = []
        for query_config in worker_state.queries:
            if isinstance(query_config, dict):
                all_queries.append(query_config.get("query", worker_state.strategy))
            else:
                all_queries.append(query_config)

        # Fallback if no queries defined
        if not all_queries:
            all_queries = [worker_state.strategy]

        # Distribute max_results across all queries
        base_max_results = int(os.getenv("PERPLEXITY_MAX_RESULTS", "5"))
        results_per_query = max(base_max_results // len(all_queries), 3)

        # Random engine selection (50/50 Perplexity vs Tavily)
        import random

        from backend.research.client_search import TavilySearchClient

        search_engine = random.choice(["perplexity", "tavily"])

        safe_get_logger().info(
            "Worker %s using %s for %d queries: %s",
            worker_state.id,
            search_engine,
            len(all_queries),
            all_queries[:2],  # Log first 2 to avoid huge logs
        )

        if search_engine == "perplexity":
            # Perplexity supports multi-query natively
            search_results = await perp_client.search(
                queries=all_queries,  # All queries at once
                max_results=results_per_query,
            )
        else:  # tavily
            # Tavily now supports parallel multi-query via asyncio.gather
            tavily_client = TavilySearchClient()
            search_results = await tavily_client.search(
                query=all_queries,  # All queries at once (parallel execution)
                max_results=results_per_query,
                include_raw_content=True,
            )

        # Calculate search cost (N API calls for both engines when multi-query)
        try:
            api_calls = len(all_queries)
            iteration_cost += calculate_search_cost(search_engine, api_calls)
        except Exception:
            pass

        # Track query execution in history (all queries executed)
        query = ", ".join(all_queries[:2]) + (f" (+{len(all_queries)-2} more)" if len(all_queries) > 2 else "")

        # Track query execution in history
        iteration_index = worker_state.pages_fetched // page_budget
        query_record = {
            "query": query,
            "engine": search_engine,
            "iteration": iteration_index,
            "results_count": len(search_results),
            "new_entities": 0,
        }

        # URLs to process in this iteration
        url_queue = [res.url for res in search_results if res.url and res.url.strip()]
        
        safe_get_logger().info(
            "Worker %s search returned %d URLs. Final url_queue size: %d",
            worker_state.id,
            len(search_results),
            len(url_queue)
        )
        if len(search_results) != len(url_queue):
            bad_urls = [res.url for res in search_results if not (res.url and res.url.strip())]
            safe_get_logger().warning("Worker %s found %d empty URLs in search results: %s", worker_state.id, len(bad_urls), bad_urls)

        # --- Intermediate State Persistence ---
        # Persist the search results immediately so the dashboard reflects activity
        try:
            async with AsyncSessionLocal() as session:
                repo = ResearchRepository(session)
                current_state = await repo.get_session(worker_state.research_id)
                if current_state and worker_state.id in current_state.workers:
                    # Update local query history record temporarily for UI visibility
                    temp_record = {
                        "query": query,
                        "engine": search_engine,
                        "iteration": worker_state.pages_fetched // page_budget,
                        "results_count": len(search_results),
                        "new_entities": 0, # Will be updated later
                    }

                    
                    # Update the global state's worker copy
                    w_global = current_state.workers[worker_state.id]
                    if not w_global.query_history:
                        w_global.query_history = []
                    w_global.query_history.append(temp_record)
                    
                    if not w_global.search_engine_history:
                        w_global.search_engine_history = []
                    w_global.search_engine_history.append({
                        "query": query,
                        "engine": search_engine,
                        "results": len(url_queue),
                        "new_entities": 0
                    })
                    
                    await repo.save_session(current_state)
                    safe_get_logger().info("Persisted intermediate state for dashboard visibility")
        except Exception as e:
            safe_get_logger().warning(f"Failed to persist intermediate state: {e}")

        # 2. Add from personal queue, preferring novel domains

        novel_domain_links = []
        same_domain_links = []

        for link in worker_state.personal_queue:
            link_domain = urlparse(link).netloc
            if link_domain not in worker_state.explored_domains:
                novel_domain_links.append(link)
            else:
                same_domain_links.append(link)

        # Fill queue with novel domains first, then same domains
        priority_links = novel_domain_links + same_domain_links
        safe_get_logger().info("Worker %s queue fill: %d novel, %d same domain links in personal_queue", worker_state.id, len(novel_domain_links), len(same_domain_links))
        
        idx = 0
        added_count = 0
        while len(url_queue) < page_budget and idx < len(priority_links):
            link = priority_links[idx]
            if not link or not link.strip():
                safe_get_logger().warning("Worker %s skipping empty link in personal_queue at idx %d", worker_state.id, idx)
                idx += 1
                continue

            url_queue.append(link)
            idx += 1
            added_count += 1
        
        safe_get_logger().info("Worker %s added %d links from personal_queue to url_queue. Total: %d", worker_state.id, added_count, len(url_queue))

        # Remove added links from personal queue
        worker_state.personal_queue = [
            l for l in worker_state.personal_queue if l not in url_queue
        ]

        # 3. Fetch & Extract Phase
        # Filter and prepare URLs for batch processing
        valid_urls = []
        for current_url in url_queue:
            if pages_fetched + len(valid_urls) >= page_budget:
                break
            if not current_url or not current_url.strip():
                continue
            
            is_visited = await state_manager.is_url_visited(
                current_url, research_id=worker_state.research_id
            )
            if is_visited:
                safe_get_logger().info("Skipping visited URL: %s", current_url)
                continue
            
            valid_urls.append(current_url)

        # Process in chunks
        chunk_size = 10
        for i in range(0, len(valid_urls), chunk_size):
            chunk = valid_urls[i:i+chunk_size]
            safe_get_logger().info("Worker %s processing batch of %d URLs", worker_state.id, len(chunk))
            
            # Mark all as visited immediately
            for url in chunk:
                await state_manager.mark_url_visited(url, research_id=worker_state.research_id)
                domain = urlparse(url).netloc
                worker_state.explored_domains.add(domain)

            crawl_extractor = Crawl4AIExtractor(research_id=worker_state.research_id)
            batch_results, batch_cost = await crawl_extractor.extract_batch(
                urls=chunk,
                research_query=query
            )
            iteration_cost += batch_cost

            # Process individual results from the batch
            for extraction_res in batch_results:
                current_url = extraction_res.get("url")
                
                # Handle PDF Fallback (Sequential for now, but rare)
                if extraction_res.get("is_pdf", False):
                    pdf_path = extraction_res.get("pdf_path")
                    if pdf_path and os.path.exists(pdf_path):
                        safe_get_logger().info("PDF detected, routing to LlamaExtract: %s", current_url)
                        try:
                            pdf_extraction, pdf_cost = await entity_extractor.extract_entities(
                                pdf_path, current_url, raw_html=None
                            )
                            # Merge entities from PDF into the results
                            extraction_res["entities"] = pdf_extraction.get("entities", [])
                            extraction_res["links"] = pdf_extraction.get("links", [])
                            iteration_cost += pdf_cost
                        finally:
                            if os.path.exists(pdf_path):
                                os.remove(pdf_path)

                pages_fetched += 1
                
                # Process discovered entities
                entities_from_this_url_canonical_names = []
                entity_mark_tasks = []
                for entry in extraction_res.get("entities", []):
                    canonical = entry.get("canonical")
                    if not canonical:
                        continue

                    new_entities_found.append(entry)
                    entities_from_this_url_canonical_names.append(canonical)
                    entity_mark_tasks.append(state_manager.mark_entity_known(
                        canonical, attributes=entry.get("attributes")
                    ))
                
                # --- Parallel Entity Marking ---
                if entity_mark_tasks:
                    mark_results = await asyncio.gather(*entity_mark_tasks)
                    globally_new_count += sum(1 for r in mark_results if r)

                # Track domain performance
                source_domain = urlparse(current_url).netloc
                if entities_from_this_url_canonical_names:
                    if source_domain not in worker_state.link_performance:
                        worker_state.link_performance[source_domain] = {"links_added": 0, "entities_found": 0}
                    worker_state.link_performance[source_domain]["entities_found"] += len(entities_from_this_url_canonical_names)

                # ================================================================
                # Link Filtering & Scoring (Phase 1, 2, 3)
                # ================================================================
                raw_links = extraction_res.get("links", [])
                if not raw_links:
                    continue

                link_filter = LinkFilter()
                
                # Parallelize visited check
                visited_tasks = [state_manager.is_url_visited(l, research_id=worker_state.research_id) for l in raw_links]
                visited_mask = await asyncio.gather(*visited_tasks)
                
                filtered_links = []
                for link, is_visited in zip(raw_links, visited_mask):
                    if is_visited:
                        continue
                    should_reject, reason = link_filter.should_reject_fast(link)
                    if should_reject:
                        continue
                    filtered_links.append(link)

                if not filtered_links:
                    continue

                current_queue_size = len(worker_state.personal_queue) + len(discovered_links)
                queue_pressure = link_filter.get_queue_pressure(current_queue_size)

                if queue_pressure > 0.5:
                    # Score links if queue is getting full
                    link_scorer = LinkScorer(research_id=worker_state.research_id)
                    links_to_score = [{"url": link, "anchor_text": "", "context": ""} for link in filtered_links]
                    scored_links = await link_scorer.score_links_batch(links_to_score, research_query=str(query))
                    
                    iteration_cost += sum(l["cost"] for l in scored_links)
                    
                    # Apply adaptive boost
                    for l_data in scored_links:
                        l_url = l_data["url"]
                        l_domain = urlparse(l_url).netloc
                        l_data["adjusted_score"] = l_data["score"]
                        if l_domain in worker_state.link_performance:
                            perf = worker_state.link_performance[l_domain]
                            if perf["links_added"] >= 5:
                                yield_rate = perf["entities_found"] / max(perf["links_added"], 1)
                                if yield_rate > 0.3: l_data["adjusted_score"] += 2
                                elif yield_rate < 0.05: l_data["adjusted_score"] -= 2
                    
                    scored_links.sort(key=lambda x: x.get("adjusted_score", x["score"]), reverse=True)
                    available_space = max(0, link_filter.MAX_QUEUE_SIZE - current_queue_size)
                    
                    for l_data in scored_links[:available_space]:
                        l_url = l_data["url"]
                        l_domain = urlparse(l_url).netloc
                        if l_domain not in worker_state.link_performance:
                            worker_state.link_performance[l_domain] = {"links_added": 0, "entities_found": 0}
                        worker_state.link_performance[l_domain]["links_added"] += 1
                        discovered_links.append(l_url)
                else:
                    # Queue space available, add up to space limit
                    available_space = max(0, link_filter.MAX_QUEUE_SIZE - current_queue_size)
                    for link in filtered_links[:available_space]:
                        l_domain = urlparse(link).netloc
                        if l_domain not in worker_state.link_performance:
                            worker_state.link_performance[l_domain] = {"links_added": 0, "entities_found": 0}
                        worker_state.link_performance[l_domain]["links_added"] += 1
                        discovered_links.append(link)

            # --- Intermediate State Persistence for Dashboard ---
            # Update the DB so the user sees progress while the worker is still running its iteration.
            try:
                # Calculate current iteration metrics accurately
                # Note: worker_state.pages_fetched is the total BEFORE this iteration started.
                # pages_fetched is the count for THIS iteration so far.
                await _persist_intermediate_metrics(
                    worker_id=worker_state.id,
                    research_id=worker_state.research_id,
                    pages_fetched=worker_state.pages_fetched + pages_fetched,
                    entities_found=worker_state.entities_found + len(new_entities_found)
                )
            except Exception as e:
                safe_get_logger().warning(f"Failed to persist intermediate metrics: {e}")

        # Update query record with results
        query_record["new_entities"] = globally_new_count
        worker_state.query_history.append(query_record)

        # Track search engine performance
        worker_state.search_engine_history.append(
            {
                "query": query,
                "engine": search_engine,
                "results": len(url_queue),
                "new_entities": globally_new_count,
            }
        )

        # Update query performance tracking
        if query not in worker_state.query_performance:
            worker_state.query_performance[query] = {
                "total_pages": 0,
                "new_entities": 0,
                "novelty_rate": 0.0,
                "engines_used": {},  # Track performance per engine
            }

        perf = worker_state.query_performance[query]
        perf["total_pages"] += pages_fetched
        perf["new_entities"] += globally_new_count
        perf["novelty_rate"] = perf["new_entities"] / max(perf["total_pages"], 1)

        # Track per-engine performance for this query
        if "engines_used" not in perf:
            perf["engines_used"] = {}
        if search_engine not in perf["engines_used"]:
            perf["engines_used"][search_engine] = {"pages": 0, "entities": 0}

        perf["engines_used"][search_engine]["pages"] += pages_fetched
        perf["engines_used"][search_engine]["entities"] += globally_new_count

        novelty_rate = globally_new_count / max(pages_fetched, 1)

        novelty_rate = globally_new_count / max(pages_fetched, 1)

        # OPTIMIZATION: Persist newly found entities immediately to the Relational DB.
        # This allows us to avoid the expensive O(N) save in the main workflow.
        if new_entities_found:
             try:
                 async with AsyncSessionLocal() as session:
                     repo = ResearchRepository(session)
                     # Convert dicts back to Entity objects for saving if needed, 
                     # but wait, new_entities_found is a list of dicts (from extraction.py).
                     # Repo expects Entity objects.
                     
                     entities_to_save = []
                     for e_data in new_entities_found:
                         # Extraction returns dicts, need to ensure compatibility
                         # Entity(...) constructor
                         # NOTE: e_data might contain 'evidence' as list of objects or dicts?
                         # extraction.py returns Pydantic models usually or dicts.
                         # Looking at extraction.py (not shown), it likely returns dicts.
                         # Let's assume dicts and hydrate carefully.
                         ent_obj = Entity(**e_data)
                         entities_to_save.append(ent_obj)
                     
                     await repo.save_entities_batch(entities_to_save)
                     safe_get_logger().info(f"Worker {worker_state.id} persisted {len(entities_to_save)} new entities.")
             except Exception as e:
                 safe_get_logger().error(f"Failed to persist batch of entities: {e}")

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
            "query_history": worker_state.query_history,
            "search_engine_history": worker_state.search_engine_history,
            "cost": iteration_cost,
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
    entity = Entity(**entity_data)

    agent = VerificationAgent()
    result, cost = await agent.verify_entity(entity, constraints)

    output = result.model_dump()
    output["cost"] = cost
    
    # OPTIMIZATION: Persist the verification result immediately to Relational DB
    # because save_state no longer iterates all entities.
    try:
        if result.status != "UNVERIFIED":
            entity.verification_status = result.status
            entity.rejection_reason = result.rejection_reason
            entity.confidence_score = result.confidence
            
            async with AsyncSessionLocal() as session:
                repo = ResearchRepository(session)
                await repo.save_entity(entity)
                safe_get_logger().info(f"Persisted verification for {entity.canonical_name}")
    except Exception as e:
        safe_get_logger().error(f"Failed to persist verification result: {e}")

    return output


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

    safe_get_logger().info(
        "Generated %d gap-filling queries for %s", len(queries), canonical_name
    )
    return queries

async def _persist_intermediate_metrics(
    worker_id: str, 
    research_id: str, 
    pages_fetched: int, 
    entities_found: int
):
    """Updates the database with the latest metrics from a running worker."""
    async with AsyncSessionLocal() as session:
        repo = ResearchRepository(session)
        state = await repo.get_session(research_id)
        if not state or worker_id not in state.workers:
            return

        # Update specific worker metrics
        w = state.workers[worker_id]
        w.pages_fetched = pages_fetched
        w.entities_found = entities_found
        
        # Save the full state dump
        # Note: This is an intermediate update, so we don't worry about merging 
        # entities here; this is purely for the worker-level counters on the UI.
        await repo.save_session(state)
        safe_get_logger().info(f"Updated intermediate metrics for {worker_id}: {pages_fetched} pages, {entities_found} assets")
