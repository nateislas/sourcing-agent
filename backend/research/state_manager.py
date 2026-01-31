"""
State Manager for Real-time Shared State.
Handles deduplication of URLs and entities across distributed workers.
"""

import logging
from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from backend.db.connection import AsyncSessionLocal
from backend.db.models import EntityModel, VisitedURL

logger = logging.getLogger(__name__)


class StateManager(ABC):
    """Abstract base class for state management."""

    @abstractmethod
    async def is_url_visited(self, url: str, research_id: str | None = None) -> bool:
        """Checks if a URL has already been visited."""
        pass

    @abstractmethod
    async def mark_url_visited(self, url: str, research_id: str | None = None) -> bool:
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
        self, canonical_name: str, attributes: dict | None = None
    ) -> bool:
        """
        Marks an entity as known. Returns True if successfully marked,
        False if it was already known (race condition caught).
        """
        pass


class DatabaseStateManager(StateManager):
    """Implementation of StateManager using the relational database."""

    async def is_url_visited(self, url: str, research_id: str | None = None) -> bool:
        async with AsyncSessionLocal() as session:
            stmt = select(VisitedURL).where(VisitedURL.url == url)
            if research_id:
                stmt = stmt.where(VisitedURL.research_id == research_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def mark_url_visited(self, url: str, research_id: str | None = None) -> bool:
        async with AsyncSessionLocal() as session:
            try:
                # Use ON CONFLICT DO NOTHING to avoid "duplicate key value" errors in logs
                stmt = insert(VisitedURL).values(url=url, research_id=research_id)
                # Ensure we handle checking unique constraint on (url, research_id) if defined
                # If only url is unique in DB schema, this might fail if same URL used in diff research
                # Assuming schema allows (url, research_id) uniqueness or we want per-research scope.
                # User request suggests updating this call implies we want per-research scope.
                stmt = stmt.on_conflict_do_nothing(index_elements=["url", "research_id"])
                result = await session.execute(stmt)
                await session.commit()
                # rowcount is 1 if inserted, 0 if conflict
                return result.rowcount > 0
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
        self, canonical_name: str, attributes: dict | None = None
    ) -> bool:
        """
        Marks an entity as known. Returns True if it's a NEW entity,
        False if it already existed (but may have updated its attributes).
        """
        async with AsyncSessionLocal() as session:
            try:
                # 1. Check if it exists
                stmt = select(EntityModel).where(
                    EntityModel.canonical_name == canonical_name
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    # Merge attributes: only update if missing or "Unknown"
                    if attributes:
                        new_attrs = existing.attributes or {}
                        updated = False
                        for k, v in attributes.items():
                            # Update if current value is missing, empty, or "Unknown"
                            current_val = new_attrs.get(k)
                            if v and (
                                not current_val or current_val in {"Unknown", ""}
                            ):
                                new_attrs[k] = v
                                updated = True

                        if updated:
                            existing.attributes = new_attrs
                            session.add(existing)
                            await session.commit()
                    return False  # Already known

                # 2. Create new if doesn't exist
                entity = EntityModel(
                    canonical_name=canonical_name, attributes=attributes or {}
                )
                session.add(entity)
                await session.commit()
                return True
            except IntegrityError:
                # Race condition: someone else created it.
                # We could retry the merge here, but for now we'll just return False.
                await session.rollback()
                return False
            except Exception as e:
                await session.rollback()
                logger.exception(
                    "Error marking entity %s as known: %s", canonical_name, e
                )
                return False


class RedisStateManager(StateManager):
    """
    Implementation of StateManager using Redis for caching and DB for persistence.
    Uses 'Cache-Aside' pattern for reads and 'Write-Through' for writes.
    """

    def __init__(self):
        import os
        import redis.asyncio as redis
        
        self.redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        # decode_responses=True ensures we get str back, not bytes
        self.redis = redis.from_url(self.redis_url, decode_responses=True)
        self.db_manager = DatabaseStateManager()

    async def is_url_visited(self, url: str, research_id: str | None = None) -> bool:
        key = f"visited_urls:{research_id}" if research_id else "visited_urls"
        
        try:
            # 1. Check Redis
            import redis.exceptions
            if await self.redis.sismember(key, url):
                return True
        except redis.exceptions.RedisError as e:
            logger.warning(f"Redis error in is_url_visited: {e}")
            
        # 2. Check DB (Cache Miss or Redis Down)
        # Note: We continue to DB even if Redis fails
        if await self.db_manager.is_url_visited(url, research_id):
            try:
                # Populate cache
                await self.redis.sadd(key, url)
            except redis.exceptions.RedisError as e:
                logger.warning(f"Redis error populating cache in is_url_visited: {e}")
            return True
            
        return False

    async def mark_url_visited(self, url: str, research_id: str | None = None) -> bool:
        key = f"visited_urls:{research_id}" if research_id else "visited_urls"
        
        # Write-Through: Write to DB first
        is_new = await self.db_manager.mark_url_visited(url, research_id)
        
        try:
            # Provide consistency: Add to Redis regardless of DB result
            await self.redis.sadd(key, url)
        except redis.exceptions.RedisError as e:
             logger.warning(f"Redis error in mark_url_visited: {e}")
        
        return is_new

    async def is_entity_known(self, canonical_name: str) -> bool:
        key = "known_entities"
        
        try:
            # 1. Check Redis
            import redis.exceptions
            if await self.redis.sismember(key, canonical_name):
                return True
        except redis.exceptions.RedisError as e:
             logger.warning(f"Redis error in is_entity_known: {e}")
            
        # 2. Check DB
        if await self.db_manager.is_entity_known(canonical_name):
            try:
                await self.redis.sadd(key, canonical_name)
            except redis.exceptions.RedisError:
                pass
            return True
            
        return False

    async def mark_entity_known(
        self, canonical_name: str, attributes: dict | None = None
    ) -> bool:
        key = "known_entities"
        
        # Write-Through
        is_new = await self.db_manager.mark_entity_known(canonical_name, attributes)
        
        try:
            # Update Cache
            await self.redis.sadd(key, canonical_name)
        except redis.exceptions.RedisError as e:
             logger.warning(f"Redis error in mark_entity_known: {e}")
        
        return is_new
