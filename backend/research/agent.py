"""
Research Agent (The "Brain").
Handles the intelligent planning and decision making logic using LLMs.
"""

import os
import json
import re
import logging
from typing import Optional

from llama_index.core.llms import ChatMessage
from backend.research.state import (
    ResearchPlan,
    ResearchState,
    InitialWorkerStrategy,
    Gap,
)
from backend.research.workflow_planning import InitialPlanningWorkflow
from backend.research.llm_factory import get_llm
from backend.research.prompts import ADAPTIVE_PLANNING_PROMPT
from backend.research.logging_utils import get_session_logger, log_api_call

logger = logging.getLogger(__name__)


class ResearchAgent:
    """
    The intelligent agent responsible for planning and guiding the research process.
    Uses LlamaIndex Workflows for complex reasoning steps.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.model_name = model_name or os.getenv(
            "RESEARCH_MODEL", "models/gemini-3-flash-preview"
        )
        self.timeout = timeout or int(os.getenv("RESEARCH_TIMEOUT", 60))

    async def generate_initial_plan(
        self, topic: str, research_id: Optional[str] = None
    ) -> ResearchPlan:
        """
        Generates the initial research plan using the planning workflow.
        """
        logger.info(f"Generating initial plan for topic: {topic}")

        # Setup workflow with research_id for logging
        planning_workflow = InitialPlanningWorkflow(
            model_name=self.model_name,
            timeout=self.timeout,
            verbose=True,
            research_id=research_id,
        )

        try:
            handler = planning_workflow.run(topic=topic)
            result = await handler

            if isinstance(result, ResearchPlan):
                return result

            logger.error(
                f"Unexpected result type from planning workflow: {type(result)}"
            )
            raise ValueError("Invalid plan generated")

        except Exception as e:
            logger.error(f"Planning workflow failed: {e}")
            # Fallback
            return ResearchPlan(
                current_hypothesis=f"Exploring {topic} (Fallback due to error)",
                findings_summary="Error in planning workflow",
                gaps=[],
                next_steps=["broad_search"],
            )

    async def update_plan_adaptive(self, state: "ResearchState") -> ResearchPlan:
        """
        Analyzes current state and updates plan adaptively.

        Args:
            state: Current research state with discoveries and worker metrics

        Returns:
            Updated ResearchPlan with new workers, killed workers, and evolved queries
        """
        logger.info(f"Running adaptive planning for iteration {state.iteration_count}")

        # Format worker metrics with query history
        worker_metrics = []
        for worker in state.workers.values():
            worker_metrics.append(
                {
                    "id": worker.id,
                    "strategy": worker.strategy,
                    "status": worker.status,
                    "pages_fetched": worker.pages_fetched,
                    "entities_found": worker.entities_found,
                    "new_entities": worker.new_entities,
                    "novelty_rate": worker.new_entities / max(worker.pages_fetched, 1),
                    "query_history": worker.query_history,
                }
            )

        # Format recent entities (last 10)
        recent_entities = []
        for name, entity in list(state.known_entities.items())[-10:]:
            recent_entities.append(
                {
                    "name": name,
                    "drug_class": entity.drug_class,
                    "clinical_phase": entity.clinical_phase,
                    "mentions": entity.mention_count,
                    "aliases": list(entity.aliases)[:5],  # First 5 aliases
                }
            )

        # Build prompt
        prompt = ADAPTIVE_PLANNING_PROMPT.format(
            iteration=state.iteration_count,
            total_entities=len(state.known_entities),
            active_workers=len(
                [
                    w
                    for w in state.workers.values()
                    if w.status in ["ACTIVE", "PRODUCTIVE", "DECLINING"]
                ]
            ),
            worker_metrics=json.dumps(worker_metrics, indent=2),
            recent_entities=json.dumps(recent_entities, indent=2),
            query_constraints=json.dumps(state.plan.query_analysis, indent=2),
        )

        # Call LLM
        llm = get_llm(model_name=self.model_name)
        messages = [ChatMessage(role="user", content=prompt)]

        try:
            response = await llm.achat(messages)
            response_text = response.message.content

            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(
                r"```json\s*(\{.*?\})\s*```", response_text, re.DOTALL
            )
            if json_match:
                response_text = json_match.group(1)

            adaptive_plan = json.loads(response_text)

            # Log adaptive planning decision
            session_logger = get_session_logger(state.id)
            log_api_call(
                session_logger,
                "gemini",
                "adaptive_planning",
                {"iteration": state.iteration_count, "state_summary": prompt},
                adaptive_plan,
            )

            # Update existing plan with adaptive decisions
            updated_plan = state.plan

            # Add new workers from spawn decisions
            for new_worker in adaptive_plan["decisions"].get("spawn_workers", []):
                updated_plan.initial_workers.append(
                    InitialWorkerStrategy(
                        worker_id=new_worker["worker_id"],
                        strategy=new_worker["strategy"],
                        strategy_description=new_worker["strategy_description"],
                        example_queries=new_worker["queries"],
                    )
                )

            # Mark workers for killing
            updated_plan.workers_to_kill = adaptive_plan["decisions"].get(
                "kill_workers", []
            )

            # Update queries for existing workers
            updated_plan.updated_queries = adaptive_plan["decisions"].get(
                "update_queries", {}
            )

            # Store gaps and reasoning
            updated_plan.gaps = [
                Gap(
                    description=gap["description"],
                    priority=gap["priority"],
                    reasoning=", ".join(gap.get("evidence", [])),
                )
                for gap in adaptive_plan.get("gaps", [])
            ]
            updated_plan.reasoning = adaptive_plan.get("reasoning", "")

            logger.info(
                f"Adaptive planning complete: {len(updated_plan.workers_to_kill)} workers to kill, "
                f"{len(adaptive_plan['decisions'].get('spawn_workers', []))} workers to spawn"
            )

            return updated_plan

        except Exception as e:
            logger.error(f"Adaptive planning failed: {e}")
            # Return existing plan unchanged on error
            return state.plan
