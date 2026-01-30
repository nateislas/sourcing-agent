"""
LLM Factory for the Deep Research Application.
Provides a configured LlamaIndex Google GenAI instance.
"""

import os
from llama_index.llms.google_genai import GoogleGenAI


def get_llm(model_name: str = "models/gemini-1.5-flash"):
    """
    Returns a configured LlamaIndex Google GenAI instance.
    The API key is retrieved from GEMINI_API_KEY or GOOGLE_API_KEY environment variables.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY or GOOGLE_API_KEY is not set in the environment"
        )

    # Map friendly names to Gemini API model names if needed
    api_model_name = model_name
    if not model_name.startswith("models/"):
        api_model_name = f"models/{model_name}"

    return GoogleGenAI(model=api_model_name, api_key=api_key)
