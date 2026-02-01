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
    extractor = EntityExtractor(research_id="test-id")

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

    # The client is nested inside llama_client
    with patch.object(
        extractor.llama_client.client, "extraction", new_callable=AsyncMock
    ) as mock_extraction_service:
        # Mock the entire chain: client.extraction.jobs.extract
        mock_job_result = AsyncMock()
        mock_job_result.data = [d.model_dump() for d in mock_data]
        mock_extraction_service.jobs.extract.return_value = mock_job_result
        
        # We also need to mock files.create
        extractor.llama_client.client.files = AsyncMock()
        extractor.llama_client.client.files.create.return_value = AsyncMock(id="file_123")
        
        # And extraction agents list/create
        mock_agent = AsyncMock(id="agent_123", name="test-agent")
        mock_extraction_service.extraction_agents.list.return_value = [mock_agent]

        # Update method call and arguments to match LlamaExtractionClient
        # Note: We are testing extract_entities which calls extract_structured_data
        # extract_structured_data calls client.extraction.jobs.extract
        
        entities_result, cost = await extractor.extract_entities("Some text", "http://source.com")

        # extract_entities returns {"entities": [...], "links": [...]}
        entities = entities_result["entities"]
        assert len(entities) >= 1
        
        # Find the main entity entry
        entity = next(e for e in entities if e["canonical"] == "Relatlimab")
        assert entity["canonical"] == "Relatlimab"
        assert "BMS-986016" in entity["alias"] or entity["alias"] == "Relatlimab"
        assert entity["attributes"]["modality"] == "LAG-3 inhibitor"
        assert entity["attributes"]["product_stage"] == "Phase 3"
        
        # Verify trial ID extraction (trials are separate entities in the list)
        trial_entity = next(e for e in entities if e["canonical"] == "NCT02061761")
        assert trial_entity["canonical"] == "NCT02061761"


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
