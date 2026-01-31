from unittest.mock import AsyncMock, patch

import pytest

from backend.research.extraction import (
    AssetExtractionSchema,
    LlamaExtractionClient as EntityExtractor,
    WebExtractor,
)


@pytest.mark.asyncio
async def test_entity_extraction_structured():
    """
    Test extraction using mocked LlamaExtract.
    """
    extractor = EntityExtractor(api_key="test-key")

    # Mock data returned by LlamaExtract
    mock_data = [
        AssetExtractionSchema(
            canonical_name="Relatlimab",
            aliases=["BMS-986016"],
            modality="LAG-3 inhibitor",
            product_stage="Phase 3",
            trial_ids=["NCT02061761"],
        )
    ]

    with patch.object(
        extractor.client, "extract_structured_data", new_callable=AsyncMock
    ) as mock_extract:
        mock_extract.return_value = (mock_data, 0.0)

        # Update method call and arguments to match LlamaExtractionClient
        results, cost = await extractor.extract_structured_data("Some text")

        # Results should contain 1 schema (as returned by LlamaExtract wrapper)
        entities = [r.model_dump() for r in results]
        assert len(entities) == 1
        
        entity = entities[0]
        assert entity["canonical_name"] == "Relatlimab"
        assert "BMS-986016" in entity["aliases"]
        assert entity["modality"] == "LAG-3 inhibitor"
        assert entity["product_stage"] == "Phase 3"
        assert "NCT02061761" in entity["trial_ids"]


@pytest.mark.asyncio
async def test_web_extractor_link_discovery():
    extractor = WebExtractor()
    html = """
    <html>
        <body>
            <a href="https://science.org/article1">Article 1</a>
            <a href="/local-path">Internal</a>
            <a href="#anchor">Anchor</a>
        </body>
    </html>
    """
    links = extractor.discover_links(html, "https://science.org")
    assert "https://science.org/article1" in links
    assert "https://science.org/local-path" in links
    # Note: urljoin("https://science.org", "#anchor") is "https://science.org#anchor"
    # But our code filters #anchor
    assert "https://science.org#anchor" not in links
