import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.research.extraction_crawl4ai import Crawl4AIExtractor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_extraction():
    load_dotenv()

    # Test URL - ACS paper that had many "Unknown" fields in CSV
    url = "https://pubs.acs.org/doi/10.1021/acs.jmedchem.2c00384"
    topic = "CDK12 small molecule inhibitor preclinical TNBC"

    print(f"Testing extraction for URL: {url}")
    print(f"Topic: {topic}")
    print("-" * 50)

    extractor = Crawl4AIExtractor(research_id="test-extraction")
    result, cost = await extractor.extract_from_html(url, topic)

    entities = result.get("entities", [])
    print(f"Found {len(entities)} entities:")

    for ent in entities:
        print(f"\nCanonical: {ent['canonical']}")
        print(f"Aliases: {ent['alias']}")
        # Check specific attributes
        attrs = ent["attributes"]
        print(f"Target: {attrs.get('target')} (Should be 'CDK12' or 'CDK12/13')")
        print(f"Modality: {attrs.get('modality')} (Should be 'Small molecule')")
        print(f"Stage: {attrs.get('product_stage')} (Should be 'Preclinical')")
        print(f"Owner: {attrs.get('owner')} (Should be 'Insilico Medicine')")
        print(f"Evidence: {ent['evidence'][0].content[:150]}...")


if __name__ == "__main__":
    asyncio.run(test_extraction())
