"""Embedding providers for the self-learning memory.

Embeddings turn goals / lessons into vectors so retrieval can rank by semantic
similarity instead of keyword overlap. Same DI shape as everything else: a
Protocol with a deterministic Fake (no network, used in tests and offline) and a
real OpenAI-compatible adapter.

GitHub Copilot does not expose an embeddings endpoint, so real embeddings use a
separate OpenAI-compatible embeddings service (OpenAI, Azure OpenAI, or a local
server) configured independently from the chat LLM.
"""

from __future__ import annotations

import hashlib
import math
from typing import Protocol


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]: ...


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class FakeEmbeddingProvider:
    """Deterministic hashing embedder — stable, offline, good enough for tests.

    Bag-of-tokens hashed into ``dim`` buckets. Texts sharing tokens get similar
    vectors, so cosine ranking is meaningful without any model.
    """

    def __init__(self, dim: int = 64):
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in text.lower().split():
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            vec[h % self.dim] += 1.0
        return vec


class OpenAIEmbeddingProvider:  # pragma: no cover - requires network/model
    """Real embeddings via an OpenAI-compatible API (langchain-openai)."""

    def __init__(self, *, model: str = "text-embedding-3-small", base_url: str | None = None,
                 api_key: str | None = None):
        from langchain_openai import OpenAIEmbeddings

        self._client = OpenAIEmbeddings(model=model, base_url=base_url, api_key=api_key)

    def embed(self, text: str) -> list[float]:
        return self._client.embed_query(text)
