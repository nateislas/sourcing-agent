"""
LlamaIndex Workflow for Initial Research Planning.
"""

import json
from llama_index.core.workflow import (
    Workflow,
    StartEvent,
    StopEvent,
    step,
)

# ResearchPlan now contains InitialWorkerStrategy
from backend.research.state import ResearchPlan, InitialWorkerStrategy
from backend.research.llm import get_llm
from backend.research.logging_utils import get_session_logger, log_api_call
from backend.research.prompts import INITIAL_PLANNING_PROMPT


class InitialPlanningWorkflow(Workflow):
    """
    Workflow that decomposes a research topic into a comprehensive plan
    using a single Expert Planning step from the PGEDF framework.
    """

    def __init__(
        self,
        model_name: str = "models/gemini-3-flash-preview",
        timeout: int = 60,
        verbose: bool = False,
        research_id: str = None,
    ):
        super().__init__(timeout=timeout, verbose=verbose)
        self.llm = get_llm(model_name)
        self.research_id = research_id
        self.logger = get_session_logger(research_id) if research_id else None

    @step
    async def generate_comprehensive_plan(self, ev: StartEvent) -> StopEvent:
        """
        Executes the Expert Planning Prompt to generate analysis, synonyms, and worker strategies.
        """
        topic = ev.get("topic")
        if not topic:
            raise ValueError("Missing topic for planning")

        # The prompt expects {query}
        prompt_str = INITIAL_PLANNING_PROMPT.format(query=topic)

        # Call LLM
        response = await self.llm.acomplete(prompt_str)

        if self.logger:
            log_api_call(
                self.logger,
                "gemini",
                "planning",
                {"topic": topic, "prompt": prompt_str},
                response.text,
            )

        try:
            # Parse JSON
            text = response.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(text)

            # Construct ResearchPlan
            # We map the complex JSON output to our Pydantic model
            # data keys expected: query_analysis, synonyms, initial_workers, budget_reserve_pct, reasoning

            # Convert dict workers to Pydantic models
            workers = [
                InitialWorkerStrategy(**w) for w in data.get("initial_workers", [])
            ]

            plan = ResearchPlan(
                query_analysis=data.get("query_analysis", {}),
                synonyms=data.get("synonyms", {}),
                initial_workers=workers,
                budget_reserve_pct=data.get("budget_reserve_pct", 0.6),
                reasoning=data.get("reasoning", "No reasoning provided"),
                # Fill legacy fields for now
                current_hypothesis=f"Planning for {topic}",
                findings_summary="Expert planning executed successfully.",
                next_steps=[w.strategy_description for w in workers],
            )

            return StopEvent(result=plan)

        except Exception as e:
            # Fallback Plan
            if self.logger:
                self.logger.error(f"Planning failed: {e}")

            fallback_worker = InitialWorkerStrategy(
                worker_id="worker_1",
                strategy="broad_fallback",
                strategy_description="Broad search due to planning failure",
                example_queries=[topic],
                page_budget=30,
            )

            fallback_plan = ResearchPlan(
                query_analysis={"target": "Unknown", "error": str(e)},
                synonyms={},
                initial_workers=[fallback_worker],
                budget_reserve_pct=0.5,
                reasoning="Fallback due to JSON parsing error in planning.",
                current_hypothesis="Fallback Plan",
                findings_summary=f"Error parsing plan: {e}",
            )
            return StopEvent(result=fallback_plan)
