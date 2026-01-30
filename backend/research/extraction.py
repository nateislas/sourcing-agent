"""
Extraction logic for the Deep Research Application.
Handles web content cleaning, link discovery, and structured entity extraction.
"""

import os
import io
from datetime import datetime
from urllib.parse import urljoin
from typing import List, Optional
from bs4 import BeautifulSoup
from trafilatura import extract as trafilatura_extract
from pydantic import BaseModel, Field, field_validator
from llama_cloud import AsyncLlamaCloud
from backend.research.state import EvidenceSnippet
from backend.research.logging_utils import get_session_logger, log_api_call


class DrugExtractionSchema(BaseModel):
    """Schema for LlamaExtract to identify drugs and trials."""

    canonical_name: str = Field(
        description="The primary name of the drug or compound (e.g. Relatlimab)"
    )
    aliases: Optional[List[str]] = Field(
        description="Other names, code names, or former names (e.g. BMS-986016)",
        default_factory=list,
    )
    drug_class: Optional[str] = Field(
        description="The mechanism of action or class (e.g. LAG-3 inhibitor)",
        default=None,
    )
    clinical_phase: Optional[str] = Field(
        description="The current clinical trial phase (e.g. Phase 2, Phase 3)",
        default=None,
    )
    trial_ids: Optional[List[str]] = Field(
        description="NCT identifiers for associated trials", default_factory=list
    )

    @field_validator("aliases", "trial_ids", mode="before")
    @classmethod
    def ensure_list(cls, v):
        """Ensures that the input is a list, returning an empty list if None."""
        if v is None:
            return []
        return v


class WebExtractor:
    """
    Extracts content from HTML using Tavily (markdown) or Trafilatura (fallback).
    Also handles link discovery.
    """

    def __init__(self):
        pass

    async def extract_content(self, html_or_markdown: str, _url: str) -> str:
        """
        Cleans content. If it looks like raw HTML, use trafilatura.
        """
        if "<html" in html_or_markdown.lower():
            # Looks like HTML, try to clean it
            content = trafilatura_extract(html_or_markdown)
            return content or ""
        return html_or_markdown  # Already markdown or clean text

    def discover_links(self, html: str, base_url: str) -> List[str]:
        """
        Identifies relevant hyperlinks for the personal queue.
        """
        soup = BeautifulSoup(html, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("#") or href.startswith("javascript:"):
                continue

            if href.startswith("/"):
                href = urljoin(base_url, href)
            elif not href.startswith("http"):
                continue

            links.append(href)
        return list(set(links))


class LlamaExtractionClient:
    """
    Structured extraction using LlamaExtract.
    """

    def __init__(
        self, api_key: Optional[str] = None, research_id: Optional[str] = None
    ):
        self.api_key = api_key or os.getenv("LLAMA_CLOUD_API_KEY")
        self.research_id = research_id or "default"
        if not self.api_key:
            self.client = None
            return

        self.client = AsyncLlamaCloud(api_key=self.api_key)
        self.agent_id = None
        self.logger = get_session_logger(self.research_id) if research_id else None

    async def close(self):
        """Closes the underlying client."""

    async def _get_or_create_agent(self):
        """Ensures an extraction agent exists for drug discovery."""
        if not self.client:
            return None

        if self.agent_id:
            return self.agent_id

        agent_name = f"drug-discovery-{self.research_id}"

        # List existing agents to find ours
        agents = await self.client.extraction.extraction_agents.list()
        for agent in agents:
            if agent.name == agent_name:
                self.agent_id = agent.id
                return self.agent_id

        # Create new agent if not found, handling race conditions (409)
        try:
            agent = await self.client.extraction.extraction_agents.create(
                name=agent_name,
                data_schema=DrugExtractionSchema.model_json_schema(),
                config={"extraction_mode": "BALANCED"},
            )
            self.agent_id = agent.id
        except Exception as e:
            if "409" in str(e):
                # Another worker likely created it. Re-list and find it.
                agents = await self.client.extraction.extraction_agents.list()
                for agent in agents:
                    if agent.name == agent_name:
                        self.agent_id = agent.id
                        return self.agent_id
            raise e

        return self.agent_id

    async def extract_structured_data(
        self, text_or_file_path: str
    ) -> List[DrugExtractionSchema]:
        """
        Runs extraction and returns a list of DrugExtractionSchema objects.
        """
        if not self.client:
            return []

        agent_id = await self._get_or_create_agent()

        if os.path.exists(text_or_file_path):
            file_obj = await self.client.files.create(
                file=text_or_file_path, purpose="extract"
            )
        else:
            # Wrap text in BytesIO
            source_buffer = io.BytesIO(text_or_file_path.encode("utf-8"))
            file_obj = await self.client.files.create(
                file=("document.txt", source_buffer), purpose="extract"
            )

        # Start extraction
        result = await self.client.extraction.jobs.extract(
            extraction_agent_id=agent_id,
            file_id=file_obj.id,
        )

        if self.logger:
            log_api_call(
                self.logger,
                "llama_extract",
                "extract",
                {"file_id": file_obj.id, "agent_id": agent_id},
                result,
            )

        # Process results
        # LlamaExtract returns data as a dict matching the schema
        # If target is PER_DOC, it's one dict. If PER_PAGE/ROW, it's a list.
        data = result.data
        if isinstance(data, dict):
            return [DrugExtractionSchema(**data)]
        if isinstance(data, list):
            return [DrugExtractionSchema(**item) for item in data]
        return []


class EntityExtractor:
    """
    Orchestrates extraction using LlamaExtract and fallbacks.
    """

    def __init__(self, research_id: Optional[str] = None):
        self.llama_client = LlamaExtractionClient(research_id=research_id)

    async def close(self):
        """Closes the underlying client."""
        await self.llama_client.close()

    async def extract_entities(
        self, text: str, source_url: str, raw_html: Optional[str] = None
    ) -> dict:
        """
        Extracts structured drug data and returns entities and discovered links.
        """
        entities = []
        links = []

        # 1. Structure Entity Extraction
        structured_findings = await self.llama_client.extract_structured_data(text)

        for drug in structured_findings:
            snippet = EvidenceSnippet(
                source_url=source_url,
                content=text[:500] if len(text) > 500 else text,
                timestamp=datetime.utcnow().isoformat() + "Z",
            )

            # Canonical and Aliases
            all_names = [drug.canonical_name] + (drug.aliases or [])
            for name in all_names:
                entities.append(
                    {
                        "canonical": drug.canonical_name,
                        "alias": name,
                        "drug_class": drug.drug_class,
                        "clinical_phase": drug.clinical_phase,
                        "evidence": [snippet],
                    }
                )

            # Trials
            for trial in drug.trial_ids or []:
                entities.append(
                    {"canonical": trial, "alias": trial, "evidence": [snippet]}
                )

        # 2. Link Discovery (if raw HTML provided)
        if raw_html:
            web_extractor = WebExtractor()
            links = web_extractor.discover_links(raw_html, source_url)

        return {"entities": entities, "links": links}
