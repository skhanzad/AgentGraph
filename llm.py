"""Ollama LLM factory for local inference."""
from __future__ import annotations

from typing import Any, Mapping

from langchain_ollama import ChatOllama

from config import OLLAMA_BASE_URL, DEFAULT_MODEL


def get_llm(model: str | None = None, temperature: float = 0.3):
    """Create a ChatOllama instance. Ensure Ollama is running and model is pulled."""
    return ChatOllama(
        model=model or DEFAULT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=temperature,
    )


def get_state_model(state: Mapping[str, Any] | None) -> str | None:
    """Return the requested model override from graph state, if present."""
    if not state:
        return None
    model = str(state.get("model_name", "") or "").strip()
    return model or None


def get_state_llm(state: Mapping[str, Any] | None, temperature: float = 0.3):
    """Create an LLM instance honoring any per-run model override."""
    return get_llm(model=get_state_model(state), temperature=temperature)
