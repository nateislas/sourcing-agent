"""
Unit tests for the ResearchAgent logic using LlamaIndex Workflows.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.research.agent import ResearchAgent
from backend.research.state import ResearchPlan


@pytest.fixture
def mock_workflow():
    with patch("backend.research.agent.InitialPlanningWorkflow") as mock_class:
        mock_instance = (
            MagicMock()
        )  # The workflow instance itself is not async, its methods might be
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.mark.asyncio
async def test_generate_initial_plan_success(mock_workflow):
    """Verifies that the agent correctly returns the plan from the workflow."""
    expected_plan = ResearchPlan(
        current_hypothesis="Test Hypothesis",
        findings_summary="Summary",
        gaps=[],
        next_steps=["step 1"],
        # New fields defaults will be used, or we can explicit set them
        reasoning="Test reasoning",
    )

    # workflow.run() returns a handler (WorkflowHandler) which is awaitable
    # So we mock .run() to return a Future-like object or just an AsyncMock that returns the plan

    # Ideally: handler = workflow.run(...) -> await handler -> result

    mock_handler = AsyncMock()
    mock_handler.return_value = expected_plan
    # Make the mock_handler itself awaitable to return 'expected_plan'
    # The pattern 'result = await handler' means handler must be a coroutine or awaitable.
    # An AsyncMock called return value is awaitable, but the AsyncMock object itself is not usually awaited directly unless it's the result of a call.
    # In agent.py: handler = self.planning_workflow.run(...)
    #              result = await handler

    # So mock_workflow.run(...) should return an object that can be awaited.
    # We can use a simple async function or a properly configured AsyncMock.

    async def async_return():
        return expected_plan

    mock_workflow.run.return_value = async_return()

    agent = ResearchAgent()
    plan = await agent.generate_initial_plan("Test Topic")

    assert plan == expected_plan
    mock_workflow.run.assert_called_once_with(topic="Test Topic")


@pytest.mark.asyncio
async def test_generate_initial_plan_failure(mock_workflow):
    """Verifies fallback behavior when workflow raises exception."""
    # Simulating exception during workflow run setup or execution
    mock_workflow.run.side_effect = Exception("Workflow crashed")

    agent = ResearchAgent()
    plan = await agent.generate_initial_plan("Failure Topic")

    assert "Fallback" in plan.current_hypothesis
    assert plan.findings_summary == "Error in planning workflow"
