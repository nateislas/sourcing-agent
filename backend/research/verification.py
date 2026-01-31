"""
Verification Logic for the Deep Research Application.
Handles strict constraint checking, gap analysis, and final asset classification.
"""

import os
from typing import Any

from pydantic import BaseModel, Field

from backend.research.llm import LLMClient
from backend.research.state import Entity


class VerificationResult(BaseModel):
    """Result of the verification process for a single entity."""

    canonical_name: str
    status: str = Field(description="VERIFIED, UNCERTAIN, or REJECTED")
    rejection_reason: str | None = Field(
        description="Reason for rejection, if applicable"
    )
    missing_fields: list[str] = Field(
        description="Critical metadata fields that are missing"
    )
    confidence: float = Field(description="Confidence score 0-100")
    explanation: str = Field(description="Reasoning for the decision")


class VerificationAgent:
    """
    Agent responsible for verifying entities against hard constraints and identifying gaps.
    """

    def __init__(self, model_name: str | None = None):
        if model_name is None:
            model_name = os.getenv("VERIFICATION_MODEL", "gemini-2.5-flash-lite")
        self.llm = LLMClient(model_name=model_name)

    async def verify_entity(
        self, entity: Entity, constraints: dict[str, Any]
    ) -> tuple[VerificationResult, float]:
        """
        Verifies a single entity against the provided constraints.
        """
        prompt = self._build_verification_prompt(entity, constraints)
        result, cost = await self.llm.generate(
            prompt, response_model=VerificationResult
        )
        return result, cost  # type: ignore

    def _build_verification_prompt(
        self, entity: Entity, constraints: dict[str, Any]
    ) -> str:
        """
        Builds the prompt for the verification agent with improved constraint clarity.
        """
        # Format constraints for the LLM
        hard_constraints = constraints.get("constraints", {}).get("hard", [])
        soft_constraints = constraints.get("constraints", {}).get("soft", [])
        target = constraints.get("target", "Not specified")
        modality = constraints.get("modality", "Not specified")
        stage = constraints.get("stage", "Not specified")
        geography = constraints.get("geography", "Not specified")

        # Prepare evidence text with sources
        evidence_text = ""
        for i, snippet in enumerate(entity.evidence, 1):
            evidence_text += (
                f'Source {i} ({snippet.source_url}):\n"{snippet.content}"\n\n'
            )

        if not evidence_text:
            evidence_text = "No evidence provided."

        return f"""
    You are a strict biomedical auditor. Your job is to verify if a discovered ASSET matches specific research constraints.
    
    ### 1. Asset Profile
    Asset Name: {entity.canonical_name}
    Aliases: {", ".join(entity.aliases)}
    Drug Class: {entity.drug_class or "Unknown"}
    Clinical Phase: {entity.clinical_phase or "Unknown"}
    Mention Count: {entity.mention_count}
    Current Attributes: {entity.attributes}
    
    ### 2. Research Constraints (THE CRITERIA)
    Target: {target}
    Modality: {modality}
    Development Stage: {stage}
    Geography: {geography}
    
    Must-Have (Hard) Constraints:
    {", ".join(hard_constraints) if hard_constraints else "None explicitly listed, but match the Target/Modality above."}
    
    Nice-to-Have (Soft) Constraints:
    {", ".join(soft_constraints) if soft_constraints else "None"}

    ### 3. Evidence Snippets
    {evidence_text}
    
    ### 4. Evidence Quality Tiers
    
    Evidence sources are weighted by reliability. When making your decision, prioritize higher-tier sources:
    
    **Tier 1 (Highest Trust):**
    - Regulatory filings (FDA, EMA, NMPA, PMDA)
    - Clinical trial registries (clinicaltrials.gov, ChiCTR, EUCTR)
    - Patent applications with detailed experimental data
    
    **Tier 2 (High Trust):**
    - Company press releases and official pipeline pages
    - Peer-reviewed publications in major journals (Nature, Science, Cell, NEJM, Lancet)
    - Conference abstracts from AACR, ASCO, ASH, ESMO
    
    **Tier 3 (Medium Trust):**
    - News articles citing company sources or interviews
    - Vendor catalogs (Selleckchem, MedChemExpress, Cayman Chemical)
    - Academic theses and institutional repositories
    - Industry reports (e.g., GlobalData, Evaluate Pharma)
    
    **Tier 4 (Low Trust):**
    - Blogs and opinion pieces
    - Social media mentions
    - Secondary citations without primary source verification
    
    **CRITICAL RULES:**
    - If Tier 1-2 evidence contradicts Tier 3-4, trust the higher tier
    - If same tier contradicts, prefer more recent date
    - Multiple sources of same tier outweigh single source
    
    **Example:**
    - Tier 1: FDA filing says "Phase 2 for breast cancer"
    - Tier 3: News article says "Preclinical"
    → VERDICT: Trust Tier 1 (Phase 2)
    
    ### 5. Verification Logic
    
    **Step 1: Does the evidence confirm the Target?**
    - Look for explicit mentions (e.g., "CDK12 inhibitor", "binds to CDK12")
    - Weight by tier: Tier 1-2 confirmation is sufficient even if Tier 3 is vague
    
    **Step 2: Does the evidence confirm the Modality?**
    - Small Molecule vs Antibody vs ADC vs PROTAC vs Cell Therapy
    - REJECT if hard evidence contradicts (e.g., constraint needs Small Molecule but Tier 1-2 says Antibody)
    
    **Step 3: Does the evidence confirm the Stage?**
    - Preclinical / IND-Enabling / Phase 1 / Phase 2 / Phase 3 / Approved / Discontinued
    - Use highest-tier source for stage determination
    
    **Step 4: Does the evidence confirm the Geography?** (Only if constrained)
    - Check for country mentions, company headquarters, trial locations
    
    **Step 5: Is the asset owned by a specific company?**
    - Check patent assignees, press releases, pipeline pages
    
    ### 6. Handling Contradictions
    
    When evidence conflicts:
    1. **Higher tier wins** (Tier 1 > Tier 2 > Tier 3 > Tier 4)
    2. **More recent wins** (if same tier, prefer newer publication date)
    3. **Multiple sources win** (3 Tier 2 sources > 1 Tier 2 source)
    
    ### 7. Missing Data Prioritization
    
    Prioritize gap-filling by criticality:
    
    **Critical (P0):** Must have for verification
    - Target (without this, can't verify constraint match)
    - Owner (needed for regional filtering and partnership analysis)
    - Stage (needed for development phase filtering)
    
    **Important (P1):** Improves confidence
    - Modality (helps verify therapeutic type)
    - Indication (confirms disease area match)
    
    **Nice-to-have (P2):** Supplementary
    - Geography (useful for regional competitive analysis)
    - Specific clinical trial IDs
    
    **Decision Rules:**
    - If UNCERTAIN due to missing P0 field (Target/Owner/Stage) → Mark for gap-filling
    - If UNCERTAIN due to missing P1-P2 only → Accept as UNCERTAIN without gap-filling
    
    ### 8. Verdict Rules
    - **VERIFIED**: The evidence (Tier 1-2) explicitly confirms the Target AND Modality AND at least one of (Stage/Owner).
    - **REJECTED**: The evidence (Tier 1-2) contradicts a Hard Constraint (e.g., wrong target, wrong modality, contradicts geographic constraint).
    - **UNCERTAIN**: 
        - Evidence is vague or only from Tier 3-4 sources
        - Hard constraints match, but critical P0 metadata (Target/Owner/Stage) is missing
        - Evidence is contradictory across same-tier sources
    
    Analyze the evidence and provide your verdict with reasoning.
    """
