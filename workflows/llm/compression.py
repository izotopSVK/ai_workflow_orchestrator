"""Pluggable context compression for LLM calls (Headroom / RTK integration).

Reduces the tokens sent to Copilot by compressing tool outputs, RAG chunks and
conversation history before they reach the model — and keeps the prompt-cache
prefix stable so the provider KV cache is not busted.

Design mirrors the rest of the codebase: a ``ContextCompressor`` Protocol with a
zero-dependency :class:`NoOpCompressor` default and a :class:`HeadroomCompressor`
adapter for `headroom-ai <https://github.com/headroomlabs-ai/headroom>`_. Nothing
here imports ``headroom`` unless the adapter is actually used, so tests and the
default path never require it.

Two deployment modes are supported:

* **Proxy** — run ``headroom proxy`` in front of the Copilot endpoint and point
  ``copilot_base_url`` (or ``headroom_proxy_url``) at it. No code path here is
  involved; compression + CacheAligner happen in the proxy.
* **SDK** — use :class:`HeadroomCompressor` to compress messages in-process
  before ``invoke``.
"""

from __future__ import annotations

from typing import Protocol

# A chat message as LangChain accepts it: (role, content).
Message = tuple[str, str]


class ContextCompressor(Protocol):
    def compress_messages(self, messages: list[Message], *, model: str) -> list[Message]: ...

    def compress_text(self, text: str, *, kind: str = "generic") -> str: ...


class NoOpCompressor:
    """Identity compressor — the safe default; changes nothing."""

    def compress_messages(self, messages: list[Message], *, model: str) -> list[Message]:
        return messages

    def compress_text(self, text: str, *, kind: str = "generic") -> str:
        return text


class HeadroomCompressor:
    """Adapter for the ``headroom-ai`` SDK (context compression + CacheAligner).

    Requires ``pip install "headroom-ai[all]"``. ``headroom`` is imported lazily
    so importing this module never pulls it in.

    NOTE: the exact SDK call is isolated in :meth:`_compress` so it is trivial to
    align with Headroom's current API. It is written against the documented
    ``compress(messages, model=...)`` entry point; if a Headroom release changes
    the signature, only that one method needs updating. On any failure it falls
    back to returning the input uncompressed — compression must never break a run.
    """

    def __init__(self, *, model: str | None = None, options: dict | None = None):
        self._model = model
        self._options = options or {}

    def _client(self):
        import headroom  # lazy, optional dependency

        return headroom

    def _compress(self, payload, *, model: str, kind: str):
        """Single seam onto the Headroom SDK. Keep all API coupling here."""
        headroom = self._client()
        # Documented entry point: headroom.compress(messages, model=...).
        return headroom.compress(payload, model=model, **self._options)

    def compress_messages(self, messages: list[Message], *, model: str) -> list[Message]:
        try:
            compressed = self._compress(messages, model=self._model or model, kind="messages")
        except Exception:  # noqa: BLE001 - never let compression break a run
            return messages
        return compressed if compressed else messages

    def compress_text(self, text: str, *, kind: str = "generic") -> str:
        if not text:
            return text
        try:
            compressed = self._compress(
                [("user", text)], model=self._model or "unknown", kind=kind
            )
        except Exception:  # noqa: BLE001
            return text
        # Best-effort unwrap back to a string.
        if isinstance(compressed, str):
            return compressed
        if isinstance(compressed, list) and compressed:
            last = compressed[-1]
            if isinstance(last, tuple) and len(last) == 2:
                return str(last[1])
        return text


def build_compressor(name: str, *, model: str | None = None, options: dict | None = None) -> ContextCompressor:
    """Factory: ``"none"`` -> NoOp, ``"headroom"`` -> Headroom SDK adapter."""
    name = (name or "none").lower()
    if name in ("none", "noop", "off"):
        return NoOpCompressor()
    if name in ("headroom", "headroom-ai"):
        return HeadroomCompressor(model=model, options=options)
    raise ValueError(f"Unknown compressor: {name!r}")
