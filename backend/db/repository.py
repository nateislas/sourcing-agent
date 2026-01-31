"""
Repository pattern for separating data access from business logic.
Handles conversion between Domain Models (Pydantic) and Persistence Models (SQLAlchemy).
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.models import EntityModel, EvidenceModel, ResearchSessionHelper
from backend.research.state import Entity, EvidenceSnippet, ResearchState


class ResearchRepository:
    """Repository for managing ResearchState persistence."""

    def __init__(self, session: AsyncSession):
        """
        Initializes the repository with a database session.
        Args:
            session: The asynchronous database session.
        """
        self.session = session

    async def get_session(self, session_id: str) -> ResearchState | None:
        """
        Loads a ResearchState from the database for a specific session.
        Args:
            session_id: The unique session identifier.
        Returns:
            The loaded ResearchState or None if not found.
        """
        stmt = select(ResearchSessionHelper).where(
            ResearchSessionHelper.session_id == session_id
        )
        result = await self.session.execute(stmt)
        db_obj = result.scalar_one_or_none()

        if not db_obj:
            return None

        # Reconstruct Pydantic model from state_dump
        if db_obj.state_dump:
            return ResearchState.model_validate(db_obj.state_dump)

        # Fallback for old records without state_dump
        return ResearchState(topic=db_obj.topic, status=db_obj.status, logs=db_obj.logs)  # type: ignore

    async def list_sessions(self, limit: int = 10) -> list[dict]:
        """
        Lists recent research sessions.
        """
        stmt = (
            select(ResearchSessionHelper)
            .order_by(ResearchSessionHelper.updated_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        sessions = result.scalars().all()
        return [
            {
                "session_id": s.session_id,
                "total_cost": s.total_cost,
                "topic": s.topic,
                "status": s.status,
                "created_at": s.created_at,
                "updated_at": s.updated_at,
                "entities_count": len(s.state_dump.get("known_entities", {}))
                if s.state_dump
                else 0,
            }
            for s in sessions
        ]

    async def save_session(self, state: ResearchState):
        """
        Persists a research session record. Upserts based on session_id.
        Args:
            state: The ResearchState to persist.
        """
        stmt = select(ResearchSessionHelper).where(
            ResearchSessionHelper.session_id == state.id
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.topic = state.topic
            existing.status = state.status
            existing.logs = state.logs
            existing.total_cost = state.total_cost
            existing.state_dump = state.model_dump(mode="json")
        else:
            db_obj = ResearchSessionHelper(
                session_id=state.id,
                topic=state.topic,
                status=state.status,
                logs=state.logs,
                total_cost=state.total_cost,
                state_dump=state.model_dump(mode="json"),
            )
            self.session.add(db_obj)

        await self.session.commit()

        # OPTIMIZATION: We no longer save all entities here.
        # Entities are now saved incrementally by the workers as they are discovered.
        # This prevents O(N) DB writes on every state save.
        
    async def save_entities_batch(self, entities: list[Entity]):
        """
        Saves a batch of entities. 
        Intended to be called with *newly discovered* entities from a worker iteration.
        """
        for entity in entities:
             await self.save_entity(entity)

    async def save_entity(self, entity: Entity):
        """
        Persists a discovered entity and its associated evidence.
        Updates existing entities if found and appends new evidence.
        Args:
            entity: The Entity domain model to save.
        """
        from sqlalchemy.dialects.postgresql import insert as postgresql_insert
        from sqlalchemy import insert

        # Check dialect to decide on upsert strategy
        bind = self.session.get_bind()
        
        if bind.dialect.name == "postgresql":
            # PostgreSQL-specific upsert
            stmt = postgresql_insert(EntityModel).values(**entity_data)
            stmt = stmt.on_conflict_do_update(
                index_elements=["canonical_name"],
                set_=entity_data
            )
            await self.session.execute(stmt)
        else:
             # Dialect-agnostic "upsert" simulation for SQLite
             # We check existence and either update or insert
             stmt_check = select(EntityModel).where(EntityModel.canonical_name == entity.canonical_name)
             result_check = await self.session.execute(stmt_check)
             existing_obj = result_check.scalar_one_or_none()
             
             if existing_obj:
                 # Update existing
                 for k, v in entity_data.items():
                     if hasattr(existing_obj, k):
                         setattr(existing_obj, k, v)
             else:
                 # Insert new
                 new_obj = EntityModel(**entity_data)
                 self.session.add(new_obj)
        
        # Handle evidence separately (append-only)
        # We need to fetch the entity (now guaranteed to exist) to manage relationships
        # Or simpler: just insert evidence ignoring duplicates if we had a unique constraint on evidence
        # But evidence table might not have unique constraint on (entity_name, source_url, content). 
        # Let's stick to the current logic for evidence but re-fetch to be safe.
        
        # Re-fetch to get the ORM object and manage evidence relationship
        current_entity_stmt = (
            select(EntityModel)
            .options(selectinload(EntityModel.evidence))
            .where(EntityModel.canonical_name == entity.canonical_name)
        )
        result = await self.session.execute(current_entity_stmt)
        db_obj = result.scalar_one()

        # Append ONLY new evidence
        existing_signatures = {(e.source_url, e.content) for e in db_obj.evidence}

        for ev in entity.evidence:
            if (ev.source_url, ev.content) not in existing_signatures:
                db_ev = EvidenceModel(
                    entity_name=entity.canonical_name,
                    source_url=ev.source_url,
                    content=ev.content,
                    timestamp=ev.timestamp,
                )
                db_obj.evidence.append(db_ev)
                existing_signatures.add((ev.source_url, ev.content))
        
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
            confidence_score=db_obj.confidence_score,
            verification_status=db_obj.verification_status,  # type: ignore
        )
