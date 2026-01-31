import csv
import io
import os
import re
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from temporalio.client import Client, TLSConfig, WorkflowExecutionStatus
from temporalio.contrib.pydantic import pydantic_data_converter

from backend.db.connection import AsyncSessionLocal
from backend.db.repository import ResearchRepository
from backend.research.state import ResearchState

# Config
TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
TEMPORAL_API_KEY = os.getenv("TEMPORAL_API_KEY")
TASK_QUEUE = "deep-research-queue"


TEMPORAL_STATUS_MAP = {
    WorkflowExecutionStatus.RUNNING: "running",
    WorkflowExecutionStatus.COMPLETED: "completed",
    WorkflowExecutionStatus.FAILED: "failed",
    WorkflowExecutionStatus.CANCELLED: "cancelled",
    WorkflowExecutionStatus.TERMINATED: "killed",
    WorkflowExecutionStatus.TIMED_OUT: "timed_out",
    WorkflowExecutionStatus.CONTINUED_AS_NEW: "running",
}

app = FastAPI(title="Deep Research API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    from backend.db.init_db import init_db
    await init_db()


class ResearchRequest(BaseModel):
    """
    Schema for starting a new research session.
    """
    topic: str


class ResearchResponse(BaseModel):
    """
    Schema for the response after starting a research session.
    """
    session_id: str
    message: str


async def get_client():
    """
    Connects to the Temporal server and returns a client instance.
    """
    tls_config = TLSConfig() if TEMPORAL_API_KEY else None
    return await Client.connect(
        TEMPORAL_ADDRESS,
        namespace=TEMPORAL_NAMESPACE,
        api_key=TEMPORAL_API_KEY,
        tls=tls_config or False,
        data_converter=pydantic_data_converter,
    )


def slugify(text: str) -> str:
    """
    Converts a string into a URL-friendly slug.
    """
    text = text.lower()
    text = re.sub(r"[^a-z0-9]", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text


@app.post("/research/start", response_model=ResearchResponse)
async def start_research(request: ResearchRequest):
    """
    Starts a new research workflow for the given topic.
    """
    topic = request.topic
    if not topic:
        raise HTTPException(status_code=400, detail="Topic is required")

    sanitized_id = f"{slugify(topic)}-{uuid.uuid4().hex[:8]}"

    # Initialize state in DB
    initial_state = ResearchState(
        id=sanitized_id,
        topic=topic,
        status="initialized",
        logs=["Initializing research session..."],
    )

    async with AsyncSessionLocal() as session:
        repo = ResearchRepository(session)
        await repo.save_session(initial_state)

    try:
        client = await get_client()
        await client.start_workflow(
            "DeepResearchOrchestrator",
            args=[topic, sanitized_id],
            id=sanitized_id,
            task_queue=TASK_QUEUE,
        )
    except Exception as e:
        # In case of failure, we should probably record it or at least log it
        print(f"Failed to start workflow: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start workflow: {e!s}")

    return ResearchResponse(
        session_id=sanitized_id, message="Research started successfully"
    )


@app.get("/research/history")
async def get_history():
    """
    Retrieves a list of recent research sessions, enriched with Temporal status.
    """
    async with AsyncSessionLocal() as session:
        repo = ResearchRepository(session)
        history = await repo.list_sessions(limit=10)

    # Use temporal status if available
    try:
        client = await get_client()
        for session_item in history:
            try:
                handle = client.get_workflow_handle(session_item["session_id"])
                desc = await handle.describe()
                t_status = TEMPORAL_STATUS_MAP.get(desc.status)
                if t_status:
                    if t_status == "running":
                        # Preserve specific internal states that are still 'running' in Temporal
                        if session_item["status"] not in ["verification_pending"]:
                            session_item["status"] = t_status
                    else:
                        # Terminal statuses from Temporal always win
                        session_item["status"] = t_status
            except Exception:
                # If not found in temporal, keep DB status
                pass
    except Exception as e:
        print(f"Failed to connect to Temporal for history: {e}")

    return history


@app.get("/research/{session_id}")
async def get_session_state(session_id: str):
    """
    Retrieves the full state of a specific research session, enriched with Temporal status.
    """
    async with AsyncSessionLocal() as session:
        repo = ResearchRepository(session)
        state = await repo.get_session(session_id)
        if not state:
            raise HTTPException(status_code=404, detail="Session not found")

    # Use temporal status if available
    try:
        client = await get_client()
        handle = client.get_workflow_handle(session_id)
        desc = await handle.describe()
        t_status = TEMPORAL_STATUS_MAP.get(desc.status)
        if t_status:
            if t_status == "running":
                if state.status not in ["verification_pending"]:
                    state.status = t_status
            else:
                state.status = t_status
    except Exception:
        # If not found in temporal, keep DB status
        pass

    return state


@app.get("/research/{session_id}/export")
async def export_session_csv(session_id: str):
    """
    Exports the research results for a session as a CSV file.
    """
    async with AsyncSessionLocal() as session:
        repo = ResearchRepository(session)
        state = await repo.get_session(session_id)
        if not state:
            raise HTTPException(status_code=404, detail="Session not found")

        # Use StringIO to generate CSV in memory
        output = io.StringIO()
        fieldnames = [
            "Canonical Label",
            "Aliases",
            "Target",
            "Modality",
            "Stage",
            "Indication",
            "Geography",
            "Owner",
            "Verification Status",
            "Confidence Score",
            "Rejection Reason",
            "Evidence Package",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        # Extract entities from the ResearchState model
        entities = state.known_entities

        for entity_name, entity in entities.items():
            # entity is an Entity Pydantic model
            aliases = list(entity.aliases) if entity.aliases else []
            attrs = entity.attributes or {}
            status = entity.verification_status
            score = entity.confidence_score
            reason = entity.rejection_reason or ""
            evidence_list = entity.evidence or []

            aliases_str = "; ".join(aliases) if aliases else ""

            evidence_lines = []
            for ev in evidence_list:
                # ev is an EvidenceSnippet Pydantic model
                content = ev.content.replace("\n", " ").strip()
                ts = ev.timestamp[:10]
                url = ev.source_url
                evidence_lines.append(f"[{ts}] {url} - {content}")

            evidence_package = "\n".join(evidence_lines)

            writer.writerow(
                {
                    "Canonical Label": entity_name,
                    "Aliases": aliases_str,
                    "Target": attrs.get("target") or "Unknown",
                    "Modality": attrs.get("modality") or "Unknown",
                    "Stage": attrs.get("product_stage") or "Unknown",
                    "Indication": attrs.get("indication") or "Unknown",
                    "Geography": attrs.get("geography") or "Unknown",
                    "Owner": attrs.get("owner") or "Unknown",
                    "Verification Status": status,
                    "Confidence Score": score,
                    "Rejection Reason": reason,
                    "Evidence Package": evidence_package,
                }
            )

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=research_{session_id}.csv"
            },
        )
