"""
Research Agent (The "Brain").
Handles the intelligent planning and decision making logic using LLMs.
"""

import json
import logging
import os

from llama_index.core.base.llms.types import ChatMessage

from backend.research.llm_factory import get_llm
from backend.research.logging_utils import get_session_logger, log_api_call
from backend.research.pricing import calculate_llm_cost
from backend.research.prompts import ADAPTIVE_PLANNING_PROMPT
from backend.research.state import (
    Gap,
    InitialWorkerStrategy,
    ResearchPlan,
    ResearchState,
    safe_uuid4,
)
from backend.research.workflow_planning import InitialPlanningWorkflow

logger = logging.getLogger(__name__)


class ResearchAgent:
    """
    The intelligent agent responsible for planning and guiding the research process.
    Uses LlamaIndex Workflows for complex reasoning steps.
    """

    def __init__(
        self,
        model_name: str | None = None,
        timeout: int | None = None,
    ):
        self.model_name = model_name or os.getenv("RESEARCH_MODEL")
        if not self.model_name:
            logger.warning("RESEARCH_MODEL not set in .env. Falling back to gemini-2.5-flash-lite.")
            self.model_name = "gemini-2.5-flash-lite"
            
        env_timeout = os.getenv("RESEARCH_TIMEOUT")
        self.timeout = timeout or (int(env_timeout) if env_timeout else 60)
        
        # Load thinking budgets
        self.planning_thinking_budget = int(os.getenv("PLANNING_THINKING_BUDGET", "0")) or None
        self.research_thinking_budget = int(os.getenv("RESEARCH_THINKING_BUDGET", "0")) or None

    async def generate_initial_plan(
        self, topic: str, research_id: str | None = None
    ) -> ResearchPlan:
        """
        Generates the initial research plan using the planning workflow.
        """
        logger.info("Generating initial plan for topic: %s", topic)

        # Setup workflow with research_id for logging
        planning_workflow = InitialPlanningWorkflow(
            model_name=self.model_name or "models/gemini-2.0-flash-exp",
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
                "Unexpected result type from planning workflow: %s", type(result)
            )
            raise ValueError("Invalid plan generated")

        except Exception as e:
            logger.error("Planning workflow failed: %s", e)
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
        logger.info("Running adaptive planning for iteration %s", state.iteration_count)

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
                    "query_performance": worker.query_performance,
                    "unique_domains": len(worker.explored_domains),
                    "search_engine_history": worker.search_engine_history,
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
        model_name = self.model_name
        # Use planning budget for adaptive planning
        temperature = float(os.getenv("RESEARCH_TEMPERATURE", "1.0"))
        llm = get_llm(model_name=model_name, thinking_budget=self.planning_thinking_budget, temperature=temperature)
        messages = [ChatMessage(role="user", content=prompt)]

        try:
            response = await llm.achat(messages)
            response_text = response.message.content

            # Calculate cost
            cost = 0.0
            try:
                # Estimate or extract usage
                input_tokens = 0
                output_tokens = 0
                if hasattr(response, "raw") and isinstance(response.raw, dict):
                    usage = response.raw.get("usageMetadata", {})
                    input_tokens = usage.get("promptTokenCount", 0)
                    output_tokens = usage.get("candidatesTokenCount", 0)

                if input_tokens == 0:
                    input_tokens = len(prompt) // 4
                    output_tokens = len(response_text) // 4

                cost = calculate_llm_cost(self.model_name or "default", input_tokens, output_tokens)
            except Exception:
                cost = 0.0

            # Extract JSON from response (robust brace-balancing)
            start_idx = response_text.find("```json")
            if start_idx != -1:
                start_idx = response_text.find("{", start_idx)
            else:
                start_idx = response_text.find("{")

            if start_idx != -1:
                brace_count = 0
                end_idx = -1
                for i in range(start_idx, len(response_text)):
                    if response_text[i] == "{":
                        brace_count += 1
                    elif response_text[i] == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            end_idx = i + 1
                            break
                if end_idx != -1:
                    response_text = response_text[start_idx:end_idx]

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
            updated_plan.cost = cost
            decisions = adaptive_plan.get("decisions", {})

            # Add new workers from spawn decisions
            for new_worker in decisions.get("spawn_workers", []):
                updated_plan.initial_workers.append(
                    InitialWorkerStrategy(
                        worker_id=new_worker.get("worker_id", safe_uuid4()),
                        strategy=new_worker.get("strategy", ""),
                        strategy_description=new_worker.get("strategy_description", ""),
                        example_queries=new_worker.get("queries", []),
                    )
                )

            # Mark workers for killing
            updated_plan.workers_to_kill = decisions.get("kill_workers", [])

            # Update queries for existing workers
            updated_plan.updated_queries = decisions.get("update_queries", {})

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
                "Adaptive planning complete: %d workers to kill, %d workers to spawn",
                len(updated_plan.workers_to_kill),
                len(adaptive_plan["decisions"].get("spawn_workers", [])),
            )

            return updated_plan

        except Exception as e:
            logger.error("Adaptive planning failed: %s", e)
            # Return existing plan unchanged on error
            return state.plan
