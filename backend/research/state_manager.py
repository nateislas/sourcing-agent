"""
State Manager for Real-time Shared State.
Handles deduplication of URLs and entities across distributed workers.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from backend.db.connection import AsyncSessionLocal
from backend.db.models import VisitedURL, EntityModel

logger = logging.getLogger(__name__)


class StateManager(ABC):
    """Abstract base class for state management."""

    @abstractmethod
    async def is_url_visited(self, url: str, research_id: Optional[str] = None) -> bool:
        """Checks if a URL has already been visited."""
        pass

    @abstractmethod
    async def mark_url_visited(
        self, url: str, research_id: Optional[str] = None
    ) -> bool:
        """
        Marks a URL as visited. Returns True if successfully marked,
        False if it was already visited (race condition caught).
        """
        pass

    @abstractmethod
    async def is_entity_known(self, canonical_name: str) -> bool:
        """Checks if an entity is already known in the global knowledge base."""
        pass

    @abstractmethod
    async def mark_entity_known(
        self, canonical_name: str, attributes: Optional[dict] = None
    ) -> bool:
        """
        Marks an entity as known. Returns True if successfully marked,
        False if it was already known (race condition caught).
        """
        pass


class DatabaseStateManager(StateManager):
    """Implementation of StateManager using the relational database."""

    async def is_url_visited(self, url: str, research_id: Optional[str] = None) -> bool:
        async with AsyncSessionLocal() as session:
            stmt = select(VisitedURL).where(VisitedURL.url == url)
            if research_id:
                stmt = stmt.where(VisitedURL.research_id == research_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def mark_url_visited(
        self, url: str, research_id: Optional[str] = None
    ) -> bool:
        async with AsyncSessionLocal() as session:
            try:
                # Check exist first to save exception overhead
                # (Optional optimization, strict correctness relies on DB constraints)
                visited = VisitedURL(url=url, research_id=research_id)
                session.add(visited)
                await session.commit()
                return True
            except IntegrityError:
                await session.rollback()
                return False
            except Exception as e:
                await session.rollback()
                logger.exception("Error marking URL %s as visited: %s", url, e)
                return False

    async def is_entity_known(self, canonical_name: str) -> bool:
        async with AsyncSessionLocal() as session:
            stmt = select(EntityModel).where(
                EntityModel.canonical_name == canonical_name
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def mark_entity_known(
        self, canonical_name: str, attributes: Optional[dict] = None
    ) -> bool:
        async with AsyncSessionLocal() as session:
            try:
                entity = EntityModel(
                    canonical_name=canonical_name, attributes=attributes or {}
                )
                session.add(entity)
                await session.commit()
                return True
            except IntegrityError:
                await session.rollback()
                return False
            except Exception as e:
                await session.rollback()
                logger.exception(
                    "Error marking entity %s as known: %s", canonical_name, e
                )
                return False
