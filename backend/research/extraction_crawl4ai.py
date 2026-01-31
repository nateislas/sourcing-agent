"""
Crawl4AI-based HTML extraction for the Deep Research Application.
Handles HTML content extraction using Crawl4AI with Gemini Flash LLM.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from typing import Any

import httpx
from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
    LLMConfig,
    LLMExtractionStrategy,
)

from backend.research.extraction import AssetExtractionSchema
from backend.research.logging_utils import get_session_logger, log_api_call
from backend.research.pricing import calculate_llm_cost
from backend.research.state import EvidenceSnippet


def generate_extraction_instruction(research_topic: str) -> str:
    """
    Generates a topic-aware extraction instruction for the LLM.

    Following the late binding principle:
    - Extract broadly: Any asset RELATED to the research topic
    - Don't filter: Don't apply strict constraints (stage, geography, etc.) yet

    Args:
        research_topic: The research query or topic (e.g., "CDK12 small molecule, preclinical, TNBC, Worldwide")

    Returns:
        Detailed extraction instruction string
    """
    return f"""You are extracting SPECIFIC therapeutic assets from biomedical text.

RESEARCH CONTEXT: The user is researching: "{research_topic}"

I. WHAT IS AN ASSET? (CRITICAL - READ CAREFULLY)

An ASSET is a specific drug candidate or therapeutic compound (NOT a target protein, NOT a disease) with:
1. **A concrete identifier:** code name (e.g., "BMS-986158"), chemical name (e.g., "trastuzumab deruxtecan"), or patent designation (e.g., "Compound 7a from CN112345678A")
2. **Evidence proving it exists:** mentioned in patents, trials, press releases, pipeline pages, or peer-reviewed publications

✅ EXAMPLES OF VALID ASSETS (DO EXTRACT):
- BMS-986158 (code name)
- Trastuzumab deruxtecan / DS-8201 (chemical name with alias)
- "Compound 7a" from patent CN112345678A (patent compound with context)
- ISM9274 (development code)
- Dinaciclib, niraparib, olaparib (approved drugs with chemical names)

❌ EXAMPLES OF INVALID ENTITIES (DO NOT EXTRACT):
- CDK12 (protein target, not a therapeutic compound)
- "CDK12 inhibitors" (compound class, not a specific asset)
- Triple-negative breast cancer (disease/indication, not a therapeutic)
- Pfizer, Bristol Myers Squibb (companies, not compounds)
- "Future CDK12 inhibitors might..." (hypothetical, no concrete identifier)

**CRITICAL RULE:** If the text only mentions a target protein (e.g., "CDK12") or a generic class (e.g., "CDK12 inhibitors") without naming a SPECIFIC compound with an identifier, DO NOT extract anything. Wait for concrete evidence of a real asset.

II. INCLUSION RULES (BROAD MATCH):
Extract any asset that is RELATED to this research topic:
- If topic mentions "CDK12", extract specific CDK12 inhibitors with identifiers (e.g., SR-4835, THZ531)
- If topic mentions "TNBC", extract specific assets tested in triple-negative breast cancer
- Extract assets even if some metadata is missing (stage unknown is OK if asset identifier is clear)
- DO NOT filter by development stage or geography—we verify constraints later

III. EXCLUSION RULES (STRICT):
DO NOT EXTRACT:
- Target proteins themselves (e.g., "CDK12", "PARP", "HER2")
- Generic drug classes without specific names (e.g., "CDK12 inhibitors" as a class)
- Diseases/indications alone (e.g., "breast cancer", "TNBC")
- Companies or institutions (e.g., "Pfizer", "Insilico Medicine")
- Mechanisms or pathways (e.g., "DNA damage response")
- Off-topic assets (e.g., KRAS inhibitors when researching CDK12)

IV. ATTRIBUTE EXTRACTION RULES (STRICT - APPLY INFERENCE):

For EACH asset you extract, apply these inference rules to populate attributes:

**Target Extraction (Biological Target):**
- IF text says "X inhibitor" → target = "X"
- IF text says "binds to Y" or "targets Y" → target = "Y"
- IF compound mentioned with indication only → target = "Unknown"
- Example: "CDK12 inhibitor SR-4835" → target = "CDK12"

