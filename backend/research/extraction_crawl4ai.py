"""
Crawl4AI-based HTML extraction for the Deep Research Application.
Handles HTML content extraction using Crawl4AI with Gemini Flash LLM.
"""

import os
import json
from typing import Dict, Any, Optional
from datetime import datetime
import httpx
import tempfile

from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CrawlerRunConfig,
    CacheMode,
    LLMConfig,
)
from crawl4ai import LLMExtractionStrategy

from backend.research.extraction import AssetExtractionSchema
from backend.research.state import EvidenceSnippet
from backend.research.logging_utils import get_session_logger, log_api_call


def generate_extraction_instruction(research_topic: str) -> str:
    """
    Generates a topic-aware extraction instruction for the LLM.

    Following the late binding principle:
    - Extract broadly: Any asset RELATED to the research topic
    - Don't filter: Don't apply strict constraints (stage, geography, etc.) yet

    Args:
        research_topic: The research query or topic (e.g., "CDK12 small molecule, preclinical, TNBC, China")

    Returns:
        Detailed extraction instruction string
    """
    return f"""You are extracting SPECIFIC therapeutic assets from biomedical text.

RESEARCH CONTEXT: The user is researching: "{research_topic}"

EXTRACTION SCOPE:
Extract any asset that is RELATED to this research topic. For example:
- If the topic mentions "CDK12", extract CDK12 inhibitors, CDK12/13 dual inhibitors, CDK12 degraders
- If the topic mentions "TNBC", extract assets being studied in triple-negative breast cancer
- Extract assets even if they don't perfectly match all aspects of the query

DO NOT filter by constraints like development stage, geography, or exact modality.
We want broad discovery now - filtering happens later.

An ASSET must have a unique identifier (name, code, or program designation).

EXTRACT (if related to the topic):
- Named drugs/compounds: ISM9274, dinaciclib, niraparib, CT7439
- Development codes: BMS-986158, CTX-712, SR-4835  
- Research compounds: Compound 7f, YJZ5118, compound 14k
- Program names WITH identifiers: "AI-designed CDK12/13 inhibitor ISM9274"

DO NOT EXTRACT (never extract these):
- Target proteins themselves: CDK12, PARP, HER2, PD-1
- Generic drug classes without names: "CDK12 inhibitors", "PARP inhibitors", "small molecules"
- Diseases/indications: "breast cancer", "TNBC", "pancreatic cancer"
- Mechanisms: "DNA damage response"
- General treatments: "chemotherapy", "immunotherapy"
- Off-topic assets: If researching CDK12, don't extract random KRASG12C inhibitors

CRITICAL RULES:
1. Only extract SPECIFIC assets with names/codes, not generic classes
2. Assets should be RELATED to the research topic
3. Don't filter strictly - we want broad recall now

For each asset, extract:
- canonical_name: The primary identifier
- aliases: Alternative names/codes for the SAME asset
- target: Biological target (e.g., CDK12, PARP)
- modality: Drug type (Small molecule, Antibody, PROTAC, etc.)
- product_stage: Development stage (Preclinical, Phase 1, IND, etc.)
- indication: Disease being treated
- owner: Company/institution developing it
- geography: Location if mentioned
- evidence_excerpt: A short (1-3 sentence) VERBATIM chunk of text from the source that mentions the asset and provides evidence for its classification. This is used for auditability.

Return a JSON array of assets. Return [] if no specific assets are found.
"""


