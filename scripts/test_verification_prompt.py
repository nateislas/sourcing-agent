import asyncio
import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.research.verification import VerificationAgent
from backend.research.state import Entity, EvidenceSnippet

def test_prompt_building():
    print("Testing Verification Prompt Construction...")
    
    # Mock Entity
    entity = Entity(
        canonical_name="ISM9274",
        aliases=["ISM-9274"],
        attributes={"target": "CDK12", "modality": "Small Molecule"},
        evidence=[
            EvidenceSnippet(
                source_url="http://example.com/paper1",
                content="ISM9274 is a potent, selective small molecule inhibitor of CDK12/13.",
                timestamp=datetime.utcnow().isoformat()
            )
        ]
    )
    
    # Mock Constraints
    constraints = {
        "target": "CDK12",
        "modality": "Small Molecule",
        "stage": "Preclinical",
        "geography": "China",
        "constraints": {
            "hard": ["Target must be CDK12", "Modality must be Small Molecule"],
            "soft": ["Prefer oral availability"]
        }
    }
    
    agent = VerificationAgent(model_name="gemini-2.5-flash-lite-preview-09-2025")
    prompt = agent._build_verification_prompt(entity, constraints)
    
    print("-" * 50)
    print(prompt)
    print("-" * 50)
    
    # Check for key sections
    assert "Asset Name: ISM9274" in prompt
    assert "Drug Class: Unknown" in prompt  # Default since not set in mock
    assert "Clinical Phase: Unknown" in prompt # Default since not set in mock
    assert "Target: CDK12" in prompt
    assert "Modality: Small Molecule" in prompt
    assert "Source 1 (http://example.com/paper1)" in prompt
    assert "Step 1: Does the evidence confirm the **Target**?" in prompt
    
    print("✅ Prompt structure verified successfully.")

if __name__ == "__main__":
    test_prompt_building()
