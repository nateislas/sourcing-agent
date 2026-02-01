"""
LlamaIndex Workflow for Initial Research Planning.
"""

import asyncio
import json
import logging
import os
import re
from typing import Any

from llama_index.core.workflow import (
    StartEvent,
    StopEvent,
    Workflow,
    step,
)

from backend.research.llm import get_llm
from backend.research.logging_utils import get_session_logger, log_api_call
from backend.research.pricing import calculate_llm_cost
from backend.research.prompts import INITIAL_PLANNING_PROMPT

# ResearchPlan now contains InitialWorkerStrategy
from backend.research.state import InitialWorkerStrategy, ResearchPlan


class InitialPlanningWorkflow(Workflow):
    """
    Workflow that decomposes a research topic into a comprehensive plan
    using a single Expert Planning step from the PGEDF framework.
    """

    def __init__(
        self,
        model_name: str | None = None,
        timeout: int = 60,
        verbose: bool = False,
        research_id: str | None = None,
    ):
        super().__init__(timeout=timeout, verbose=verbose)
        if model_name is None:
            model_name = os.getenv("PLANNING_MODEL")
            if not model_name:
                logging.getLogger(__name__).warning("PLANNING_MODEL not set in .env. Falling back to gemini-3-flash-preview.")
                model_name = "gemini-3-flash-preview"
        
        thinking_budget = int(os.getenv("PLANNING_THINKING_BUDGET", "0")) or None
        temperature = float(os.getenv("PLANNING_TEMPERATURE", "1.0"))
        self.llm = get_llm(model_name, thinking_budget=thinking_budget, temperature=temperature)
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

        # The prompt expects {query} and {context}
        context = ev.get("context", "")
        prompt_str = INITIAL_PLANNING_PROMPT.format(query=topic, context=context)

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

        # Calculate cost (do this before parsing to ensure it's captured even on errors)
        cost = 0.0
        try:
            # Estimate or extract usage
            # Google GenAI response typically has usages in raw
            input_tokens = 0
            output_tokens = 0
            if hasattr(response, "raw") and isinstance(response.raw, dict):
                usage = response.raw.get("usageMetadata", {})
                input_tokens = usage.get("promptTokenCount", 0)
                output_tokens = usage.get("candidatesTokenCount", 0)

            if input_tokens == 0:
                input_tokens = len(prompt_str) // 4
                output_tokens = len(response.text) // 4

            cost = calculate_llm_cost(self.llm.model, input_tokens, output_tokens)
        except Exception:
            # Fallback to rough estimate
            cost = calculate_llm_cost(
                self.llm.model, len(prompt_str) // 4, len(response.text) // 4
            )

        try:
            # Parse JSON
            text = response.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(text)

            # Construct ResearchPlan from JSON output
            # Expected keys: query_analysis, synonyms, initial_workers,
            # budget_reserve_pct, reasoning

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
                cost=cost,
            )

            return StopEvent(result=plan)

        except (
            ValueError,
            KeyError,
            json.JSONDecodeError,
            AttributeError,
            TypeError,
        ) as e:
            # Fallback Plan (preserve cost calculation)
            if self.logger:
                self.logger.error("Planning failed: %s", e)

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
                cost=cost,  # Include cost even in fallback
            )
            return StopEvent(result=fallback_plan)
