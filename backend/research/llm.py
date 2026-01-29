"""
LLM Client configuration and factory.
Wraps the llama-index-llms-gemini library.
"""

from llama_index.llms.google_genai import GoogleGenAI

from backend.config import GEMINI_API_KEY as KEY


def get_llm(model_name: str = "models/gemini-1.5-flash"):
    """
    Returns a configured LlamaIndex Google GenAI instance.
    """
    if not KEY:
        raise ValueError("GEMINI_API_KEY is not set in the environment or config.py")

    # Map friendly names to Gemini API model names if needed
    # LlamaIndex GoogleGenAI usually expects "models/gemini-..."
    api_model_name = model_name
    if not model_name.startswith("models/"):
        api_model_name = f"models/{model_name}"

    return GoogleGenAI(model=api_model_name, api_key=KEY)
