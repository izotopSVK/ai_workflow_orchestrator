"""Small text utilities shared across the dev orchestrator."""

from __future__ import annotations


def keyword_score(query: str, text: str) -> int:
    """Naive keyword-overlap score: how many >2-char query words appear in text.

    Shared by memory (lesson/episode retrieval) and the skills library. A real
    deployment swaps this for embedding similarity.
    """
    q = {w for w in query.lower().split() if len(w) > 2}
    t = text.lower()
    return sum(1 for w in q if w in t)
