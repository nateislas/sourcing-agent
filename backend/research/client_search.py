import os
import asyncio
from typing import List, Optional, Union
from perplexity import Perplexity
from tavily import TavilyClient
from backend.research.logging_utils import get_session_logger, log_api_call


class SearchResult:
    def __init__(
        self,
        title: str,
        url: str,
        snippet: str,
        source: str,
        raw_content: Optional[str] = None,
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

    def __init__(
        self, api_key: Optional[str] = None, research_id: Optional[str] = None
    ):
        self.api_key = api_key or os.getenv("PERPLEXITY_API_KEY")
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY is required.")
        self.client = Perplexity(api_key=self.api_key)
        self.research_id = research_id
        self.logger = get_session_logger(research_id) if research_id else None

    async def search(
        self, queries: Union[str, List[str]], max_results: int = 5
    ) -> List[SearchResult]:
        """
        Executes one or more search queries.
        """
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
    """

    def __init__(
        self, api_key: Optional[str] = None, research_id: Optional[str] = None
    ):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            raise ValueError("TAVILY_API_KEY is required.")
        self.client = TavilyClient(api_key=self.api_key)
        self.research_id = research_id
        self.logger = get_session_logger(research_id) if research_id else None

    async def search(
        self, query: str, max_results: int = 5, include_raw_content: bool = True
    ) -> List[SearchResult]:
        """
        Executes a search query and optionally includes raw markdown content.
        """
        loop = asyncio.get_event_loop()

        def _run_search():
            return self.client.search(
                query=query,
                max_results=max_results,
                include_raw_content=include_raw_content,
            )

        response = await loop.run_in_executor(None, _run_search)

        if self.logger:
            log_api_call(
                self.logger,
                "tavily",
                "search",
                {
                    "query": query,
                    "max_results": max_results,
                    "include_raw_content": include_raw_content,
                },
                response,
            )

        results = []
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