class Crawl4AIExtractor:
    """
    Extracts structured asset data from HTML using Crawl4AI + Gemini Flash.
    """

    def __init__(self, research_id: Optional[str] = None):
        self.research_id = research_id or "default"
        self.logger = get_session_logger(self.research_id) if research_id else None

    async def extract_from_html(
        self, url: str, research_query: str, max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Extracts assets from an HTML page using Crawl4AI.

        Args:
            url: The URL to crawl and extract from
            research_query: The research topic/query for context-aware extraction
            max_retries: Number of retries on failure

        Returns:
            Dictionary with 'entities' (list of assets) and 'links' (discovered URLs)
        """
        # Generate topic-aware extraction instruction
        extraction_instruction = generate_extraction_instruction(research_query)

        # Configure LLM extraction strategy
        llm_strategy = LLMExtractionStrategy(
            llm_config=LLMConfig(
                provider="gemini/gemini-2.5-flash-lite-preview-09-2025",
                api_token=os.getenv("GEMINI_API_KEY"),
            ),
            schema=AssetExtractionSchema.model_json_schema(),
            extraction_type="schema",
            instruction=extraction_instruction,  # Use dynamic instruction
            chunk_token_threshold=4000,  # Gemini Flash can handle larger contexts
            overlap_rate=0.1,  # 10% overlap for context continuity
            apply_chunking=True,
            input_format="markdown",  # Cleaner than HTML
            extra_args={"temperature": 0.0},  # Deterministic extraction
        )

        # Configure crawler
        crawl_config = CrawlerRunConfig(
            extraction_strategy=llm_strategy,
            cache_mode=CacheMode.BYPASS,  # Always fetch fresh content
            word_count_threshold=10,  # Min words to consider valid content
        )

        browser_config = BrowserConfig(
            headless=True,
            verbose=False,
        )

        entities = []
        links = []

        try:
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=crawl_config)

                if self.logger:
                    log_api_call(
                        self.logger,
                        "crawl4ai",
                        "extract",
                        {"url": url},
                        {"success": result.success, "status_code": result.status_code},
                    )

                if not result.success:
                    if self.logger:
                        self.logger.warning(
                            "Crawl4AI failed for %s: %s", url, result.error_message
                        )
                    return {"entities": [], "links": [], "is_pdf": False}

                # Detect if we got PDF content
                final_url = result.url or url
                markdown_content = result.markdown or ""
                
                is_pdf_url = final_url.lower().endswith(".pdf")
                is_pdf_content_marker = markdown_content.startswith("%PDF-")
                
                if is_pdf_url or is_pdf_content_marker:
                    if self.logger:
                        self.logger.info("PDF detected at %s. Downloading binary for LlamaExtract.", url)
                    
                    # Create a temporary file to store the PDF
                    fd, temp_path = tempfile.mkstemp(suffix=".pdf")
                    os.close(fd)
                    
                    try:
                        async with httpx.AsyncClient(follow_redirects=True) as client:
                            response = await client.get(url, timeout=30.0)
                            response.raise_for_status()
                            with open(temp_path, "wb") as f:
                                f.write(response.content)
                        
                        return {
                            "entities": [],
                            "links": [],
                            "is_pdf": True,
                            "pdf_path": temp_path,
                        }
                    except Exception as e:
                        if self.logger:
                            self.logger.error("Failed to download PDF from %s: %s", url, e)
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                        # Continue to normal extraction if download fails (might be a false positive PDF)
                        pass

                # Parse extracted content (JSON from LLM)
                if result.extracted_content:
                    if self.logger:
                        log_api_call(
                            self.logger,
                            "crawl4ai",
                            "data_parsed",
                            {"url": url},
                            {"content": result.extracted_content[:2000]} # Log snippet of data
                        )
                    try:
                        extracted_data = json.loads(result.extracted_content)

                        # Handle both single dict and list of dicts
                        if isinstance(extracted_data, dict):
                            extracted_data = [extracted_data]

                        # List of generic terms to filter out if they appear as canonical names
                        generic_terms = {"none", "unknown", "n/a", "inhibitor", "inhibitors", "molecule", "molecules", "asset", "assets"}

                        # Convert to entity format
                        for asset_data in extracted_data:
                            canonical = asset_data.get("canonical_name")
                            if not canonical or str(canonical).lower() in generic_terms:
                                continue  # Skip empty or generic extractions
                            
                            # Additional check: if canonical is too long or looks like a sentence, skip
                            if len(str(canonical)) > 100:
                                continue

                            # Create evidence snippet
                            # Use specific excerpt if provided by LLM, else fallback to slashing
                            excerpt = asset_data.get("evidence_excerpt") or (result.markdown or "")[:500]

                            snippet = EvidenceSnippet(
                                source_url=url,
                                content=excerpt,
                                timestamp=datetime.utcnow().isoformat() + "Z",
                            )

                            # Create entity record for canonical name
                            all_names = [canonical] + (asset_data.get("aliases") or [])
                            for name in all_names:
                                if name and name.strip():  # Skip empty aliases
                                    entities.append(
                                        {
                                            "canonical": canonical,
                                            "alias": name,
                                            "attributes": {
                                                "target": asset_data.get("target"),
                                                "modality": asset_data.get("modality"),
                                                "product_stage": asset_data.get(
                                                    "product_stage"
                                                ),
                                                "indication": asset_data.get(
                                                    "indication"
                                                ),
                                                "geography": asset_data.get(
                                                    "geography"
                                                ),
                                                "owner": asset_data.get("owner"),
                                            },
                                            "evidence": [snippet],
                                        }
                                    )

                    except json.JSONDecodeError as e:
                        if self.logger:
                            self.logger.error(
                                "Failed to parse extraction JSON for %s: %s", url, e
                            )

                # Extract links from the page
                if result.links:
                    # Filter for HTTP(S) links only
                    links = [
                        link["href"]
                        for link in result.links.get("internal", [])
                        + result.links.get("external", [])
                        if link.get("href", "").startswith("http")
                    ]

        except Exception as e:
            if self.logger:
                self.logger.error("Crawl4AI extraction error for %s: %s", url, e)

        return {"entities": entities, "links": links, "is_pdf": False}
