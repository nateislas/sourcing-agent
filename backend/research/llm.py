"""
LLM Factory for the Deep Research Application.
Provides a configured LlamaIndex Google GenAI instance.
"""

import os
from typing import Any
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.core.program import LLMTextCompletionProgram


def get_llm(model_name: str = None):
    """
    Returns a configured LlamaIndex Google GenAI instance.
    The API key is retrieved from GEMINI_API_KEY or GOOGLE_API_KEY environment variables.
    """
    if model_name is None:
        model_name = os.getenv("DEFAULT_LLM_MODEL", "gemini-1.5-flash")
    
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


class LLMClient:
    """
    Wrapper around LlamaIndex/Gemini for simplified interaction.
    Supports structured output generation.
    """

    def __init__(self, model_name: str = None):
        if model_name is None:
            model_name = os.getenv("DEFAULT_LLM_MODEL", "gemini-2.5-flash-lite")
        self.llm = get_llm(model_name)

    async def generate(self, prompt: str, response_model: Any = None):
        """
        Generates a response from the LLM.
        If response_model is provided, attempts to generate structured JSON matching the Pydantic model.
        """
        if response_model:
            try:
                # Use LlamaIndex Text Completion Program for structured output
                program = LLMTextCompletionProgram.from_defaults(
                    output_cls=response_model,
                    llm=self.llm,
                    prompt_template_str="{prompt}"
                )
                return await program.acall(prompt=prompt)
            except Exception as e:
                # Simple fallback or logging could go here
                raise e
        else:
            response = await self.llm.acomplete(prompt)
            return response.text
