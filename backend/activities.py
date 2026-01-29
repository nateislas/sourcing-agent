from temporalio import activity
from backend.state import ResearchState


@activity.defn
async def search(query: str) -> list[str]:
    activity.logger.info(f"Searching for: {query}")
    return [f"http://example.com/result_for_{query}"]


@activity.defn
async def fetch_page(url: str) -> str:
    activity.logger.info(f"Fetching: {url}")
    return f"Content of {url}"


@activity.defn
async def extract_entities(content: str) -> list[dict]:
    activity.logger.info(f"Extracting from content")
    return [{"name": "Example Entity", "type": "Test"}]
