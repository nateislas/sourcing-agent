import pytest
from unittest.mock import patch
from backend.research.orchestrator import DeepResearchWorkflow
from backend.research.state import ResearchState, ResearchPlan, InitialWorkerStrategy


@pytest.mark.asyncio
async def test_deep_research_workflow_structure():
    """
    Verifies that the workflow executes the correct sequence of steps:
    Start -> Dispatch -> Execute (Mocked) -> Aggregate -> Dispatch ... -> Stop
    """

    # Mock activities
    with (
        patch("backend.research.activities.generate_initial_plan") as mock_plan,
        patch("backend.research.activities.save_state") as mock_save,
        patch("backend.research.activities.execute_worker_iteration") as mock_exec,
        patch("backend.research.activities.update_plan") as mock_update,
    ):
        # Setup Mock Plan
        worker_cfg = InitialWorkerStrategy(
            worker_id="test_worker_1",
            strategy="broad",
            strategy_description="test",
            example_queries=["q1"],
        )
        plan = ResearchPlan(
            current_hypothesis="Test Hypothesis", initial_workers=[worker_cfg]
        )
        mock_plan.return_value = plan
        mock_save.return_value = True

        # Setup Mock Worker Execution
        # Return different results for different calls to simulate progress
        mock_exec.side_effect = [
            {
                "worker_id": "test_worker_1",
                "pages_fetched": 10,
                "entities_found": 12,
                "new_entities": 5,
                "novelty_rate": 0.5,
                "status": "PRODUCTIVE",
            },  # Iteration 1
            {
                "worker_id": "test_worker_1",
                "pages_fetched": 10,
                "entities_found": 5,
                "new_entities": 2,
                "novelty_rate": 0.2,
                "status": "PRODUCTIVE",
            },  # Iteration 2
            {
                "worker_id": "test_worker_1",
                "pages_fetched": 10,
                "entities_found": 2,
                "new_entities": 0,
                "novelty_rate": 0.0,
                "status": "DECLINING",
            },  # Iteration 3
            {
                "worker_id": "test_worker_1",
                "pages_fetched": 0,
                "entities_found": 0,
                "new_entities": 0,
                "novelty_rate": 0.0,
                "status": "EXHAUSTED",
            },  # Iteration 4
            {
                "worker_id": "test_worker_1",
                "pages_fetched": 0,
                "entities_found": 0,
                "new_entities": 0,
                "novelty_rate": 0.0,
                "status": "EXHAUSTED",
            },  # Iteration 5 -> Should Stop
        ]

        mock_update.return_value = plan

        # Run Workflow
        workflow = DeepResearchWorkflow(timeout=10, verbose=True)
        result = await workflow.run(topic="Test Topic")

        # Assertions
        assert isinstance(result, ResearchState)
        assert result.status == "completed"
        assert result.topic == "Test Topic"

        # Verify call counts
        assert mock_plan.called
        assert (
            mock_exec.call_count == 4
        )  # Iteration 4 finishes with EXHAUSTED, dispatch sees it and stops

        # Verify state updates
        worker_state = result.workers["test_worker_1"]
        assert worker_state.pages_fetched == 30  # 10 + 10 + 10 + 0 + 0
        assert worker_state.entities_found == 19  # 12 + 5 + 2 + 0 + 0
        assert worker_state.new_entities == 7  # 5 + 2 + 0 + 0 + 0
