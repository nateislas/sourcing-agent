
import asyncio
import os
import logging
from backend.research.link_scorer import LinkScorer

async def test_batch_scoring():
    logging.basicConfig(level=logging.INFO)
    scorer = LinkScorer(research_id="test_run")
    scorer.model = "gemini-2.0-flash"
    
    test_links = [
        {"url": "https://clinicaltrials.gov/study/NCT01234567", "context": "Phase 3 trial for BTK inhibitor in MCL"},
        {"url": "https://www.nature.com/articles/s41586-023-01234-x", "context": "New mechanism of resistance to ibrutinib"},
        {"url": "https://twitter.com/biotech_news", "context": "Follow us for more news"},
        {"url": "https://www.pfizer.com/privacy-policy", "context": "Our commitment to data privacy"},
        {"url": "https://en.wikipedia.org/wiki/Bruton%27s_tyrosine_kinase", "context": "General information about BTK protein"},
    ]
    
    print("\n--- Phase 1: Initial Batch Scoring ---")
    results = await scorer.score_links_batch(test_links, "BTK inhibitor approved or phase 3 lung cancer")
    
    for r in results:
        print(f"URL: {r['url'][:50]}... | Score: {r['score']} | Cached: {r.get('cached')} | Reasoning: {r['reasoning'][:50]}...")

    print("\n--- Phase 2: Caching Check (Should be faster) ---")
    # Add one new link and repeat some old ones
    mixed_links = [
        test_links[0], # Should be cached
        {"url": "https://www.fda.gov/news-events/press-announcements/fda-approves-new-btk-inhibitor", "context": "FDA approval news"}, # New
        test_links[2], # Should be cached
    ]
    
    results2 = await scorer.score_links_batch(mixed_links, "BTK inhibitor approved or phase 3 lung cancer")
    for r in results2:
        print(f"URL: {r['url'][:50]}... | Score: {r['score']} | Cached: {r.get('cached')} | Reasoning: {r['reasoning'][:50]}...")

if __name__ == "__main__":
    asyncio.run(test_batch_scoring())
