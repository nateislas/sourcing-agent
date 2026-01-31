"""
LLM Factory for the Deep Research Application.
Provides a configured LlamaIndex Google GenAI instance.
"""

import os
from typing import Any
import logging

from llama_index.core.program import LLMTextCompletionProgram
from llama_index.llms.google_genai import GoogleGenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from google.api_core.exceptions import ResourceExhausted, ServerError

from backend.research.pricing import calculate_llm_cost

logger = logging.getLogger(__name__)


class LLMHandler:
    """Wrapper for GoogleGenAI to add retries on rate limits and server overloads."""
    def __init__(self, llm: GoogleGenAI, thinking_budget: int | None = None):
        self.llm = llm
        self.thinking_budget = thinking_budget

    @property
    def model(self):
        return self.llm.model

    @retry(
        retry=retry_if_exception_type((ResourceExhausted, ServerError)),
        wait=wait_exponential(multiplier=1, min=4, max=20),
        stop=stop_after_attempt(5),
        before_sleep=lambda retry_state: logger.warning(
            f"LLM Error during acomplete: {retry_state.outcome.exception()}. Retrying in {retry_state.next_action.sleep}s... (Attempt {retry_state.attempt_number})"
        ),
    )
    async def acomplete(self, *args, **kwargs):
        if self.thinking_budget and "gemini-3" in self.model:
            # Inject thinking_config into the request parameters
            # LlamaIndex passes extra kwargs to the underlying generate_content call
            kwargs.setdefault("thinking_config", {
                "include_thoughts": True,
                "token_limit": self.thinking_budget
            })
        return await self.llm.acomplete(*args, **kwargs)

    @retry(
        retry=retry_if_exception_type((ResourceExhausted, ServerError)),
        wait=wait_exponential(multiplier=1, min=4, max=20),
        stop=stop_after_attempt(5),
        before_sleep=lambda retry_state: logger.warning(
            f"LLM Error during achat: {retry_state.outcome.exception()}. Retrying in {retry_state.next_action.sleep}s... (Attempt {retry_state.attempt_number})"
        ),
    )
    async def achat(self, *args, **kwargs):
        if self.thinking_budget and "gemini-3" in self.model:
             # Inject thinking_config into the request parameters
            kwargs.setdefault("thinking_config", {
                "include_thoughts": True,
                "token_limit": self.thinking_budget
            })
        return await self.llm.achat(*args, **kwargs)

    def __getattr__(self, name):
        """Proxy all other attributes to the underlying LLM."""
        return getattr(self.llm, name)


def get_llm(model_name: str | None = None, thinking_budget: int | None = None, temperature: float | None = None):
    """
    Returns a configured LLMHandler instance (wrapped GoogleGenAI).
    The API key is retrieved from GEMINI_API_KEY or GOOGLE_API_KEY environment variables.
    """
    if model_name is None:
        model_name = os.getenv("DEFAULT_LLM_MODEL")
        if not model_name:
             logger.warning("DEFAULT_LLM_MODEL not set in .env. Falling back to gemini-2.0-flash.")
             model_name = "gemini-2.0-flash"

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY or GOOGLE_API_KEY is not set in the environment"
        )

    # Standardize model name
    if model_name:
        if not (model_name.startswith("models/") or model_name.startswith("tunedModels/")):
            model_name = f"models/{model_name}"
    else:
        model_name = "models/gemini-2.0-flash"

    # Configure thinking mode for models that support it (gemini-3 or thinking experimental models)
    pass_thinking_config = False
    if thinking_budget:
        if "gemini-3" in model_name or "thinking" in model_name:
            pass_thinking_config = True

    kwargs = {}
    if pass_thinking_config:
        # Note: LlamaIndex GoogleGenAI passes extra kwargs to the GenerativeModel
        # Gemini Thinking mode uses thinking_config
        kwargs["thinking_config"] = {
            "include_thoughts": True,
            "token_limit": thinking_budget
        }

    # Pass temperature if provided
    if temperature is not None:
        kwargs["temperature"] = temperature

    llm = GoogleGenAI(model=model_name, api_key=api_key, **kwargs)
    return LLMHandler(llm, thinking_budget=thinking_budget)


class LLMClient:
    """
    Wrapper around LlamaIndex/Gemini for simplified interaction.
    Supports structured output generation.
    """

    def __init__(self, model_name: str | None = None, thinking_budget: int | None = None, temperature: float | None = None):
        if model_name is None:
            model_name = os.getenv("DEFAULT_LLM_MODEL")
            if not model_name:
                logger.warning("DEFAULT_LLM_MODEL not set in .env. Falling back to gemini-2.0-flash.")
                model_name = "gemini-2.0-flash"
        self.llm = get_llm(model_name, thinking_budget=thinking_budget, temperature=temperature)

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
