"""
LLM Factory - Wrapper for backward compatibility.
Re-exports get_llm from llm.py.
"""

from backend.research.llm import get_llm

__all__ = ["get_llm"]
