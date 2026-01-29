"""
Temporal activities for the Deep Research Application.
Handles external interactions like searching and fetching content.
"""

from temporalio import activity
from backend.research.state import ResearchState, Entity
from backend.db.connection import AsyncSessionLocal
from backend.db.repository import ResearchRepository


@activity.defn
async def search(query: str) -> list[str]:
    """
    Performs a broad search for the given query.
    Args:
        query: The search term.
    Returns:
        A list of discoverable URLs.
    """
    activity.logger.info(f"Searching for: {query}")
    return [f"http://example.com/result_for_{query}"]


@activity.defn
async def fetch_page(url: str) -> str:
    """
    Fetches the content of a specific URL.
    Args:
        url: The URL to fetch.
    Returns:
        The raw content of the page.
    """
    activity.logger.info(f"Fetching: {url}")
    return f"Content of {url}"


@activity.defn
async def extract_entities(_content: str) -> list[dict]:
    """
    Extracts structured entities from raw content and persists them.
    Args:
        _content: The text content to analyze.
    Returns:
        A list of extracted entity dictionaries.
    """
    activity.logger.info("Extracting from content")
    # Stub extraction result
    extracted = [{"name": "Example Entity", "type": "Test"}]

    # Persist to DB
    async with AsyncSessionLocal() as session:
        repo = ResearchRepository(session)
        for ent_data in extracted:
            entity = Entity(
                canonical_name=ent_data["name"],
                attributes={"type": ent_data["type"]},
                mention_count=1,
            )
            await repo.save_entity(entity)

    return extracted


@activity.defn
async def save_state(state: ResearchState) -> bool:
    """
    Persists the current global research state.
    Args:
        state: The ResearchState to save.
    Returns:
        True if successful.
    """
    activity.logger.info(f"Saving state for topic: {state.topic}")
    async with AsyncSessionLocal() as session:
        repo = ResearchRepository(session)
        await repo.save_session(state)
    return True
