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


class LLMClient:
    """
    Wrapper around LlamaIndex/Gemini for simplified interaction.
    Supports structured output generation.
    """

    def __init__(self, model_name: str = "gemini-2.5-flash-lite"):
        self.llm = get_llm(model_name)

    async def generate(self, prompt: str, response_model=None):
        """
        Generates a response from the LLM.
        If response_model is provided, attempts to generate structured JSON matching the Pydantic model.
        """
        if response_model:
            # Use LlamaIndex's structured prediction capabilities
            # Currently using `as_structured_llm` if available, or prompt engineering + Pydantic validation
            try:
                sllm = self.llm.as_structured_llm(response_model)
                response = await sllm.acomplete(prompt)
                # The response object from structured LLM should be the Pydantic object directly
                # However, LlamaIndex abstraction might return a CompletionResponse with .raw which is the object
                # Let's verify standard LlamaIndex behavior:
                # sllm.complete returns the Pydantic object
                return response.raw
            except Exception:
                # Fallback to direct prompt instruction
                # (Simple implementation for now)
                from llama_index.core.program import LLMTextCompletionProgram
                
                program = LLMTextCompletionProgram.from_defaults(
                    output_cls=response_model,
                    llm=self.llm,
                    prompt_template_str="{prompt}"
                )
                return await program.acall(prompt=prompt)
        else:
            response = await self.llm.acomplete(prompt)
            return response.text
