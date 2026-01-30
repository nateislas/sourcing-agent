"""
Core state definitions for the Deep Research Application.
Defines the shared data structures used by the Orchestrator, Workers, and Activities.
"""

import os
import uuid
from typing import List, Dict, Set, Literal, Any, Optional
from pydantic import BaseModel, Field

try:
    from temporalio import workflow
except ImportError:
    workflow = None


def safe_uuid4() -> str:
    """Returns a UUID4 string, using Temporal's deterministic generator if in a workflow."""
    if workflow:
        try:
            return str(workflow.uuid4())
        except RuntimeError:
            # Not in a workflow context
            pass
    return str(uuid.uuid4())


def safe_getenv(key: str, default: Any = None) -> Any:
    """Return the environment variable using os.getenv; does not perform Temporal sandbox handling."""
    return os.getenv(key, default)


# --- Core Entity Definitions ---


class EvidenceSnippet(BaseModel):
    """Stores verbatim text evidence with its source and timestamp."""

    source_url: str
    content: str
    timestamp: str  # ISO format


class Entity(BaseModel):
    """Represents a discovered entity with its metadata and evidence."""

    canonical_name: str
    # Raw strings found in text (e.g. "BMS-986158", "Compound 7")
    aliases: Set[str] = Field(default_factory=set)
    # Structured data
    drug_class: Optional[str] = None
    clinical_phase: Optional[str] = None
    # Flexible attributes
    attributes: Dict[str, str] = Field(default_factory=dict)
    # Verbatim excerpts backing the entity
    evidence: List[EvidenceSnippet] = Field(default_factory=list)
    # Count of times extracted
    mention_count: int = 0


# --- Worker State & Metrics ---


class WorkerState(BaseModel):
    """Tracks the state and metrics of an individual search worker."""

    id: str = Field(default_factory=safe_uuid4)

    research_id: Optional[str] = None
    strategy: str  # e.g., "broad_english", "specific_code_name"
    queries: List[str] = Field(default_factory=list)  # Actual search queries
    status: Literal["PRODUCTIVE", "DECLINING", "EXHAUSTED", "DEAD_END", "ACTIVE"] = (
        "ACTIVE"
    )
    pages_fetched: int = 0
    entities_found: int = 0
    new_entities: int = 0
    # URLs discovered by this worker to be visited
    personal_queue: List[str] = Field(default_factory=list)
    # Query history tracking
    query_history: List[Dict[str, Any]] = Field(
        default_factory=list, description="History of queries executed by this worker"
    )
    # Each entry: {"query": str, "iteration": int, "results_count": int, "new_entities": int}


# --- Strategic Planning ---


class Gap(BaseModel):
    """Represents a missing piece of information or coverage gap."""

    description: str
    priority: Literal["low", "medium", "high"]
    reasoning: str


class InitialWorkerStrategy(BaseModel):
    worker_id: str = Field(default_factory=safe_uuid4)
    strategy: str
    strategy_description: str
    example_queries: List[str]
    page_budget: int = Field(
        default_factory=lambda: int(safe_getenv("WORKER_PAGE_BUDGET", "50"))
    )
    status: Literal["ACTIVE"] = "ACTIVE"


class ResearchPlan(BaseModel):
    """Encapsulates the current strategic understanding and next steps."""

    # New fields for Expert Planning
    query_analysis: Dict[str, Any] = Field(
        default_factory=dict, description="Structured analysis of the user query"
    )
    synonyms: Dict[str, List[str]] = Field(
        default_factory=dict, description="Generated synonyms for targets/indications"
    )
    initial_workers: List[InitialWorkerStrategy] = Field(
        default_factory=list, description="Initial spawn configuration"
    )
    budget_reserve_pct: float = Field(
        default_factory=lambda: float(safe_getenv("BUDGET_RESERVE_PCT", "0.6")),
        description="Percentage of budget to reserve for adaptive phase",
    )
    reasoning: str = Field(
        default="", description="Explanation of the planning strategy"
    )

    # Legacy/Computed fields used by Orchestrator
    current_hypothesis: str = "Plan Generated"
    findings_summary: str = "Initial Planning Complete"
    gaps: List[Gap] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)

    # Adaptive planning outputs
    workers_to_kill: List[str] = Field(
        default_factory=list, description="Worker IDs to kill this iteration"
    )
    updated_queries: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="New queries for existing workers {worker_id: [queries]}",
    )


# --- Global Orchestrator State ---


class ResearchState(BaseModel):
    """Manages the global state of the research process, including entities and workers."""

    id: str = Field(default_factory=safe_uuid4)

    topic: str
    status: Literal["initialized", "running", "completed", "failed"] = "initialized"

    # Global Knowledge Base
    # Key: Normalized entity string
    known_entities: Dict[str, Entity] = Field(default_factory=dict)

    # Global Concurrency Control
    visited_urls: Set[str] = Field(default_factory=set)

    # Worker Management
    workers: Dict[str, WorkerState] = Field(default_factory=dict)

    # Strategic Plan (The "Brain")
    plan: ResearchPlan = Field(
        default_factory=lambda: ResearchPlan(
            current_hypothesis="Initial state",
            findings_summary="None",
            gaps=[],
            next_steps=["Initial Analysis"],
        )
    )

    iteration_count: int = 0
    logs: List[str] = Field(default_factory=list)

    # Discovery tracking for gap detection
    discovered_code_names: Set[str] = Field(
        default_factory=set, description="Code names found in entity aliases"
    )
    discovered_companies: Set[str] = Field(
        default_factory=set, description="Company names mentioned in entity context"
    )
    high_value_urls: List[str] = Field(
        default_factory=list, description="URLs discovered but not yet explored"
    )
