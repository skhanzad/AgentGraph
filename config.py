"""Configuration for the multi-agent software pipeline."""
import os

# Local LLM (Ollama)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.getenv("SOFTWARE_AGENT_MODEL", "llama3")

# Output
OUTPUT_DIR = os.getenv("SOFTWARE_OUTPUT_DIR", "./generated_project")
MAX_REVIEW_ITERATIONS = 3
MAX_DEBUG_ITERATIONS = 3

# Memory / RAG
MEMORY_DIR = os.getenv("AGENT_MEMORY_DIR", "./.agentgraph_memory")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))
ENABLE_WEB_SEARCH = os.getenv("ENABLE_WEB_SEARCH", "true").lower() == "true"
RAG_MAX_CONTEXT_CHARS = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "3000"))
WEB_SEARCH_AGENTS = {"architect", "coder", "debugger", "devops"}
