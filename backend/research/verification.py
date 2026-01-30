"""
Verification Logic for the Deep Research Application.
Handles strict constraint checking, gap analysis, and final asset classification.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from backend.research.llm import LLMClient
from backend.research.state import Entity

class VerificationResult(BaseModel):
    """Result of the verification process for a single entity."""
    canonical_name: str
    status: str = Field(description="VERIFIED, UNCERTAIN, or REJECTED")
    rejection_reason: Optional[str] = Field(description="Reason for rejection, if applicable")
    missing_fields: List[str] = Field(description="Critical metadata fields that are missing")
    confidence: float = Field(description="Confidence score 0-100")
    explanation: str = Field(description="Reasoning for the decision")

class VerificationAgent:
    """
    Agent responsible for verifying entities against hard constraints and identifying gaps.
    """
    def __init__(self, model_name: str = "gemini-2.5-flash-lite"):
        self.llm = LLMClient(model_name=model_name)

    async def verify_entity(self, entity: Entity, constraints: Dict[str, Any]) -> VerificationResult:
        """
        Verifies a single entity against the provided constraints.
        """
        prompt = self._build_verification_prompt(entity, constraints)
        response = await self.llm.generate(prompt, response_model=VerificationResult)
        return response

    def _build_verification_prompt(self, entity: Entity, constraints: Dict[str, Any]) -> str:
        """
        Constructs the prompt for the verification LLM.
        """
        evidence_text = "\n".join([f"- [{e.timestamp}] {e.content}" for e in entity.evidence])
        
        return f"""
        You are a strict biomedical auditor. Your job is to verify if a discovered asset matches specific research constraints.
        
        ### Asset to Verify
        Name: {entity.canonical_name}
        Aliases: {', '.join(entity.aliases)}
        Current Attributes: {entity.attributes}
        
        ### Evidence Snippets
        {evidence_text}
        
        ### Constraints (MUST MATCH)
        {constraints}
        
        ### Rules
        1. **Strictness**: If the evidence explicitly contradicts a hard constraint (e.g. "Antibody" when "Small Molecule" is required), REJECT it.
        2. **Uncertainty**: If the evidence is insufficient to confirm a hard constraint OR if critical metadata (Owner, Stage) is missing, mark as UNCERTAIN and list the missing fields.
        3. **Verification**: Only mark as VERIFIED if all hard constraints are supported by evidence AND critical metadata is present.
        4. **Critical Metadata**: We need at least 'Owner' (Company/Institution) and 'Development Stage' to consider it fully verified.
        
        Analyze the evidence and provide your verdict.
        """