**Modality Extraction (Drug Type):**
- IF text says "small molecule", "oral drug", "chemical compound", "inhibitor" → modality = "Small Molecule"
- IF text says "antibody", "mAb", "immunotherapy" → modality = "Antibody"
- IF text says "ADC", "antibody-drug conjugate" → modality = "ADC"
- IF text says "PROTAC", "degrader" → modality = "PROTAC"
- IF text says "cell therapy", "CAR-T" → modality = "Cell Therapy"
- IF unclear but has chemical structure diagram → modality = "Small Molecule"
- Example: "The degrader compound 7b" → modality = "PROTAC"

**Stage Extraction (Development Phase):**
- IF text says "preclinical", "in vitro", "in vivo" (non-human studies) → product_stage = "Preclinical"
- IF text says "Phase I", "Phase 1", "first-in-human", "FIH" → product_stage = "Phase 1"
- IF text says "Phase II", "Phase 2" → product_stage = "Phase 2"
- IF text says "Phase III", "Phase 3" → product_stage = "Phase 3"
- IF text says "IND-enabling", "preparing IND" → product_stage = "IND-Enabling"
- IF text says "approved", "FDA approved", "marketed", "on market" → product_stage = "Approved"
- IF text says "discontinued", "halted", "terminated" → product_stage = "Discontinued"
- Example: "ISM9274 nominated as preclinical candidate" → product_stage = "Preclinical"

**Owner Extraction (Company/Institution):**
- IF company name appears WITH the asset mention → owner = company name
- IF patent assignee listed → owner = assignee company
- IF academic paper with author affiliation → owner = institution
- IF code name prefix suggests company (e.g., "BMS-" → Bristol Myers Squibb) → owner = inferred company
- Example: "Insilico Medicine's ISM9274" → owner = "Insilico Medicine"

**Geography Extraction (Regional Focus):**
- IF text mentions country name with asset → geography = country
- IF company HQ location is known/mentioned → geography = company location
- IF trial registry ID prefix is known (e.g. NCT -> US/Global, EudraCT -> EU, ChiCTR -> China, JPRN -> Japan, CRiS -> Korea) → geography = region
- Extract ANY mentioned geography or region associated with the asset's development.

**Indication Extraction (Disease/Condition):**
- IF disease name appears with asset → indication = disease
- Example: "SR-4835 for TNBC" → indication = "Triple-negative breast cancer"

**CRITICAL RULES:**
- "Unknown" is ONLY acceptable if the text genuinely does not contain the information
- Do NOT be lazy: If text says "The CDK12 inhibitor ISM9274", you MUST extract target="CDK12", modality="Small Molecule"
- Apply inference: "inhibitor" implies Small Molecule unless stated otherwise

V. EXTRACTION EXAMPLES (TEXT → JSON MAPPING):

**Example 1:**
Text: "BMS-986158, a selective CDK12/13 inhibitor, showed efficacy in preclinical TNBC models"
→ Output:
```json
{{
  "canonical_name": "BMS-986158",
  "aliases": [],
  "target": "CDK12/13",
  "modality": "Small Molecule",
  "product_stage": "Preclinical",
  "indication": "Triple-negative breast cancer",
  "geography": "Unknown",
  "owner": "Bristol Myers Squibb",
  "evidence_excerpt": "BMS-986158, a selective CDK12/13 inhibitor, showed efficacy in preclinical TNBC models"
}}
```

**Example 2:**
Text: "Insilico Medicine nominated ISM9274 as the preclinical candidate for CDK12/13 inhibition in August 2023"
→ Output:
```json
{{
  "canonical_name": "ISM9274",
  "aliases": [],
  "target": "CDK12/13",
  "modality": "Small Molecule",
  "product_stage": "Preclinical",
  "indication": "Unknown",
  "geography": "Unknown",
  "owner": "Insilico Medicine",
  "evidence_excerpt": "Insilico Medicine nominated ISM9274 as the preclinical candidate for CDK12/13 inhibition in August 2023"
}}
```

**Example 3 (INVALID - Do NOT Extract):**
Text: "CDK12 is a promising target for triple-negative breast cancer treatment"
→ Output: `[]` (empty array - mentions target protein only, no specific asset)

