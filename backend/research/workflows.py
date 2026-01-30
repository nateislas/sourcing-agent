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
        workflow.logger.info(f"Starting research on: {topic}")

        # 1. Initialize State
        state = ResearchState(topic=topic, status="running")
        state.logs.append("Workflow initialized.")
        await workflow.execute_activity(
            activities.save_state, state, start_to_close_timeout=timedelta(seconds=5)
        )

        # 2. Initial Planning
        state.plan = await workflow.execute_activity(
            activities.generate_initial_plan,
            topic,
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
            workflow.logger.info(f"Starting iteration {state.iteration_count}")

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

                # Process Discovered Links
                for link in res.get("discovered_links", []):
                    if link not in state.visited_urls:
                        state.visited_urls.add(link)
                        w_state.personal_queue.append(link)

                # Merge entities into global state
                for item in res.get("extracted_data", []):
                    canonical = item["canonical"]
                    if canonical not in state.known_entities:
                        state.known_entities[canonical] = Entity(
                            canonical_name=canonical,
                            mention_count=1,
                            drug_class=item.get("drug_class"),
                            clinical_phase=item.get("clinical_phase"),
                        )
                    else:
                        entity = state.known_entities[canonical]
                        entity.mention_count += 1
                        if not entity.drug_class:
                            entity.drug_class = item.get("drug_class")
                        if not entity.clinical_phase:
                            entity.clinical_phase = item.get("clinical_phase")

                    # Update aliases and evidence
                    entity = state.known_entities[canonical]
                    entity.aliases.add(item["alias"])
                    entity.evidence.extend(item["evidence"])

            state.iteration_count += 1
            global_novelty = total_new_entities / max(total_pages, 1)
            log_msg = f"Iteration {state.iteration_count} completed. Found {total_new_entities} new entities. Global Novelty: {global_novelty:.2%}"
            state.logs.append(log_msg)
            workflow.logger.info(log_msg)

            # --- Check Stopping Criteria ---
            if global_novelty < 0.05 and state.iteration_count > 1:
                state.logs.append(
                    f"Stopping: Low novelty detected ({global_novelty:.2%})"
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
                    state.logs.append(f"Killed worker {worker_id} (exhausted)")

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
                    state.logs.append(f"Spawned new worker {w_state.id}")

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
