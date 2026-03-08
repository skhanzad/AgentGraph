"""Shared Memory Store: ChromaDB-backed vector storage for agent episodic, code, and knowledge memory."""
import hashlib
import json
import os
import re
from typing import Optional

import chromadb
from langchain_ollama import OllamaEmbeddings

from config import OLLAMA_BASE_URL, MEMORY_DIR, EMBEDDING_MODEL


class _OllamaChromaEF(chromadb.EmbeddingFunction):
    """Adapts langchain OllamaEmbeddings to ChromaDB's EmbeddingFunction protocol."""

    def __init__(self, model: str, base_url: str):
        self._ef = OllamaEmbeddings(model=model, base_url=base_url)

    def __call__(self, input: list[str]) -> list[list[float]]:
        return self._ef.embed_documents(input)


class MemoryStore:
    """ChromaDB-backed memory store with scoped collections.

    Collections:
        episodic   - agent outputs, decisions, feedback (project history)
        codebase   - generated code indexed by file path
        architecture - architecture docs, PRD, design decisions
        knowledge  - persistent knowledge: resolved bugs, patterns, cached web docs
    """

    _instance: Optional["MemoryStore"] = None
    PROJECT_COLLECTIONS = ("episodic", "codebase", "architecture")

    @classmethod
    def get(cls) -> "MemoryStore":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        os.makedirs(MEMORY_DIR, exist_ok=True)
        self._client = None
        self._client_available = False
        try:
            self._client = chromadb.PersistentClient(path=MEMORY_DIR)
            self._client_available = True
        except Exception as e:
            print(f"  [memory] Chroma persistence unavailable ({e}). Falling back to JSON-only memory.")
        try:
            self._ef = _OllamaChromaEF(model=EMBEDDING_MODEL, base_url=OLLAMA_BASE_URL)
            # Quick test to verify the embedding model is available
            self._ef(["test"])
            self._available = self._client_available
        except Exception as e:
            print(f"  [memory] Embedding model '{EMBEDDING_MODEL}' unavailable ({e}). "
                  f"Run: ollama pull {EMBEDDING_MODEL}")
            print("  [memory] Pipeline will proceed without RAG.")
            self._available = False
        self._collections: dict[str, chromadb.Collection] = {}

    def _fallback_path(self, collection: str) -> str:
        return os.path.join(MEMORY_DIR, f"{collection}.json")

    def _load_fallback_docs(self, collection: str) -> list[dict]:
        path = self._fallback_path(collection)
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save_fallback_docs(self, collection: str, docs: list[dict]) -> None:
        try:
            with open(self._fallback_path(collection), "w", encoding="utf-8") as f:
                json.dump(docs, f, ensure_ascii=True, indent=2)
        except Exception:
            pass

    def _upsert_fallback_doc(
        self,
        collection: str,
        doc_id: str,
        content: str,
        metadata: dict | None = None,
    ) -> None:
        docs = self._load_fallback_docs(collection)
        record = {"id": doc_id, "document": content[:6000], "metadata": metadata or {}}
        replaced = False
        for idx, existing in enumerate(docs):
            if existing.get("id") == doc_id:
                docs[idx] = record
                replaced = True
                break
        if not replaced:
            docs.append(record)
        self._save_fallback_docs(collection, docs)

    def _clear_fallback_docs(self, collection: str) -> None:
        path = self._fallback_path(collection)
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                self._save_fallback_docs(collection, [])

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {token for token in re.findall(r"[A-Za-z0-9_]+", text.lower()) if len(token) > 1}

    def _fallback_retrieve(self, collection: str, query: str, k: int = 3) -> list[str]:
        docs = self._load_fallback_docs(collection)
        if not docs:
            return []

        query_tokens = self._tokenize(query)
        scored: list[tuple[int, int, str]] = []
        for idx, record in enumerate(docs):
            content = record.get("document", "")
            if not content:
                continue
            doc_tokens = self._tokenize(content)
            score = len(query_tokens & doc_tokens)
            if score == 0 and query.lower() not in content.lower():
                continue
            scored.append((score, idx, content))

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [content for _, _, content in scored[:k]]

    @property
    def available(self) -> bool:
        return self._available

    def _col(self, name: str) -> chromadb.Collection:
        if self._client is None:
            raise RuntimeError("Chroma client unavailable")
        if name not in self._collections:
            kwargs = {"name": name}
            if self._available:
                kwargs["embedding_function"] = self._ef
            self._collections[name] = self._client.get_or_create_collection(**kwargs)
        return self._collections[name]

    @staticmethod
    def _doc_id(prefix: str, content: str) -> str:
        h = hashlib.sha256(content[:300].encode()).hexdigest()[:16]
        return f"{prefix}_{h}"

    # ---------- write ----------

    def store(
        self,
        collection: str,
        content: str,
        metadata: dict | None = None,
        doc_id: str | None = None,
    ):
        """Upsert a document into the named collection."""
        if not content or not content.strip():
            return
        doc_id = doc_id or self._doc_id(collection, content)
        self._upsert_fallback_doc(collection, doc_id, content, metadata)
        if not self._available:
            return
        try:
            col = self._col(collection)
            col.upsert(
                ids=[doc_id],
                documents=[content[:6000]],
                metadatas=[metadata or {}],
            )
        except Exception:
            pass

    def store_code(self, file_path: str, code: str):
        self.store("codebase", code, metadata={"file": file_path}, doc_id=f"code_{file_path}")

    def store_decision(self, agent: str, content: str):
        self.store("architecture", content, metadata={"agent": agent})

    def store_knowledge(self, content: str, metadata: dict | None = None):
        self.store("knowledge", content, metadata=metadata)

    def store_episode(self, agent: str, content: str):
        self.store("episodic", content, metadata={"agent": agent})

    # ---------- read ----------

    def retrieve(self, collection: str, query: str, k: int = 3) -> list[str]:
        """Return top-k relevant documents from a collection."""
        if not self._available:
            return self._fallback_retrieve(collection, query, k=k)
        try:
            col = self._col(collection)
            count = col.count()
            if count == 0:
                return self._fallback_retrieve(collection, query, k=k)
            results = col.query(query_texts=[query], n_results=min(k, count))
            docs = results.get("documents", [[]])[0]
            return docs or self._fallback_retrieve(collection, query, k=k)
        except Exception:
            return self._fallback_retrieve(collection, query, k=k)

    def retrieve_multi(self, collections: list[str], query: str, k: int = 3) -> list[str]:
        """Retrieve from multiple collections, merge results."""
        docs: list[str] = []
        seen: set[str] = set()
        for name in collections:
            for doc in self.retrieve(name, query, k=k):
                key = doc[:200]
                if key not in seen:
                    seen.add(key)
                    docs.append(doc)
        return docs[:k * 2]  # soft cap

    def reset_project_memory(self) -> None:
        """Clear project-scoped memory while preserving durable knowledge docs."""
        for name in self.PROJECT_COLLECTIONS:
            self._clear_fallback_docs(name)
            if self._client is not None:
                try:
                    self._client.delete_collection(name=name)
                except Exception:
                    pass
            self._collections.pop(name, None)
