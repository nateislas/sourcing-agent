
import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.research.client_search import PerplexitySearchClient, TavilySearchClient
from dotenv import load_dotenv

# Load env vars
load_dotenv()

async def verify_perplexity():
    print("\n--- Verifying Perplexity Client ---")
    client = PerplexitySearchClient()
    
    # Test 1: High token budget
    print("Test 1: High token budget (100k) query...")
    results_high = await client.search(
        queries="current treatment landscape for KRAS G12C lung cancer",
        max_results=5,
        max_tokens=100000
    )
    total_len_high = sum(len(r.snippet) for r in results_high)
    print(f"Total snippet length (High Budget): {total_len_high} chars")
    
    # Test 2: Low token budget
    print("Test 2: Low token budget (100) query...")
    results_low = await client.search(
        queries="current treatment landscape for KRAS G12C lung cancer",
        max_results=5,
        max_tokens=100
    )
    total_len_low = sum(len(r.snippet) for r in results_low)
    print(f"Total snippet length (Low Budget): {total_len_low} chars")
    
    if total_len_high > total_len_low:
        print("✅ PASS: High token budget returned more content.")
    else:
        print("❌ FAIL: Token budget did not affect content length.")

async def verify_tavily():
    print("\n--- Verifying Tavily Client ---")
    client = TavilySearchClient()
    
    print("Test 1: General search for 'AI news'...")
    results = await client.search(
        query="latest AI news",
        max_results=3,
        topic="general",
        days=30
    )
    print(f"Got {len(results)} results.")
    for r in results:
        print(f" - {r.title} ({r.url})")
    
    if len(results) > 0:
        print("✅ PASS: Tavily search with news/days params successful.")
    else:
        print("⚠️ WARN: No results found (might be valid if no news).")

async def main():
    await verify_perplexity()
    await verify_tavily()

if __name__ == "__main__":
    asyncio.run(main())
