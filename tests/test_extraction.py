import pytest
from unittest.mock import AsyncMock, patch
from backend.research.extraction import (
    EntityExtractor,
    WebExtractor,
    DrugExtractionSchema,
)


@pytest.mark.asyncio
async def test_entity_extraction_structured():
    """
    Test extraction using mocked LlamaExtract.
    """
    extractor = EntityExtractor()

    # Mock data returned by LlamaExtract
    mock_data = [
        DrugExtractionSchema(
            canonical_name="Relatlimab",
            aliases=["BMS-986016"],
            drug_class="LAG-3 inhibitor",
            clinical_phase="Phase 3",
            trial_ids=["NCT02061761"],
        )
    ]

    with patch.object(
        extractor.llama_client, "extract_structured_data", new_callable=AsyncMock
    ) as mock_extract:
        mock_extract.return_value = mock_data

        results = await extractor.extract_entities("Some text", "https://example.com")

        # Results should contain:
        # 1. Canonical entry
        # 2. Alias entry
        # 3. Trial entry
        assert len(results) == 3

        # Check canonical
        canonical = next(
            r
            for r in results
            if r["canonical"] == "Relatlimab" and r["alias"] == "Relatlimab"
        )
        assert canonical["drug_class"] == "LAG-3 inhibitor"
        assert canonical["clinical_phase"] == "Phase 3"

        # Check alias
        alias = next(r for r in results if r["alias"] == "BMS-986016")
        assert alias["canonical"] == "Relatlimab"

        # Check trial
        trial = next(r for r in results if r["canonical"] == "NCT02061761")
        assert trial["alias"] == "NCT02061761"


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
