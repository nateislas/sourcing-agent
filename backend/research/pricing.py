"""
Pricing configuration and calculation utilities.
"""

from typing import Any


# Pricing configuration (Cost in USD)
# TODO: Review and update pricing quarterly from official sources
# Last verified: 2026-01-31
# Sources:
# - Google AI: https://ai.google.dev/pricing
# - Tavily: https://tavily.com/pricing
# - Perplexity: https://docs.perplexity.ai/pricing
# - LlamaCloud: https://www.llamaindex.ai/pricing
PRICING_CONFIG: dict[str, Any] = {
    # LLM Pricing (per million tokens)
    "llm": {
        "gemini-2.0-flash-exp": {"input": 0.0, "output": 0.0},  # Free preview (verified)
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30},  # Verified
        "gemini-1.5-pro": {"input": 1.25, "output": 5.00},  # Verified
        # UNVERIFIED: Legacy models - pricing may have changed
        "gemini-pro": {"input": 0.50, "output": 1.50},  # UNVERIFIED - Legacy 1.0
        # UNVERIFIED: Preview models - no public pricing available
        # "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},  # UNVERIFIED
        # "gemini-3-flash-preview": {"input": 0.50, "output": 3.00},  # UNVERIFIED
        # Default fallback
        "default": {"input": 0.075, "output": 0.30},  # Use flash pricing as default
    },
    # Search Pricing (per 1000 requests)
    "search": {
        "tavily_basic": 8.00,  # $8/1000 for basic search (verified)
        "tavily_advanced": 16.00,  # $16/1000 for advanced search (verified)
        "tavily": 8.00,  # Default to basic pricing
        "perplexity": 5.00,  # $5/1000 searches (verified)
    },
    # Extraction Pricing
    "crawling": {
        # UNVERIFIED: LlamaCloud uses tiered pricing, not flat $0.003/page
        # TODO: Implement tiered pricing based on actual LlamaCloud pricing tiers
        "llama-cloud": 3.00,  # UNVERIFIED - placeholder at $3/1000 pages
    },
}



def calculate_llm_cost(
    model_name: str, input_tokens: float, output_tokens: float
) -> float:
    """Calculates cost for LLM usage."""
    # Normalize model name
    if "gemini-1.5-flash" in model_name:
        key = "gemini-1.5-flash"
    elif "gemini-1.5-pro" in model_name:
        key = "gemini-1.5-pro"
    elif "gemini-2.0-flash" in model_name:
        key = "gemini-2.0-flash-exp"
    elif "gemini-2.5-flash-lite" in model_name:
        key = "gemini-2.5-flash-lite"
    elif "gemini-3-flash-preview" in model_name:
        key = "gemini-3-flash-preview"
    else:
        key = "default"

    prices = PRICING_CONFIG["llm"].get(key, PRICING_CONFIG["llm"]["default"])

    input_cost = (input_tokens / 1_000_000) * float(prices["input"])
    output_cost = (output_tokens / 1_000_000) * float(prices["output"])

    return input_cost + output_cost


def calculate_search_cost(engine: str, count: int = 1) -> float:
    """Calculates cost for search queries."""
    price_per_k = float(PRICING_CONFIG["search"].get(engine.lower(), 5.00))
    return (count / 1000) * price_per_k


def calculate_crawling_cost(pages: int) -> float:
    """Calculates cost for LlamaCloud extraction/crawling."""
    price_per_k = float(PRICING_CONFIG["crawling"]["llama-cloud"])
    return (pages / 1000) * price_per_k
