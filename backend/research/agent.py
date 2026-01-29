"""
Research Agent (The "Brain").
Handles the intelligent planning and decision making logic using LLMs.
"""

import os
import logging
from typing import Optional

from backend.research.state import ResearchPlan
from backend.research.workflow_planning import InitialPlanningWorkflow

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
