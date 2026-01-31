"""
Pricing configuration and calculation utilities.
"""

from typing import Any


# Pricing configuration (Cost in USD)
PRICING_CONFIG: dict[str, Any] = {
    # LLM Pricing (per million tokens)
    "llm": {
        "gemini-2.0-flash-exp": {"input": 0.0, "output": 0.0},  # Free preview (Correct)
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30},  # Correct for standard context
        "gemini-1.5-pro": {"input": 1.25, "output": 5.00},  # Updated from user's 3.50/10.50
        "gemini-pro": {"input": 0.50, "output": 1.50},  # Legacy 1.0 (Correct)
        "gemini-2.5-flash-lite": {
            "input": 0.10,
            "output": 0.40,
        },  # Updated from user's 0.075/0.30
        "gemini-3-flash-preview": {
            "input": 0.50,
            "output": 3.00,
        },  # Added model
        # Default fallback (updated to match latest flash-lite rates)
        "default": {"input": 0.10, "output": 0.40},
    },
    # Search Pricing (per 1000 requests)
    "search": {
        "tavily": 8.00,  # Updated from user's 5.00
        "perplexity": 5.00,  # $5 per 1000 searches (Search API plan) (Correct)
    },
    # Extraction Pricing (per 1000 pages)
    "crawling": {
        "llama-cloud": 3.00,  # $0.003 per page (Correct)
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
