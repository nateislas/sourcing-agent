"""
Verification Logic for the Deep Research Application.
Handles strict constraint checking, gap analysis, and final asset classification.
"""

import json
import os
import re
from typing import Any

from pydantic import BaseModel, Field

from backend.research.llm import LLMClient
from backend.research.state import Entity, VerificationStatus


class VerificationResult(BaseModel):
    """Result of the verification process for a single entity."""

    canonical_name: str
    status: VerificationStatus = Field(description="VERIFIED, UNCERTAIN, or REJECTED")
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
        thinking_budget = int(os.getenv("VERIFICATION_THINKING_BUDGET", "0")) or None
        temperature = float(os.getenv("VERIFICATION_TEMPERATURE", "1.0"))
        self.llm = LLMClient(model_name=model_name, thinking_budget=thinking_budget, temperature=temperature)

    async def verify_entity(
        self, entity: Entity, constraints: dict[str, Any]
    ) -> tuple[VerificationResult, float]:
        """
        Verifies a single entity against the provided constraints.
        """
        # Build prompt
        prompt = self._build_verification_prompt(entity, constraints)
        
        # Use thinking model? Handled by LLMClient config
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
    
    **Must-Have (Hard) Constraints:**
    {", ".join(hard_constraints) if hard_constraints else "None explicitly listed, but match the Target/Modality above."}
    
    **Negative Constraints (Must NOT match):**
    - Do NOT accept assets that are clearly NOT the required modality (e.g. if small molecule required, reject antibodies).
    - Do NOT accept assets that fail a hard geographic exclusion (if specified).
    
    **Nice-to-Have (Soft) Constraints:**
    {", ".join(soft_constraints) if soft_constraints else "None"}

    ### 3. Evidence Snippets
    {evidence_text}
    
    ### 4. Evidence Quality Tiers
    
    Evidence sources are weighted by reliability. When making your decision, prioritize higher-tier sources:
    
    **Tier 1 (Highest Trust - The "Gold Standard"):**
    - Regulatory filings (FDA, EMA, NMPA, PMDA)
    - Clinical trial registries (ClinicalTrials.gov, ChiCTR, EUCTR)
    - **Patents with Experimental Data** (Examples/Claims)
    
    **Tier 2 (High Trust - Official Corporate):**
    - Company press releases and official pipeline pages
    - Peer-reviewed publications in major journals (Nature, Science, Cell, NEJM, Lancet)
    - Conference abstracts from AACR, ASCO, ASH, ESMO
    
    **Tier 3 (Medium Trust - Secondary Sources):**
    - News articles citing company sources or interviews
    - Vendor catalogs (Selleckchem, MedChemExpress, Cayman Chemical)
    - Academic theses and institutional repositories
    - Industry reports (e.g., GlobalData, Evaluate Pharma)
    
    **Tier 4 (Low Trust - Speculative):**
    - Blogs and opinion pieces
    - Social media mentions
    - Secondary citations without primary source verification
    
    **CRITICAL RULES:**
    - If Tier 1-2 evidence contradicts Tier 3-4, trust the higher tier.
    - If same tier contradicts, prefer **more recent date**.
    - Multiple sources of same tier outweigh single source.
    - **NEGATIVE EVIDENCE CHECK**: Actively look for terms like "Discontinued", "Terminated", "Withdrawn", "Suspended". If found in Tier 1-2 sources, weight this heavily.
    
    ### 5. Verification Logic
    
    **Step 1: Does the evidence confirm the Target?**
    - Look for explicit mentions (e.g., "CDK12 inhibitor", "binds to CDK12").
    - Weight by tier: Tier 1-2 confirmation is sufficient even if Tier 3 is vague.
    
    **Step 2: Does the evidence confirm the Modality?**
    - Small Molecule vs Antibody vs ADC vs PROTAC vs Cell Therapy.
    - **REJECT** if hard evidence contradicts (e.g., constraint needs Small Molecule but Tier 1-2 says Antibody).
    
    **Step 3: Does the evidence confirm the Stage?**
    - Preclinical / IND-Enabling / Phase 1 / Phase 2 / Phase 3 / Approved / Discontinued.
    - Use highest-tier source for stage determination.
    
    **Step 4: Does the evidence confirm the Geography?** (Only if constrained)
    - Check for country mentions, company headquarters, trial locations.
    - **Inference Rule:** If Company is Swiss, but trial is in US, the asset *is* in US.
    
    **Step 5: Is the asset owned by a specific company?**
    - Check patent assignees, press releases, pipeline pages.
    
    ### 6. Handling Contradictions
    
    When evidence conflicts:
    1. **Higher tier wins** (Tier 1 > Tier 2 > Tier 3 > Tier 4).
    2. **More recent wins** (if same tier, prefer newer publication date).
    3. **Multiple sources win** (3 Tier 2 sources > 1 Tier 2 source).
    
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
    - If UNCERTAIN due to missing P0 field (Target/Owner/Stage) -> Mark for gap-filling
    - If UNCERTAIN due to missing P1-P2 only -> Accept as UNCERTAIN without gap-filling
    
    ### 8. Verdict Rules
    - **VERIFIED**: The evidence (Tier 1-2) explicitly confirms the Target AND Modality AND at least one of (Stage/Owner).
    - **REJECTED**: The evidence (Tier 1-2) contradicts a Hard Constraint (e.g., wrong target, wrong modality, contradicts geographic constraint).
    - **UNCERTAIN**: 
        - Evidence is vague or only from Tier 3-4 sources.
        - Hard constraints match, but critical P0 metadata (Target/Owner/Stage) is missing.
        - Evidence is contradictory across same-tier sources.
    
    Analyze the evidence and provide your verdict with reasoning.
    """

    async def deduplicate_entities(self, entities: list[Entity]) -> list[Entity]:
        """
        Analyzes a list of entities and merges duplicates using reasoning.
        """
        if not entities:
            return []

        # Convert to simplified dicts for LLM to save tokens
        entity_list = []
        for e in entities:
             entity_list.append({
                 "canonical_name": e.canonical_name,
                 "aliases": list(e.aliases),
                 "target": e.attributes.get("target"),
                 "modality": e.attributes.get("modality"),
                 "owner": e.attributes.get("owner"),
             })

        prompt = f"""
        You are a biomedical data reconciliation expert. Your task is to identify and merge duplicate drug assets from a provided list.

        ### Input Data
        {entity_list}

        ### Deduplication Rules
        1. **Name Matching**: "Drug X" and "Drug-X" are duplicates.
        2. **Code Name Matching**: "Code 123" and "Company-123" are duplicates. 
        3. **Alias Matching**: If Asset A has alias "X" and Asset B is named "X", they are duplicates.
        4. **Context Matching**: If two assets have the same Target + Modality + Owner, they might be duplicates (be careful).
        5. **Do NOT Merge**: If they are clearly different assets (e.g. mRNA-123 vs mRNA-456) even if from same company.

        ### Output Format
        Return a JSON object with a list of "groups". Each group contains the "canonical_names" of entities that should be merged.
        Example:
        {{
            "groups": [
                ["Asset A", "Asset-A (US)"],
                ["Asset B"]
            ]
        }}
        """

        try:
            response_text, _ = await self.llm.generate(prompt)
            # Parse response_text logic here (assuming LLMClient handles JSON parsing or we do it manually)
            # For robustness, we'll try to parse the JSON
            
            # Clean markdown code blocks
            text = response_text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            
            # Simple JSON cleanup for trailing commas
            text = re.sub(r",\s*}", "}", text)
            text = re.sub(r",\s*]", "]", text)

            data = json.loads(text.strip())
            groups = data.get("groups", [])
            
            merged_entities = []
            processed_names = set()
            
            # Map name to entity object
            name_map = {e.canonical_name: e for e in entities}
            
            for group in groups:
                # Filter valid names
                valid_names = [n for n in group if n in name_map]
                if not valid_names:
                    continue
                    
                # Mark as processed
                for n in valid_names:
                    processed_names.add(n)
                
                # Merge logic: Take the first one as primary, merge others into it
                primary_name = valid_names[0]
                primary_ent = name_map[primary_name]
                
                for other_name in valid_names[1:]:
                    other_ent = name_map[other_name]
                    # Merge logic
                    primary_ent.aliases.update(other_ent.aliases)
                    primary_ent.aliases.add(other_name)
                    primary_ent.mention_count += other_ent.mention_count
                    primary_ent.evidence.extend(other_ent.evidence)
                    if not primary_ent.drug_class and other_ent.drug_class:
                        primary_ent.drug_class = other_ent.drug_class
                    if not primary_ent.clinical_phase and other_ent.clinical_phase:
                        primary_ent.clinical_phase = other_ent.clinical_phase
                    if not primary_ent.attributes.get("owner") and other_ent.attributes.get("owner"):
                        primary_ent.attributes["owner"] = other_ent.attributes.get("owner") or "Unknown"

                merged_entities.append(primary_ent)
            
            # Add any that weren't in groups
            for e in entities:
                if e.canonical_name not in processed_names:
                    merged_entities.append(e)

            return merged_entities

        except Exception as e:
            # Fallback: return original list
            print(f"Deduplication failed: {e}")
            return entities
