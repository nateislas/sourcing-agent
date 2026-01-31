"""
LLM-based link relevance scoring for intelligent queue prioritization.
"""

import json
import os
from typing import Any

from google.api_core.exceptions import ResourceExhausted
from backend.research.llm import LLMClient
from backend.research.logging_utils import get_session_logger


LINK_SCORING_PROMPT = """You are evaluating multiple discovered web links to determine their relevance to a biomedical research query.

Research Query: {research_query}

Discovered Links:
{links_list}

For each link, rate its relevance on a scale of 0-10:
- 0-2: Completely irrelevant (e.g., social media, ads, navigation)
- 3-4: Tangentially related (e.g., general disease info when looking for specific drugs)
- 5-6: Somewhat relevant (e.g., related therapeutic area but different target)
- 7-8: Highly relevant (e.g., same target or indication, different asset)
- 9-10: Extremely relevant (e.g., directly discusses assets matching the query)

Output a JSON array of objects:
[
  {{
    "url": "https://example.com/page1",
    "score": 8,
    "reasoning": "FDA approval announcement for target matching query"
  }},
  ...
]
"""


class LinkScorer:
    """LLM-based link relevance scorer with batching and caching."""
    
    # Simple class-level cache to share across instances in the same process
    _cache: dict[str, dict[str, Any]] = {}

    def __init__(self, research_id: str | None = None):
        self.research_id = research_id
        self.logger = get_session_logger(research_id) if research_id else None
        self.model = os.getenv("LINK_SCORING_MODEL")
        if not self.model:
            import logging
            logging.getLogger(__name__).warning("LINK_SCORING_MODEL not set in .env. Falling back to gemini-2.0-flash.")
            self.model = "gemini-2.0-flash"

    async def score_links_batch(
        self,
        links: list[dict[str, str]],
        research_query: str,
    ) -> list[dict[str, Any]]:
        """
        Score multiple links in batches to improve efficiency and avoid rate limits.
        """
        if not links:
            return []

        # 1. Filter out cached results
        results_map = {}
        links_to_score = []
        for link in links:
            url = link["url"]
            if url in self._cache:
                results_map[url] = {**link, **self._cache[url], "cached": True}
            else:
                links_to_score.append(link)

        if not links_to_score:
            return [results_map[l["url"]] for l in links]

        # 2. Process in chunks to avoid prompt too large but maximize batching
        chunk_size = int(os.getenv("LINK_SCORING_BATCH_SIZE", "20"))
        all_scored_links = []
        import asyncio
        
        # We can still use a semaphore for the batch calls if many workers are hitting this
        sem = asyncio.Semaphore(3)

        async def _score_chunk(chunk):
            async with sem:
                return await self._process_batch_request(chunk, research_query)

        chunks = [links_to_score[i:i + chunk_size] for i in range(0, len(links_to_score), chunk_size)]
        batch_tasks = [_score_chunk(c) for c in chunks]
        batch_results = await asyncio.gather(*batch_tasks)
        
        for batch in batch_results:
            for item in batch:
                url = item["url"]
                # Update cache
                self._cache[url] = {
                    "score": item.get("score", 5),
                    "reasoning": item.get("reasoning", "No reasoning provided"),
                    "cost": item.get("cost", 0.0)
                }
                results_map[url] = {**item, "cached": False}

        # 3. Assemble final list in original order
        final_results = []
        total_cost = 0.0
        for link in links:
            res = results_map.get(link["url"], {**link, "score": 5, "reasoning": "Scoring failed", "cost": 0.0})
            final_results.append(res)
            total_cost += res.get("cost", 0.0)

        if self.logger:
            self.logger.info(
                "Scored %d links (%d from cache). Total cost: $%.4f", 
                len(links), len(links) - len(links_to_score), total_cost
            )

        return final_results

    async def _process_batch_request(
        self,
        chunk: list[dict[str, str]],
        research_query: str,
    ) -> list[dict[str, Any]]:
        """Sends a single batch request to the LLM."""
        links_list_text = ""
        for i, l in enumerate(chunk):
            links_list_text += f"{i+1}. URL: {l['url']}\n   Context: {l.get('context', 'N/A')[:200]}\n\n"

        prompt = LINK_SCORING_PROMPT.format(
            research_query=research_query,
            links_list=links_list_text
        )

        try:
            llm_client = LLMClient(model_name=self.model)
            response_text, cost = await llm_client.generate(prompt)
            
            # Parse the array of results
            parsed_results = self._parse_json_list(response_text)
            
            # Divide cost proportionally across the batch
            per_item_cost = cost / max(len(chunk), 1)
            
            # Map back to original URLs to ensure we don't lose association
            scored_data = []
            for i, l_input in enumerate(chunk):
                # Try to find match by URL or index
                match = None
                for p in parsed_results:
                    if p.get("url") == l_input["url"]:
                        match = p
                        break
                
                if not match and i < len(parsed_results):
                    match = parsed_results[i]
                
                if match:
                    scored_data.append({
                        **l_input,
                        "score": int(match.get("score", 5)),
                        "reasoning": match.get("reasoning", "Parsed from batch"),
                        "cost": per_item_cost
                    })
                else:
                    scored_data.append({**l_input, "score": 5, "reasoning": "Failed to parse from batch", "cost": per_item_cost})
            
            return scored_data

        except ResourceExhausted:
            if self.logger:
                self.logger.warning("Batch link scoring rate limited")
            raise
        except Exception as e:
            if self.logger:
                self.logger.error("Batch link scoring failed: %s", e)
            return [{**l, "score": 5, "reasoning": f"Error: {e}", "cost": 0.0} for l in chunk]

    def _parse_json_list(self, text: str) -> list[dict]:
        """Helper to parse JSON array from LLM response."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        try:
            data = json.loads(text)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            import re
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError as e:
                    if self.logger:
                        self.logger.error(f"Failed to parse JSON from regex match: {e}. Text: {match.group(0)[:100]}...")
                except Exception as e:
                     if self.logger:
                        self.logger.error(f"Unexpected error parsing JSON from regex match: {e}")
            return []

    async def score_link(self, url: str, research_query: str = "", context: dict | None = None, **extra):
        """Legacy method for single link scoring."""
        # Build item for batch processing
        item = {"url": url, "context": str(context) if context else "", **extra}
        results = await self.score_links_batch([item], research_query)
        return results[0] if results else {"score": 5, "reasoning": "Failed", "cost": 0.0}
