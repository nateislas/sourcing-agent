
import asyncio
import time
import os
from dotenv import load_dotenv
from backend.research.extraction_crawl4ai import Crawl4AIExtractor

load_dotenv()

async def test_batch():
    extractor = Crawl4AIExtractor(research_id="test_perf")
    urls = [
        "https://example.com",
        "https://en.wikipedia.org/wiki/Clinical_trial",
        "https://www.nature.com"
    ]
    
    print(f"Starting batch extraction of {len(urls)} URLs...")
    start_time = time.time()
    
    # We use a real query but the goal is to see if it runs in parallel
    results, cost = await extractor.extract_batch(urls, "Biomedical research standards")
    
    duration = time.time() - start_time
    print(f"Extraction completed in {duration:.2f} seconds.")
    print(f"Total results: {len(results)}")
    print(f"Total cost: ${cost:.4f}")
    
    for i, res in enumerate(results):
        print(f"URL: {res.get('url')} -> Entities: {len(res.get('entities', []))} | Links: {len(res.get('links', []))}")

if __name__ == "__main__":
    asyncio.run(test_batch())
