"""
SQLAlchemy models for the Deep Research Application.
Define the database schema for persisting research state.
"""

# pylint: disable=unsubscriptable-object,too-few-public-methods

from typing import List
from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, JSON, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.db.connection import Base


class ResearchSessionHelper(Base):
    """Stores the high-level state of a research session."""

    __tablename__ = "research_sessions"
    # pylint: disable=too-few-public-methods

    topic: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, default="initialized")
    logs: Mapped[List[str]] = mapped_column(JSON, default=list)
    # Serialized version of the full ResearchState Pydantic model
    state_dump: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationship to entities found in this session
    # Note: In a real app, we might want a many-to-many if entities are shared,
    # but for this assignment, we scope entities to a session or keep them global.
    # PGEDF implies a Global Knowledge Base, so we won't strictly bind entities to sessions here.


class EntityModel(Base):
    """Database model for a discovered Entity."""

    __tablename__ = "entities"

    canonical_name: Mapped[str] = mapped_column(String, primary_key=True)
    aliases: Mapped[List[str]] = mapped_column(JSON, default=list)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    mention_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    evidence: Mapped[List["EvidenceModel"]] = relationship(
        "EvidenceModel", back_populates="entity", cascade="all, delete-orphan"
    )


class EvidenceModel(Base):
    """Database model for an EvidenceSnippet."""

    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_name: Mapped[str] = mapped_column(ForeignKey("entities.canonical_name"))
    source_url: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[str] = mapped_column(String)

    entity: Mapped["EntityModel"] = relationship(
        "EntityModel", back_populates="evidence"
    )


class WorkerLogModel(Base):
    """Log of worker states for analysis/debugging."""

    __tablename__ = "worker_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    worker_id: Mapped[str] = mapped_column(String)
    session_topic: Mapped[str] = mapped_column(String)  # Logic link to session
    strategy: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    pages_fetched: Mapped[int] = mapped_column(Integer)
    entities_found: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class VisitedURL(Base):
    """Tracks unique URLs visited across all workers to prevent redundant fetching."""

    __tablename__ = "visited_urls"

    url: Mapped[str] = mapped_column(String, primary_key=True)
    # We might want to scope this by research_id if we support multiple concurrent research topics.
    # For now, simplistic global deduplication or explicit scoping.
    research_id: Mapped[str] = mapped_column(String, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
