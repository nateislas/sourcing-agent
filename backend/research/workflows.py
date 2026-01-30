"""
Main workflow orchestration logic for Deep Research.
Implements the iterative plan-guided discovery framework.
"""

import asyncio
from datetime import timedelta
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from backend import config
    from backend.research import activities
    from backend.research.state import ResearchState, WorkerState, Entity


@workflow.defn
class DeepResearchOrchestrator:
    """
    The central workflow that orchestrates the research process.
    """

    @workflow.run
    async def run(self, topic: str) -> dict:
        """
        Executes the main research loop for a given topic.
        """
        workflow.logger.info("Starting research on: %s", topic)

        # 1. Initialize State
        state = ResearchState(topic=topic, status="running")
        state.logs.append("Workflow initialized.")
        await workflow.execute_activity(
            activities.save_state, state, start_to_close_timeout=timedelta(seconds=5)
        )

        # 2. Initial Planning
        state.plan = await workflow.execute_activity(
            activities.generate_initial_plan,
            args=[topic, state.id],
            start_to_close_timeout=timedelta(seconds=60),
        )
        state.logs.append(f"Plan generated: {state.plan.current_hypothesis}")

        # Initialize workers from plan
        for worker_cfg in state.plan.initial_workers:
            w_state = WorkerState(
                id=worker_cfg.worker_id,
                research_id=state.id,
                strategy=worker_cfg.strategy,
                queries=worker_cfg.example_queries,
                status="ACTIVE",
            )
            state.workers[w_state.id] = w_state

        await workflow.execute_activity(
            activities.save_state, state, start_to_close_timeout=timedelta(seconds=5)
        )

        # 3. Execution Loop
        max_iters = config.MAX_ITERATIONS

        while state.iteration_count < max_iters:
            workflow.logger.info("Starting iteration %s", state.iteration_count)

            # Identify active workers
            active_workers = [
                w
                for w in state.workers.values()
                if w.status in ["ACTIVE", "PRODUCTIVE", "DECLINING"]
            ]

            if not active_workers:
                state.logs.append("No active workers remaining. Stopping.")
                break

            # --- Fan-Out: Execute Workers in Parallel ---
            worker_tasks = []
            for worker in active_workers:
                worker_tasks.append(
                    workflow.execute_activity(
                        activities.execute_worker_iteration,
                        worker,
                        start_to_close_timeout=timedelta(minutes=5),
                    )
                )

            # Wait for all workers to complete this iteration
            results = await asyncio.gather(*worker_tasks)

            # --- Fan-In: Aggregate Results ---
            total_new_entities = 0
            total_pages = 0

            for res in results:
                w_id = res.get("worker_id")
                w_state = state.workers.get(w_id)
                if not w_state:
                    continue

                # Update worker metrics
                w_state.pages_fetched += res.get("pages_fetched", 0)
                w_state.entities_found += res.get("entities_found", 0)
                w_state.new_entities += res.get("new_entities", 0)
                w_state.status = res.get("status", "PRODUCTIVE")

                total_new_entities += res.get("new_entities", 0)
                total_pages += res.get("pages_fetched", 0)

                # Update Personal Queue
                # 1. Remove consumed URLs (FIFO)
                consumed_urls = res.get("consumed_urls", [])
                if consumed_urls:
                    w_state.personal_queue = [
                        url
                        for url in w_state.personal_queue
                        if url not in consumed_urls
                    ]

                # 2. Add Discovered Links
                for link in res.get("discovered_links", []):
                    if link not in state.visited_urls:
                        state.visited_urls.add(link)
                        w_state.personal_queue.append(link)

                # Merge entities into global state
                for item in res.get("extracted_data", []):
                    canonical = item.get("canonical")
                    if not canonical:
                        workflow.logger.warning(
                            "Skipping entity with missing canonical name"
                        )
                        continue

                    if canonical not in state.known_entities:
                        # Create new entity WITH aliases and evidence
                        new_entity = Entity(
                            canonical_name=canonical,
                            mention_count=1,
                            drug_class=item.get("drug_class"),
                            clinical_phase=item.get("clinical_phase"),
                        )
                        new_entity.aliases.add(item["alias"])
                        new_entity.evidence.extend(item["evidence"])
                        state.known_entities[canonical] = new_entity
                    else:
                        # Update existing entity
                        entity = state.known_entities[canonical]
                        entity.mention_count += 1
                        if not entity.drug_class:
                            entity.drug_class = item.get("drug_class")
                        if not entity.clinical_phase:
                            entity.clinical_phase = item.get("clinical_phase")
                        
                        # Add new aliases and evidence to existing entity
                        entity.aliases.add(item["alias"])
                        entity.evidence.extend(item["evidence"])

            state.iteration_count += 1
            global_novelty = total_new_entities / max(total_pages, 1)
            log_msg = (
                "Iteration %s completed. Found %d new entities. Global Novelty: %.2f%%"
            )
            state.logs.append(
                log_msg
                % (state.iteration_count, total_new_entities, global_novelty * 100)
            )
            workflow.logger.info(
                log_msg,
                state.iteration_count,
                total_new_entities,
                global_novelty * 100,
            )

            # --- Check Stopping Criteria ---
            if global_novelty < 0.05 and state.iteration_count > 1:
                state.logs.append(
                    "Stopping: Low novelty detected (%.2f%%)" % (global_novelty * 100)
                )
                break

            # --- Adaptive Planning ---
            state.plan = await workflow.execute_activity(
                activities.update_plan,
                state,
                start_to_close_timeout=timedelta(minutes=2),
            )

            # Handle worker kills
            for worker_id in state.plan.workers_to_kill:
                if worker_id in state.workers:
                    state.workers[worker_id].status = "DEAD_END"
                    state.logs.append("Killed worker %s (exhausted)" % worker_id)

            # Handle worker spawns
            for worker_cfg in state.plan.initial_workers:
                if worker_cfg.worker_id not in state.workers:
                    w_state = WorkerState(
                        id=worker_cfg.worker_id,
                        research_id=state.id,
                        strategy=worker_cfg.strategy,
                        queries=worker_cfg.example_queries,
                        status="ACTIVE",
                    )
                    state.workers[w_state.id] = w_state
                    state.logs.append("Spawned new worker %s" % w_state.id)

            # Update queries for existing workers
            for worker_id, new_queries in state.plan.updated_queries.items():
                if worker_id in state.workers:
                    state.workers[worker_id].queries = new_queries

            # Save state after iteration
            await workflow.execute_activity(
                activities.save_state,
                state,
                start_to_close_timeout=timedelta(seconds=5),
            )

        # 4. Verification Phase
        state.status = "verification_pending"
        state.logs.append(f"Starting verification phase for {len(state.known_entities)} entities.")
        await workflow.execute_activity(
            activities.save_state, state, start_to_close_timeout=timedelta(seconds=5)
        )

        verification_tasks = []
        constraints = state.plan.query_analysis
        for entity in state.known_entities.values():
            verification_tasks.append(
                workflow.execute_activity(
                    activities.verify_entity,
                    args=[entity.model_dump(), constraints],
                    start_to_close_timeout=timedelta(minutes=2),
                )
            )

        if verification_tasks:
            verification_results = await asyncio.gather(*verification_tasks)
            
            # Update state with verification results
            uncertain_entities = []
            for res in verification_results:
                canonical = res.get("canonical_name")
                if canonical in state.known_entities:
                    ent = state.known_entities[canonical]
                    ent.verification_status = res.get("status", "UNCERTAIN")
                    ent.rejection_reason = res.get("rejection_reason")
                    ent.confidence_score = res.get("confidence", 0.0)
                    
                    if ent.verification_status == "UNCERTAIN":
                        uncertain_entities.append(ent)

            # 5. Gap Filling Phase (Optional)
            if uncertain_entities:
                state.logs.append(f"Found {len(uncertain_entities)} uncertain entities. Starting gap analysis.")
                gap_filling_tasks = []
                for ent in uncertain_entities:
                    # Analyze gaps to get queries
                    queries = await workflow.execute_activity(
                        activities.analyze_gaps,
                        args=[ent.model_dump(), {"status": "UNCERTAIN", "missing_fields": []}],
                        start_to_close_timeout=timedelta(seconds=30)
                    )
                    
                    if queries:
                        # Create a targeted worker iteration for gap filling
                        gap_worker = WorkerState(
                            id=f"gap-fill-{ent.canonical_name[:20]}",
                            research_id=state.id,
                            strategy="gap_filling",
                            queries=queries,
                            status="ACTIVE"
                        )
                        gap_filling_tasks.append(
                            workflow.execute_activity(
                                activities.execute_worker_iteration,
                                gap_worker,
                                start_to_close_timeout=timedelta(minutes=5)
                            )
                        )
                
                if gap_filling_tasks:
                    await asyncio.gather(*gap_filling_tasks)
                    state.logs.append("Gap filling phase complete.")

        state.status = "completed"
        await workflow.execute_activity(
            activities.save_state, state, start_to_close_timeout=timedelta(seconds=5)
        )

        # Return summary dictionary for Temporal UI visibility
        return {
            "topic": state.topic,
            "entities_found": len(state.known_entities),
            "iterations": state.iteration_count,
            "status": state.status,
        }
