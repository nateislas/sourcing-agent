"""
Events used in LlamaIndex Workflows for Deep Research.
"""

from llama_index.core.workflow import Event
from backend.research.state import ResearchPlan


# Intermediate events removed as we now use a consolidated Expert Planning step.
# Only the final result (ResearchPlan) matters, which is returned by the workflow directly.


class PlanCreatedEvent(Event):
    """Final result event containing the ResearchPlan."""

    plan: ResearchPlan
