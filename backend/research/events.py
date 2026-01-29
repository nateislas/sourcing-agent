"""
Events for the Deep Research Orchestrator workflow.
Defines the communication messages between workflow steps.
"""

from typing import List
from llama_index.core.workflow import Event
from backend.research.state import ResearchPlan, WorkerState


class PlanCreatedEvent(Event):
    """Event triggered when the initial research plan is generated."""

    plan: ResearchPlan


class WorkerStartEvent(Event):
    """Event triggered to start a specific worker's execution."""

    worker_state: WorkerState


class WorkerResultEvent(Event):
    """
    Event carried by a worker upon completion of an iteration.
    Includes comprehensive metrics for orchestrator analysis.
    """

    worker_id: str  # UUID string
    pages_fetched: int
    entities_found: int  # Total mentions extracted
    new_entities: int  # Novel entities not previously known
    novelty_rate: float  # new_entities / total_pages_this_iteration
    status: str  # Classification: PRODUCTIVE, DECLINING, EXHAUSTED, DEAD_END
    extracted_data: List[dict] = []  # List of found entities/aliases


class IterationCompleteEvent(Event):
    """
    Event triggered when all workers have finished and aggregation is done.
    Signals the start of the next planning/dispatch cycle.
    """

    iteration: int
    summary: str
    global_novelty_rate: float
