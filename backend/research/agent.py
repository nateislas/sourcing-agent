"""
Research Agent (The "Brain").
Handles the intelligent planning and decision making logic using LLMs.
"""

import logging

from backend.research.state import ResearchPlan
from backend.research.workflow_planning import InitialPlanningWorkflow

logger = logging.getLogger(__name__)


class ResearchAgent:
    """
    The intelligent agent responsible for planning and guiding the research process.
    Uses LlamaIndex Workflows for complex reasoning steps.
    """

    def __init__(
        self, model_name: str = "models/gemini-3-flash-preview", timeout: int = 60
    ):
        # Initial planning workflow
        self.planning_workflow = InitialPlanningWorkflow(
            model_name=model_name, timeout=timeout, verbose=True
        )

    async def generate_initial_plan(self, topic: str) -> ResearchPlan:
        """
        Generates the initial research plan using the planning workflow.
        """
        logger.info(f"Generating initial plan for topic: {topic}")

        try:
            handler = self.planning_workflow.run(topic=topic)
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
