"""RAG Pipeline: retrieval from memory + web documentation search."""
from __future__ import annotations

import warnings

from memory import MemoryStore
from config import RAG_TOP_K, RAG_MAX_CONTEXT_CHARS, ENABLE_WEB_SEARCH, WEB_SEARCH_AGENTS

warnings.filterwarnings(
    "ignore",
    message=r"This package \(`duckduckgo_search`\) has been renamed to `ddgs`!.*",
    category=RuntimeWarning,
)

# Default collections each agent queries
_AGENT_COLLECTIONS: dict[str, list[str]] = {
    "orchestrator": ["episodic"],
    "pm":           ["episodic", "architecture"],
    "architect":    ["architecture", "knowledge"],
    "planner":      ["architecture", "codebase"],
    "coder":        ["codebase", "architecture", "knowledge"],
    "reviewer":     ["codebase", "episodic"],
    "tester":       ["codebase", "episodic"],
    "debugger":     ["codebase", "episodic", "knowledge"],
    "docs":         ["architecture", "codebase", "episodic"],
    "devops":       ["architecture", "codebase", "knowledge"],
}


# ---------- public API ----------

def build_rag_context(
    agent_name: str,
    query: str,
    web_query: str = "",
) -> str:
    """Assemble RAG context for an agent: memory retrieval + optional web docs.

    Returns a formatted string ready to inject into the LLM prompt, or "" if empty.
    """
    mem = MemoryStore.get()

    parts: list[str] = []

    # 1. Retrieve from memory collections scoped to this agent
    collections = _AGENT_COLLECTIONS.get(agent_name, ["episodic"])
    docs = mem.retrieve_multi(collections, query, k=RAG_TOP_K)
    if docs:
        parts.append("### Retrieved from project memory\n" + "\n---\n".join(docs))

    # 2. Web doc search (only for designated agents)
    if ENABLE_WEB_SEARCH and agent_name in WEB_SEARCH_AGENTS and web_query:
        web_ctx = search_web_docs(web_query)
        if web_ctx:
            parts.append(web_ctx)

    if not parts:
        return ""

    ctx = "\n\n".join(parts)
    if len(ctx) > RAG_MAX_CONTEXT_CHARS:
        ctx = ctx[:RAG_MAX_CONTEXT_CHARS] + "\n... (truncated)"
    return ctx


def store_output(agent_name: str, content: str, collection: str = "episodic"):
    """Store an agent's output in memory."""
    if not content or not content.strip():
        return
    mem = MemoryStore.get()
    mem.store(collection, content, metadata={"agent": agent_name})


def index_code(code_artifacts: dict[str, str], task_to_file: dict[str, str]):
    """Index code artifacts into the codebase collection for RAG retrieval."""
    mem = MemoryStore.get()
    for task_id, code in code_artifacts.items():
        file_path = task_to_file.get(task_id, task_id)
        mem.store_code(file_path, code)


# ---------- web search ----------

def search_web_docs(query: str, max_results: int = 3) -> str:
    """Search the web for documentation, return formatted context string.

    Uses DuckDuckGo (no API key). Falls back gracefully on any error.
    Caches fetched content in the knowledge collection for future retrieval.
    """
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                from duckduckgo_search import DDGS
        except ImportError:
            return ""

    mem = MemoryStore.get()

    # Check cache first
    cached = mem.retrieve("knowledge", query, k=2)
    if cached:
        return "### Cached documentation\n" + "\n---\n".join(cached)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return ""
    except Exception:
        return ""

    parts: list[str] = []
    for r in results:
        title = r.get("title", "")
        body = r.get("body", "")
        href = r.get("href", "")
        snippet = f"**{title}**\n{body}\n(Source: {href})"
        parts.append(snippet)

    # Fetch full page content from the first result for richer context
    first_url = results[0].get("href", "")
    if first_url:
        page = _fetch_page(first_url)
        if page:
            parts.append(f"### Documentation page content\n{page}")
            # Cache in knowledge collection
            mem.store_knowledge(page[:4000], metadata={"source": first_url, "type": "web_doc"})

    return "### Web documentation\n" + "\n\n".join(parts)


def _fetch_page(url: str, max_chars: int = 3000) -> str:
    """Fetch a documentation page and extract its text content."""
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        return ""

    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove non-content elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        # Prefer main content area
        main = soup.find("main") or soup.find("article") or soup.find(role="main")
        target = main or soup.body or soup

        text = target.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        content = "\n".join(lines)
        return content[:max_chars]
    except Exception:
        return ""
