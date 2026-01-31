"""
LLM-based link relevance scoring for intelligent queue prioritization.
"""

import json
import os
from typing import Any

from backend.research.llm import LLMClient
from backend.research.logging_utils import get_session_logger


LINK_SCORING_PROMPT = """You are evaluating whether a discovered web link is relevant to a biomedical research query.

Research Query: {research_query}

Discovered Link:
- URL: {url}
- Anchor Text: {anchor_text}
- Surrounding Context: {context}

Rate the link's relevance on a scale of 0-10:
- 0-2: Completely irrelevant (e.g., social media, ads, navigation)
- 3-4: Tangentially related (e.g., general disease info when looking for specific drugs)
- 5-6: Somewhat relevant (e.g., related therapeutic area but different target)
- 7-8: Highly relevant (e.g., same target or indication, different asset)
- 9-10: Extremely relevant (e.g., directly discusses assets matching the query)

Output JSON only:
{{
  "score": 8,
  "reasoning": "FDA approval announcement for KRAS G12C inhibitor matching query criteria"
}}
"""


class LinkScorer:
    """LLM-based link relevance scorer."""

    def __init__(self, research_id: str | None = None):
        self.research_id = research_id
        self.logger = get_session_logger(research_id) if research_id else None
        self.model = os.getenv("LINK_SCORING_MODEL", "gemini-2.5-flash-lite")

    async def score_link(
        self,
        url: str,
        anchor_text: str,
        context: str,
        research_query: str,
    ) -> dict[str, Any]:
        """
        Score a single link using LLM.

        Returns:
            {
                "score": int (0-10),
                "reasoning": str,
                "cost": float
            }
        """
        prompt = LINK_SCORING_PROMPT.format(
            research_query=research_query,
            url=url,
            anchor_text=anchor_text or "N/A",
            context=context[:500] if context else "N/A",  # Limit context length
        )

        try:
            llm_client = LLMClient(model_name=self.model)
            # LLMClient.generate returns (text, cost) tuple
            response_text, cost = await llm_client.generate(prompt)

            # Parse JSON response
            result = json.loads(response_text)
            score = int(result.get("score", 0))
            reasoning = result.get("reasoning", "")

            if self.logger:
                self.logger.debug(
                    "Link scored: %s -> %d/10 (%s)", url[:50], score, reasoning[:50]
                )

            return {"score": score, "reasoning": reasoning, "cost": cost}

        except Exception as e:
            if self.logger:
                self.logger.error("Link scoring failed for %s: %s", url, e)
            # On failure, return neutral score
            return {"score": 5, "reasoning": f"Scoring error: {e}", "cost": 0.0}

    async def score_links_batch(
        self,
        links: list[dict[str, str]],
        research_query: str,
    ) -> list[dict[str, Any]]:
        """
        Score multiple links in a batch.

        Args:
            links: List of dicts with keys: url, anchor_text, context
            research_query: The research topic

        Returns:
            List of scored links with added "score", "reasoning", "cost" fields
        """
        results = []
        total_cost = 0.0

        for link_data in links:
            scored = await self.score_link(
                url=link_data["url"],
                anchor_text=link_data.get("anchor_text", ""),
                context=link_data.get("context", ""),
                research_query=research_query,
            )

            # Merge score into link data
            result = {**link_data, **scored}
            results.append(result)
            total_cost += scored["cost"]

        if self.logger:
            self.logger.info(
                "Scored %d links. Total cost: $%.4f", len(links), total_cost
            )

        return results
