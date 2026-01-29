"""
Prompts for the Biomedical Entity Discovery Agent.
Based on the Plan-Guided Entity Discovery Framework (PGEDF).
"""

INITIAL_PLANNING_PROMPT = """
You are a biomedical entity discovery planner. Your goal is to analyze the user's query and prepare for parallel web exploration to find matching entities in an unknown corpus.

**System Rationale (Why acts this way):**
*   **Forced Diversity:** We spawn multiple workers with *non-overlapping* strategies to prevent "echo chambers" where everyone searches the same terms.
*   **Late Binding:** We generate synonyms *now* (Discovery Phase) to maximize recall, but verify constraints *later* (Verification Phase) to maximize precision.
*   **Echo Chambers:** If all workers use the same top-level synonyms, we waste budget on duplicate results. Divergent strategies (e.g., one checking conferences, one checking regional patents) yield higher novelty.

Query: {query}

Perform the following analysis:

1. **Query Structure Analysis:**
   Parse the query to identify:
   - Target entity type (e.g., "CDK12 inhibitors", "EGFR antibodies", "KRAS G12C inhibitors")
   - Constraints that must be satisfied:
     * Hard constraints: MUST match (e.g., "CDK12 target")
     * Soft constraints: Prefer but not required (e.g., "preclinical stage")
     * Geographic constraints: Specific country/region (e.g., "Japan", "Germany")
     * Semantic constraints: Entity categories to find (e.g., "small molecules", "biologics")
   - Modality if specified: small molecule, biologic, antibody, ADC, etc.
   - Development stage if specified: preclinical, Phase 1/2/3, IND-enabling, approved, discontinued
   - Indication if specified: disease name, cancer type, specific condition
   - Geography if specified: country, region, or company location

2. **Comprehensive Synonym Generation:**
   Generate synonyms for all query components using domain knowledge and ontologies:

   **Target synonyms:**
   - Protein names: full names, abbreviations, gene symbols
   - Official names and aliases from UniProt
   - All known short forms and variants
   Example: "CDK12" → ["cyclin-dependent kinase 12", "CrkRS", "CRKRS", "cell division protein kinase 12"]

   **Indication synonyms:**
   - Full disease names and abbreviations
   - Clinical codes and classifications
   - MeSH standardized medical terms
   Example: "TNBC" → ["triple-negative breast cancer", "ER-PR-HER2-", "triple negative breast neoplasm"]

   **Cross-lingual variants (if geographic constraint present):**
   - Translate target and indication to target language
   - Include transliterations and romanizations
   Example: If query mentions a non-English speaking region → generate translations in that language

   **Chemical variants (if applicable for small molecules):**
   - Salt forms (e.g., "hydrochloride", "mesylate")
   - Stereoisomers (R/S configurations)
   - Prodrug forms

   Use your knowledge of these ontologies: ChEMBL, MeSH, UniProt, DrugBank

3. **Initial Worker Spawn Strategy:**
   Decide how to start exploration based on query complexity:

   **Simple query (single target, no geography):**
   - Spawn 1 worker: Broad English search
   - Reserve 70% budget for adaptive spawning

   **Geographic constraint present:**
   - Spawn 2 workers: Broad English + target-language search
   - Reserve 60% budget

   **Highly specific query (multiple constraints):**
   - Spawn 2-3 workers with diverse strategies
   - Each worker uses different synonym combinations
   - Reserve 50-60% budget

   For each worker, specify:
   - Unique strategy (must not overlap with other workers)
   - Query template using synonyms
   - Page budget (typically 40-50 pages per iteration)

Output as JSON matching this schema:
{{
  "query_analysis": {{
    "target": "string (main entity type being searched)",
    "constraints": {{
      "hard": ["constraint that must match"],
      "soft": ["constraint that is preferred"],
      "geographic": ["country or region"],
      "semantic": ["entity category to find"]
    }},
    "modality": "string or null (small molecule, biologic, etc.)",
    "stage": "string or null (preclinical, Phase 1, etc.)",
    "indication": "string or null (disease or condition)",
    "geography": "string or null (country or region)"
  }},
  "synonyms": {{
    "target": ["synonym1", "synonym2", "..."],
    "indication": ["synonym1", "synonym2", "..."],
    "cross_lingual": ["translation1", "translation2", "..."],
    "chemical": ["salt1", "stereoisomer1", "..."]
  }},
  "initial_workers": [
    {{
      "worker_id": "worker_1",
      "strategy": "broad_english_search",
      "strategy_description": "Search using target + indication synonyms broadly",
      "example_queries": [
        "CDK12 inhibitor",
        "cyclin-dependent kinase 12 inhibitor",
        "CDK12 TNBC"
      ],
      "page_budget": 50
    }},
    {{
      "worker_id": "worker_2",
      "strategy": "regional_language_search",
      "strategy_description": "Search using target language translations for geographic constraint",
      "example_queries": [
        "CDK12 inhibitor [country/region]",
        "[translated target] [translated indication]"
      ],
      "page_budget": 50
    }}
  ],
  "budget_reserve_pct": 60,
  "reasoning": "Brief explanation of why this initial strategy was chosen"
}}

**Important guidelines:**
- Be comprehensive with synonyms - these are critical for discovery
- Ensure worker strategies do NOT overlap (forced diversity)
- Typical initial spawn: 1-3 workers (not more)
- Reserve 50-70% budget for adaptive spawning during execution
- Query templates should use actual synonyms generated, not placeholders
"""
