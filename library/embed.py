"""Embeddings from the local Ollama nomic-embed-text model."""
from __future__ import annotations

import logging
import os

import httpx

logging.getLogger("httpx").setLevel(logging.WARNING)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = "nomic-embed-text"
BATCH = 32


def _embed(texts: list[str]) -> list[list[float]]:
    r = httpx.post(f"{OLLAMA_URL}/api/embed",
                   json={"model": MODEL, "input": texts, "truncate": True},
                   timeout=300)
    r.raise_for_status()
    return r.json()["embeddings"]


def embed_documents(texts: list[str]) -> list[list[float]]:
    # nomic-embed-text expects task prefixes
    out: list[list[float]] = []
    for i in range(0, len(texts), BATCH):
        out.extend(_embed(["search_document: " + t for t in texts[i:i + BATCH]]))
    return out


def embed_query(text: str) -> list[float]:
    return _embed(["search_query: " + text])[0]
