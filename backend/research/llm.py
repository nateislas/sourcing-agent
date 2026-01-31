"""
LLM Factory for the Deep Research Application.
Provides a configured LlamaIndex Google GenAI instance.
"""

import os
from typing import Any

from llama_index.core.program import LLMTextCompletionProgram
from llama_index.llms.google_genai import GoogleGenAI

from backend.research.pricing import calculate_llm_cost


def get_llm(model_name: str | None = None):
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

    def __init__(self, model_name: str | None = None):
        if model_name is None:
            model_name = os.getenv("DEFAULT_LLM_MODEL", "gemini-2.5-flash-lite")
        self.llm = get_llm(model_name)

    async def generate(
        self, prompt: str, response_model: Any = None
    ) -> tuple[Any, float]:
        """
        Generates a response from the LLM.
        If response_model is provided, attempts to generate structured JSON matching the Pydantic model.
        Returns:
            (result, cost) tuple.
        """
        cost = 0.0
        model_name = self.llm.model

        if response_model:
            try:
                # Use LlamaIndex Text Completion Program for structured output
                program = LLMTextCompletionProgram.from_defaults(
                    output_cls=response_model,
                    llm=self.llm,
                    prompt_template_str="{prompt}",
                )
                # LLMTextCompletionProgram doesn't easily expose raw response/usage
                # We'll estimate based on prompt length and result length?
                # Or try to inspect the last response if cached?
                # For now, let's just make a simple estimate or 0 if we can't get it.
                # Actually, program.acall returns the Pydantic object, not the response.
                # We could wrap the LLM to capture the last call, but that's complex.
                # Let's assume 0 for structured output for now unless we refactor.
                result = await program.acall(prompt=prompt)

                # Estimate tokens
                input_tokens = len(prompt) / 4  # Rough estimate
                output_tokens = 100  # Rough estimate for structured data
                cost = calculate_llm_cost(model_name, input_tokens, output_tokens)

                return result, cost
            except Exception as e:
                # Simple fallback or logging could go here
                raise e
        else:
            response = await self.llm.acomplete(prompt)

            # Extract token usage from Google GenAI response
            # Format: response.raw['usageMetadata'] = {'promptTokenCount': 123, 'candidatesTokenCount': 456, ...}
            input_tokens = 0
            output_tokens = 0
            try:
                # Type safe check
                if hasattr(response, "raw") and isinstance(response.raw, dict):
                    usage = response.raw.get("usageMetadata", {})
                    input_tokens = usage.get("promptTokenCount", 0)
                    output_tokens = usage.get("candidatesTokenCount", 0)
                elif hasattr(response, "additional_kwargs"):
                    # Other providers
                    usage = response.additional_kwargs.get("usage", {})
                    input_tokens = usage.get("prompt_tokens", 0)
                    output_tokens = usage.get("completion_tokens", 0)
            except Exception:
                pass

            # Fallback estimation if usages are 0 (e.g. streaming or mocked)
            if input_tokens == 0:
                input_tokens = len(prompt) // 4
                output_tokens = len(response.text) // 4

            cost = calculate_llm_cost(model_name, input_tokens, output_tokens)
            return response.text, cost
