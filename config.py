"""Configuration for the multi-agent software pipeline."""
import os

# Local LLM (Ollama)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.getenv("SOFTWARE_AGENT_MODEL", "llama3")

# Output
OUTPUT_DIR = os.getenv("SOFTWARE_OUTPUT_DIR", "./generated_project")
MAX_REVIEW_ITERATIONS = 3
MAX_DEBUG_ITERATIONS = 3
MAX_DOCKER_TEST_ITERATIONS = 3
