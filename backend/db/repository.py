"""
Repository pattern for separating data access from business logic.
Handles conversion between Domain Models (Pydantic) and Persistence Models (SQLAlchemy).
"""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import ResearchSessionHelper, EntityModel, EvidenceModel
from backend.research.state import ResearchState, Entity, EvidenceSnippet


class ResearchRepository:
    """Repository for managing ResearchState persistence."""

    def __init__(self, session: AsyncSession):
        """
        Initializes the repository with a database session.
        Args:
            session: The asynchronous database session.
        """
        self.session = session

    async def get_session(self, topic: str) -> Optional[ResearchState]:
        """
        Loads a ResearchState from the database for a specific topic.
        Args:
            topic: The topic identifier for the session.
        Returns:
            The loaded ResearchState or None if not found.
        """
        stmt = select(ResearchSessionHelper).where(ResearchSessionHelper.topic == topic)
        result = await self.session.execute(stmt)
        db_obj = result.scalar_one_or_none()

        if not db_obj:
            return None

        # Reconstruct Pydantic model from state_dump
        if db_obj.state_dump:
            return ResearchState.model_validate(db_obj.state_dump)

        # Fallback for old records without state_dump
        return ResearchState(topic=db_obj.topic, status=db_obj.status, logs=db_obj.logs)

    async def save_session(self, state: ResearchState):
        """
        Persists a research session record. Upserts if topic already exists.
        Args:
            state: The ResearchState to persist.
        """
        stmt = select(ResearchSessionHelper).where(
            ResearchSessionHelper.topic == state.topic
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.status = state.status
            existing.logs = state.logs
            existing.state_dump = state.model_dump(mode="json")
        else:
            db_obj = ResearchSessionHelper(
                topic=state.topic,
                status=state.status,
                logs=state.logs,
                state_dump=state.model_dump(mode="json"),
            )
            self.session.add(db_obj)

        await self.session.commit()

    async def save_entity(self, entity: Entity):
        """
        Persists a discovered entity and its associated evidence.
        Updates existing entities if found by canonical name.
        Args:
            entity: The Entity domain model to save.
        """
        # Check if exists
        stmt = select(EntityModel).where(
            EntityModel.canonical_name == entity.canonical_name
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Update attributes and count
            existing.attributes = entity.attributes
            existing.aliases = list(entity.aliases)
            existing.mention_count = entity.mention_count
        else:
            # Create new
            db_entity = EntityModel(
                canonical_name=entity.canonical_name,
                attributes=entity.attributes,
                aliases=list(entity.aliases),
                mention_count=entity.mention_count,
            )
            self.session.add(db_entity)
            # Flush to get ID if needed, though canonical_name is PK
            await self.session.flush()

            # Handle Evidence
            for ev in entity.evidence:
                db_ev = EvidenceModel(
                    entity_name=entity.canonical_name,
                    source_url=ev.source_url,
                    content=ev.content,
                    timestamp=ev.timestamp,
                )
                self.session.add(db_ev)

        await self.session.commit()

    async def get_entity(self, canonical_name: str) -> Optional[Entity]:
        """
        Retrieves a hydrated Entity by its canonical name.
        Args:
            canonical_name: The name of the entity to retrieve.
        Returns:
            The Entity domain model or None if not found.
        """
        stmt = (
            select(EntityModel)
            .options(selectinload(EntityModel.evidence))
            .where(EntityModel.canonical_name == canonical_name)
        )
        result = await self.session.execute(stmt)
        db_obj = result.scalar_one_or_none()

        if not db_obj:
            return None

        # Hydrate EvidenceSnippets
        evidence = [
            EvidenceSnippet(
                source_url=ev.source_url, content=ev.content, timestamp=ev.timestamp
            )
            for ev in db_obj.evidence
        ]

        # Hydrate Entity Pydantic model
        return Entity(
            canonical_name=db_obj.canonical_name,
            aliases=set(db_obj.aliases),
            attributes=db_obj.attributes,
            mention_count=db_obj.mention_count,
            evidence=evidence,
        )
