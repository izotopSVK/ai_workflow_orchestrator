"""LLM response cache configuration (dedupe identical Copilot calls).

Complements Headroom's prompt-cache alignment: this is an *exact-match* response
cache — identical (prompt, params) returns the stored completion instead of a new
API call. Cheap win for retries and repeated analyze/plan prompts.

Backed by LangChain's global cache. ``configure_llm_cache`` is idempotent and
safe to call at startup or from the dev-orchestrator factory.
"""

from __future__ import annotations

_CONFIGURED: str | None = None


def configure_llm_cache(mode: str = "none", *, sqlite_path: str = ".llm_cache.sqlite") -> None:
    """Set the global LangChain LLM cache.

    ``mode``: ``"none"`` (disable), ``"memory"`` (in-process), or ``"sqlite"``
    (persists across restarts at ``sqlite_path``).
    """
    global _CONFIGURED
    mode = (mode or "none").lower()
    if mode == _CONFIGURED:
        return

    from langchain_core.globals import set_llm_cache

    if mode in ("none", "off"):
        set_llm_cache(None)
    elif mode in ("memory", "in_memory"):
        from langchain_core.caches import InMemoryCache

        set_llm_cache(InMemoryCache())
    elif mode == "sqlite":
        from langchain_community.cache import SQLiteCache

        set_llm_cache(SQLiteCache(database_path=sqlite_path))
    else:
        raise ValueError(f"Unknown llm_cache mode: {mode!r}")

    _CONFIGURED = mode
