"""
Main workflow orchestration logic for Deep Research.
Implements the iterative plan-guided discovery framework.
"""

from datetime import timedelta
from temporalio import workflow
from backend.research.state import ResearchState, ResearchPlan

with workflow.unsafe.imports_passed_through():
    from backend.research import activities


@workflow.defn
class DeepResearchOrchestrator:
    """
    The central workflow that orchestrates the research process.
    """

    @workflow.run
    async def run(self, topic: str) -> ResearchState:
        """
        Executes the main research loop for a given topic.
        Args:
            topic: The research subject.
        Returns:
            The final ResearchState containing discovered entities.
        """
        workflow.logger.info(f"Starting research on: {topic}")

        # 1. Initialize State
        state = ResearchState(topic=topic, status="running")
        state.logs.append("Workflow initialized.")

        # 2. Initial Planning (Stub)
        # In a real impl, this would call an LLM to analyze the query
        state.plan.current_hypothesis = f"Exploring {topic}"
        state.plan.next_steps = ["broad_search"]

        # 3. Execution Loop (Limit to 1 iteration for now)
        iteration = 0
        max_iterations = 1

        while iteration < max_iterations:
            workflow.logger.info(f"Starting iteration {iteration}")

            # --- Fan-Out: Execute Workers ---
            # Stub: Just running one search activity for now
            search_results = await workflow.execute_activity(
                activities.search, topic, start_to_close_timeout=timedelta(seconds=10)
            )
            state.logs.append(
                f"Iteration {iteration}: Found {len(search_results)} raw results"
            )

            # --- Fan-In: Analysis & Update Plan ---
            # Stub: Simply logging completion
            iteration += 1

        state.status = "completed"
        return state
