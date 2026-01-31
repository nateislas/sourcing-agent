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
from backend.research.state_manager import DatabaseStateManager
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
        url_queue = [res.url for res in search_results]

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
        idx = 0
        while len(url_queue) < page_budget and idx < len(priority_links):
            url_queue.append(priority_links[idx])
            idx += 1

        # Remove added links from personal queue
        worker_state.personal_queue = [
            l for l in worker_state.personal_queue if l not in url_queue
        ]

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

            # Track domain for diversity
            domain = urlparse(current_url).netloc
            worker_state.explored_domains.add(domain)

            safe_get_logger().info(
                "Worker %s processing URL: %s (domain: %s, unique domains: %d)",
                worker_state.id,
                current_url,
                domain,
                len(worker_state.explored_domains),
            )

            # Smart Content Routing:
            # 1. Always try Crawl4AI first (handles JS, clicks buttons, finds PDFs)
            # 2. If PDF content is detected, fallback to LlamaExtract
            # 3. Otherwise use Crawl4AI's extraction results

            try:
                # Step 1: Try Crawl4AI (works for most cases)
                safe_get_logger().info("Attempting Crawl4AI for %s", current_url)

                crawl_extractor = Crawl4AIExtractor(
                    research_id=worker_state.research_id
                )
                extraction_res, ext_cost = await crawl_extractor.extract_from_html(
                    url=current_url,
                    research_query=query,  # Topic context for late binding
                )
                iteration_cost += ext_cost

                # Step 2: Check if PDF content was detected
                if extraction_res.get("is_pdf", False):
                    # Fallback to LlamaExtract for PDF content
                    pdf_path = extraction_res.get("pdf_path")
                    if pdf_path and os.path.exists(pdf_path):
                        safe_get_logger().info(
                            "PDF downloaded to %s, routing to LlamaExtract: %s",
                            pdf_path,
                            current_url,
                        )
                        try:
                            # Extract using LlamaExtract
                            (
                                pdf_extraction,
                                pdf_cost,
                            ) = await entity_extractor.extract_entities(
                                pdf_path, current_url, raw_html=None
                            )
                            extraction_res = pdf_extraction
                            iteration_cost += pdf_cost
                        finally:
                            # Cleanup temporary PDF file
                            try:
                                os.remove(pdf_path)
                            except Exception as e:
                                safe_get_logger().warning(
                                    "Failed to cleanup PDF %s: %s", pdf_path, e
                                )

                pages_fetched += 1

            except Exception as e:
                safe_get_logger().error("Extraction failed for %s: %s", current_url, e)
                continue

            # Entity Deduplication Logic
            entities_from_this_url = []
            for entry in extraction_res.get("entities", []):
                canonical = entry.get("canonical")
                if not canonical:
                    continue

                # Always add to extracted_data so we capture the evidence
                new_entities_found.append(entry)
                entities_from_this_url.append(canonical)

                # Attempt to mark as known. If it returns True, it's a NEW entity.
                # Even if it's already known, mark_entity_known will handle metadata merging.
                if await state_manager.mark_entity_known(
                    canonical, attributes=entry.get("attributes")
                ):
                    globally_new_count += 1

            # PHASE 3: Track yield for the source URL's domain
            if entities_from_this_url:
                source_domain = urlparse(current_url).netloc
                if source_domain in worker_state.link_performance:
                    worker_state.link_performance[source_domain]["entities_found"] += len(
                        entities_from_this_url
                    )

            # ================================================================
            # PHASE 1, 2, 3: Intelligent Link Filtering
            # ================================================================
            raw_links = extraction_res.get("links", [])
            
            if raw_links:
                link_filter = LinkFilter()
                
                # Phase 1: Fast Rejection (heuristics)
                filtered_links = []
                for link in raw_links:
                    # Check if already visited (global dedup)
                    if await state_manager.is_url_visited(
                        link, research_id=worker_state.research_id
                    ):
                        continue
                    
                    # Fast rejection patterns
                    should_reject, reason = link_filter.should_reject_fast(link)
                    if should_reject:
                        safe_get_logger().debug(
                            "Rejected link (Phase 1): %s - %s", link[:50], reason
                        )
                        continue
                    
                    filtered_links.append(link)
                
                # Phase 2: LLM Relevance Scoring (when queue pressure > 50%)
                current_queue_size = len(worker_state.personal_queue)
                queue_pressure = link_filter.get_queue_pressure(current_queue_size)
                
                if queue_pressure > 0.5 and filtered_links:
                    # Enable LLM scoring for high queue pressure
                    safe_get_logger().info(
                        "Queue pressure %.2f - enabling LLM link scoring for %d links",
                        queue_pressure,
                        len(filtered_links),
                    )
                    
                    link_scorer = LinkScorer(research_id=worker_state.research_id)
                    
                    # Prepare link data for scoring (we don't have anchor/context from Crawl4AI currently)
                    links_to_score = [
                        {
                            "url": link,
                            "anchor_text": "",  # TODO: Extract from Crawl4AI if available
                            "context": "",
                        }
                        for link in filtered_links
                    ]
                    
                    # Get the current query for context
                    current_query = query if isinstance(query, str) else str(query)
                    
                    # Score all links
                    scored_links = await link_scorer.score_links_batch(
                        links_to_score, research_query=current_query
                    )
                    
                    # Add scoring cost to iteration total
                    scoring_cost = sum(link["cost"] for link in scored_links)
                    iteration_cost += scoring_cost
                    
                    # Phase 3: Adaptive Learning - adjust scores based on domain performance
                    for link_data in scored_links:
                        link_url = link_data["url"]
                        base_score = link_data["score"]
                        
                        # Get domain
                        domain = urlparse(link_url).netloc
                        
                        # Apply adaptive boost/penalty
                        if domain in worker_state.link_performance:
                            perf = worker_state.link_performance[domain]
                            links_added = perf.get("links_added", 0)
                            entities_found = perf.get("entities_found", 0)
                            
                            if links_added >= 5:  # Need minimum data
                                yield_rate = entities_found / max(links_added, 1)
                                
                                if yield_rate > 0.3:
                                    # High-performing domain - boost score
                                    link_data["adjusted_score"] = min(base_score + 2, 10)
                                    link_data["boost_reason"] = f"High yield domain ({yield_rate:.2%})"
                                elif yield_rate < 0.05:
                                    # Low-performing domain - penalty
                                    link_data["adjusted_score"] = max(base_score - 2, 0)
                                    link_data["boost_reason"] = f"Low yield domain ({yield_rate:.2%})"
                                else:
                                    link_data["adjusted_score"] = base_score
                            else:
                                link_data["adjusted_score"] = base_score
                        else:
                            link_data["adjusted_score"] = base_score
                    
                    # Sort by adjusted score (descending)
                    scored_links.sort(key=lambda x: x.get("adjusted_score", x["score"]), reverse=True)
                    
                    # Take top N based on available queue space
                    available_space = link_filter.MAX_QUEUE_SIZE - current_queue_size
                    top_links = scored_links[:available_space]
                    
                    # Track domain performance (Phase 3)
                    for link_data in top_links:
                        link_url = link_data["url"]
                        domain = urlparse(link_url).netloc
                        
                        if domain not in worker_state.link_performance:
                            worker_state.link_performance[domain] = {
                                "links_added": 0,
                                "entities_found": 0,
                            }
                        
                        worker_state.link_performance[domain]["links_added"] += 1
                        discovered_links.append(link_url)
                    
                    safe_get_logger().info(
                        "Added %d/%d scored links (scores: %s)",
                        len(top_links),
                        len(scored_links),
                        [f"{l['adjusted_score']:.1f}" for l in top_links[:5]],
                    )
                else:
                    # Queue pressure low - add all filtered links up to cap
                    available_space = link_filter.MAX_QUEUE_SIZE - current_queue_size
                    
                    for link in filtered_links[:available_space]:
                        # Track domain performance (Phase 3)
                        domain = urlparse(link).netloc
                        
                        if domain not in worker_state.link_performance:
                            worker_state.link_performance[domain] = {
                                "links_added": 0,
                                "entities_found": 0,
                            }
                        
                        worker_state.link_performance[domain]["links_added"] += 1
                        discovered_links.append(link)

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
                "parameters": query_params,
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