**Example 4:**
Text: "The degrader compound 7b showed potent CDK12/13 degradation activity"
→ Output:
```json
{{
  "canonical_name": "Compound 7b",
  "aliases": ["7b"],
  "target": "CDK12/13",
  "modality": "PROTAC",
  "product_stage": "Unknown",
  "indication": "Unknown",
  "geography": "Unknown",
  "owner": "Unknown",
  "evidence_excerpt": "The degrader compound 7b showed potent CDK12/13 degradation activity"
}}
```

Return a JSON array of assets matching this schema. Return `[]` if no specific assets with identifiers are found.
"""


class Crawl4AIExtractor:
    """
    Extracts structured asset data from HTML using Crawl4AI + Gemini Flash.
    """

    def __init__(self, research_id: str | None = None):
        self.research_id = research_id or "default"
        self.logger = get_session_logger(self.research_id) if research_id else None

    async def extract_batch(
        self, urls: list[str], research_query: str
    ) -> tuple[list[dict[str, Any]], float]:
        """
        Processes a batch of URLs in parallel using Crawl4AI's arun_many.
        Reuse browser and crawler session for efficiency.
        """
        if not urls:
            return [], 0.0

        # Generate topic-aware extraction instruction (shared for the batch)
        extraction_instruction = generate_extraction_instruction(research_query)

        # Configure LLM extraction strategy
        model_provider = os.getenv("EXTRACTION_MODEL", "gemini-2.5-flash-lite")
        if not model_provider.startswith("gemini/"):
            model_provider = f"gemini/{model_provider}"

        llm_strategy = LLMExtractionStrategy(
            llm_config=LLMConfig(
                provider=model_provider,
                api_token=os.getenv("GEMINI_API_KEY"),
            ),
            schema=AssetExtractionSchema.model_json_schema(),
            extraction_type="schema",
            instruction=extraction_instruction,
            # OPTIMIZATION: Gemini Flash has 1M+ context. 
            # Process typical pages in one shot (no chunking) for speed and context coherence.
            chunk_token_threshold=100000, 
            overlap_rate=0.0,
            apply_chunking=True, # Only triggers for massive documents > 100k tokens
            input_format="markdown", # Use raw markdown to avoid over-pruning tables/lists
            extra_args={"temperature": float(os.getenv("EXTRACTION_TEMPERATURE", "0.4"))},
        )

        # Configure crawler
        page_timeout = int(os.getenv("CRAWL_TIMEOUT", "60000")) # Fail faster (60s)
        crawl_config = CrawlerRunConfig(
            extraction_strategy=llm_strategy,
            cache_mode=CacheMode.BYPASS,
            word_count_threshold=10,
            page_timeout=page_timeout,
            # Robustness settings
            magic=True,
            remove_overlay_elements=True,
            excluded_tags=['nav', 'footer', 'header', 'aside', 'script', 'style'],
        )

        browser_config = BrowserConfig(
            headless=True,
            verbose=False,
            # Block images/fonts to speed up load time since we only need text
            text_mode=True, 
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        )

        total_cost = 0.0
        all_results = []

        # Filter out empty URLs before calling arun_many
        original_count = len(urls)
        urls = [u for u in urls if u and u.strip()]
        if len(urls) < original_count and self.logger:
            self.logger.warning("Crawl4AIExtractor filtered out %d empty URLs from batch", original_count - len(urls))

        if not urls:
            return [], 0.0

        try:
            async with AsyncWebCrawler(config=browser_config) as crawler:
                results = await crawler.arun_many(urls=urls, config=crawl_config)

                for i, result in enumerate(results):
                    url = urls[i]
                    processed_res, cost = await self._process_single_result(result, url)
                    total_cost += cost
                    all_results.append(processed_res)

        except Exception as e:
            if self.logger:
                self.logger.error("Batch Crawl4AI extraction error: %s", e)

        return all_results, total_cost

    async def _process_single_result(
        self, result: Any, url: str
    ) -> tuple[dict[str, Any], float]:
        """Helper to process a single Crawl4AI result into the system format."""
        entities = []
        links = []

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
                    "Crawl4AI failed for URL [%s]: %s", url, result.error_message
                )
            return {"entities": [], "links": [], "is_pdf": False, "url": url}, 0.0

        # Detect if we got PDF content
        final_url = result.url or url
        markdown_content = result.markdown or ""

        is_pdf_url = final_url.lower().endswith(".pdf")
        is_pdf_content_marker = markdown_content.startswith("%PDF-")

        if is_pdf_url or is_pdf_content_marker:
            if self.logger:
                self.logger.info(
                    "PDF detected at %s. Downloading binary for LlamaExtract.",
                    url,
                )

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
                    "url": url,
                }, 0.0
            except Exception as e:
                if self.logger:
                    self.logger.error("Failed to download PDF from %s: %s", url, e)
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                pass

        # Parse extracted content (JSON from LLM)
        if result.extracted_content:
            if self.logger:
                log_api_call(
                    self.logger,
                    "crawl4ai",
                    "data_parsed",
                    {"url": url},
                    {"content": result.extracted_content[:2000]},
                )
            try:
                extracted_data = json.loads(result.extracted_content)

                if isinstance(extracted_data, dict):
                    extracted_data = [extracted_data]

                generic_terms = {
                    "none",
                    "unknown",
                    "n/a",
                    "inhibitor",
                    "inhibitors",
                    "molecule",
                    "molecules",
                    "asset",
                    "assets",
                }

                for asset_data in extracted_data:
                    canonical = asset_data.get("canonical_name")
                    if not canonical or str(canonical).lower() in generic_terms:
                        continue

                    if len(str(canonical)) > 100:
                        continue

                    excerpt = asset_data.get("evidence_excerpt") or (result.markdown or "")[:500]

                    snippet = EvidenceSnippet(
                        source_url=url,
                        content=excerpt,
                        timestamp=datetime.utcnow().isoformat() + "Z",
                    )

                    # Normalize: Emit single entity per canonical
                    
                    # Gather all unique names for this asset
                    unique_names_set = set()
                    unique_names_set.add(canonical)
                    for n in (asset_data.get("aliases") or []):
                        if n and n.strip():
                            unique_names_set.add(n.strip())
                    
                    # Create "aliases" list excluding the canonical itself
                    aliases_list = [n for n in unique_names_set if n != canonical]
                    
                    # Create the entity dictionary with the normalized schema
                    entity = {
                        "canonical": canonical, # Normalized key
                        "aliases": aliases_list,
                        "attributes": {
                            "target": asset_data.get("target"),
                            "modality": asset_data.get("modality"),
                            "product_stage": asset_data.get("product_stage"),
                            "indication": asset_data.get("indication"),
                            "geography": asset_data.get("geography"),
                            "owner": asset_data.get("owner"),
                        },
                        "evidence": [snippet] # Attach the snippet here
                    }
                    entities.append(entity)

            except json.JSONDecodeError as e:
                if self.logger:
                    self.logger.error("Failed to parse extraction JSON for %s: %s", url, e)

        if result.links:
            links = [
                link["href"]
                for link in result.links.get("internal", []) + result.links.get("external", [])
                if link.get("href", "").startswith("http")
            ]

        # Calculate cost
        try:
            input_len = len(markdown_content)
            output_len = len(result.extracted_content or "")
            cost = calculate_llm_cost("gemini-2.5-flash-lite", input_len // 4, output_len // 4)
        except Exception:
            cost = 0.0

        return {"entities": entities, "links": links, "is_pdf": False, "url": url}, cost

    async def extract_from_html(
        self, url: str, research_query: str, max_retries: int = 2
    ) -> tuple[dict[str, Any], float]:
        """
        Legacy single-URL extraction, now wraps _process_single_result but with single-use browser.
        (For compatibility during migration or special cases)
        """
        if not url or not url.strip():
            return {"entities": [], "links": [], "is_pdf": False, "url": url}, 0.0

        # Reuse the batch logic for a batch of 1 for consistency
        res, cost = await self.extract_batch([url], research_query)
        if res:
            return res[0], cost
        return {"entities": [], "links": [], "is_pdf": False, "url": url}, 0.0

    async def fetch_page_content(self, url: str) -> str:
        """
        Fetches the raw markdown content of a page without LLM extraction.
        Useful for 'Deep Read' verification.
        """
        browser_config = BrowserConfig(
            headless=True,
            text_mode=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        )
        crawl_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            word_count_threshold=10,
            magic=True,
            remove_overlay_elements=True,
            excluded_tags=['nav', 'footer', 'header', 'aside', 'script', 'style'],
        )

        try:
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url, config=crawl_config)
                if result.success:
                    return result.markdown or ""
        except Exception as e:
            if self.logger:
                self.logger.error("Failed to fetch raw content for %s: %s", url, e)
        
        return ""
