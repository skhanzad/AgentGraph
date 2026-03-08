"""Ollama LLM factory for local inference."""
from langchain_ollama import ChatOllama

from config import OLLAMA_BASE_URL, DEFAULT_MODEL


def get_llm(model: str | None = None, temperature: float = 0.3):
    """Create a ChatOllama instance. Ensure Ollama is running and model is pulled."""
    return ChatOllama(
        model=model or DEFAULT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=temperature,
    )
