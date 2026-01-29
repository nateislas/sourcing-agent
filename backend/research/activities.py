"""
Temporal activities for the Deep Research Application.
Handles external interactions like searching and fetching content.
"""

from temporalio import activity
from backend.research.state import ResearchState


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
async def extract_entities(content: str) -> list[dict]:
    """
    Extracts structured entities from raw content.
    Args:
        content: The text content to analyze.
    Returns:
        A list of extracted entity dictionaries.
    """
    activity.logger.info(f"Extracting from content")
    return [{"name": "Example Entity", "type": "Test"}]
