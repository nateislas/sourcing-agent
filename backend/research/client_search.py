"""
Clients for external search APIs (Perplexity and Tavily).
Provides wrappers for structured search results and logging.
"""

import asyncio
import os

from perplexity import Perplexity
from tavily import TavilyClient, AsyncTavilyClient

from backend.research.logging_utils import get_session_logger, log_api_call
from backend.research.pricing import calculate_search_cost


class SearchResult:
    """Unified search result object used across different search clients."""

    def __init__(
        self,
        title: str,
        url: str,
        snippet: str,
        source: str,
        raw_content: str | None = None,
    ):
        self.title = title
        self.url = url
        self.snippet = snippet
        self.source = source
        self.raw_content = raw_content


class PerplexitySearchClient:
    """
    Wrapper for Perplexity Search API.
    Used for reasoning-heavy multi-query searches.
    """

    def __init__(self, api_key: str | None = None, research_id: str | None = None):
        self.api_key = api_key or os.getenv("PERPLEXITY_API_KEY")
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY is required.")
        self.client = Perplexity(api_key=self.api_key)
        self.research_id = research_id
        self.logger = get_session_logger(research_id) if research_id else None

    async def search(
        self, queries: str | list[str], max_results: int | None = None, **kwargs
    ) -> list[SearchResult]:
        """
        Executes one or more search queries.
        """
        if max_results is None:
            max_results = int(os.getenv("PERPLEXITY_MAX_RESULTS", "5"))
        
        # Perplexity API max limit is 20
        max_results = min(max_results, 20)

        # Perplexity SDK is synchronous, so we run in executor
        loop = asyncio.get_event_loop()

        def _run_search():
            return self.client.search.create(
                query=queries,
                max_results=max_results,
            )

        response = await loop.run_in_executor(None, _run_search)

        if self.logger:
            log_api_call(
                self.logger,
                "perplexity",
                "search",
                {"queries": queries, "max_results": max_results},
                response,
            )

        results = []
        # Multi-query response is a list of lists, single query is a flat list
        if isinstance(queries, list):
            for query_results in response.results:
                for res in query_results:
                    results.append(
                        SearchResult(
                            title=res.title,
                            url=res.url,
                            snippet=res.snippet,
                            source="perplexity",
                        )
                    )
        else:
            for res in response.results:
                results.append(
                    SearchResult(
                        title=res.title,
                        url=res.url,
                        snippet=res.snippet,
                        source="perplexity",
                    )
                )
        return results


class TavilySearchClient:
    """
    Wrapper for Tavily Search API.
    Used for rapid discovery and Markdown extraction.
    Supports parallel multi-query execution.
    """

    def __init__(self, api_key: str | None = None, research_id: str | None = None):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            raise ValueError("TAVILY_API_KEY is required.")
        # Use AsyncTavilyClient for native async support
        self.async_client = AsyncTavilyClient(api_key=self.api_key)
        self.research_id = research_id
        self.logger = get_session_logger(research_id) if research_id else None

    async def search(
        self,
        query: str | list[str],
        max_results: int | None = None,
        include_raw_content: bool | None = None,
        **kwargs,
    ) -> list[SearchResult]:
        """
        Executes one or more search queries.
        For multiple queries, uses asyncio.gather for parallel execution.
        """
        if max_results is None:
            max_results = int(os.getenv("TAVILY_MAX_RESULTS", "5"))
        if include_raw_content is None:
            include_raw_content = (
                os.getenv("TAVILY_INCLUDE_RAW_CONTENT", "true").lower() == "true"
            )

        # Normalize to list for uniform handling
        queries = [query] if isinstance(query, str) else query

        # Execute all queries in parallel
        responses = await asyncio.gather(
            *(
                self.async_client.search(
                    query=q,
                    max_results=max_results,
                    include_raw_content=include_raw_content,
                )
                for q in queries
            ),
            return_exceptions=True,
        )

        if self.logger:
            log_api_call(
                self.logger,
                "tavily",
                "search",
                {
                    "queries": queries,
                    "max_results": max_results,
                    "include_raw_content": include_raw_content,
                },
                f"{len(queries)} parallel queries",
            )

        results = []
        for response in responses:
            if isinstance(response, Exception):
                if self.logger:
                    self.logger.error("Tavily search failed: %s", response)
                continue
            for res in response.get("results", []):
                results.append(
                    SearchResult(
                        title=res.get("title", ""),
                        url=res.get("url", ""),
                        snippet=res.get("content", ""),
                        source="tavily",
                        raw_content=res.get("raw_content") if include_raw_content else None,
                    )
                )
        return results
