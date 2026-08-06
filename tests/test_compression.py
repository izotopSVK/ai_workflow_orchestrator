from __future__ import annotations

import pytest

from workflows.dev_orchestrator.config import DevOrchestratorConfig
from workflows.dev_orchestrator.copilot import GitHubCopilotLLM, StaticTokenProvider
from workflows.dev_orchestrator.factory import build_copilot_llm
from workflows.llm.cache import configure_llm_cache
from workflows.llm.compression import (
    HeadroomCompressor,
    NoOpCompressor,
    build_compressor,
)


class RecordingCompressor:
    """Test double that tags messages so we can assert it ran before invoke."""

    def __init__(self):
        self.calls: list[str] = []

    def compress_messages(self, messages, *, model):
        self.calls.append(model)
        return [(role, f"[c]{content}") for role, content in messages]

    def compress_text(self, text, *, kind="generic"):
        return f"[c]{text}"


# --- compressor building blocks ---------------------------------------------

def test_noop_compressor_is_identity():
    c = NoOpCompressor()
    msgs = [("system", "s"), ("human", "h")]
    assert c.compress_messages(msgs, model="m") == msgs
    assert c.compress_text("hello") == "hello"


def test_build_compressor_selects_impl():
    assert isinstance(build_compressor("none"), NoOpCompressor)
    assert isinstance(build_compressor("headroom"), HeadroomCompressor)
    with pytest.raises(ValueError):
        build_compressor("bogus")


def test_headroom_falls_back_when_sdk_missing():
    # headroom-ai isn't installed here; adapter must degrade to a no-op, never raise.
    c = HeadroomCompressor()
    msgs = [("human", "keep me")]
    assert c.compress_messages(msgs, model="m") == msgs
    assert c.compress_text("keep me") == "keep me"


# --- wiring into the LLM ----------------------------------------------------

def test_llm_applies_compressor_before_invoke():
    rec = RecordingCompressor()
    llm = GitHubCopilotLLM(
        token_provider=StaticTokenProvider("t"),
        model="chatgpt-5.6-terra",
        compressor=rec,
    )
    messages = llm.prepare_messages("analyze this", "analyze")
    assert rec.calls == ["chatgpt-5.6-terra"]
    assert all(content.startswith("[c]") for _, content in messages)


def test_llm_defaults_to_noop_compressor():
    llm = GitHubCopilotLLM(token_provider=StaticTokenProvider("t"))
    messages = llm.prepare_messages("hi", "plan")
    # NoOp leaves content untouched: the human message is exactly what we passed.
    assert ("human", "hi") in messages
    assert not any(content.startswith("[c]") for _, content in messages)


# --- factory: compressor + proxy mode ---------------------------------------

def test_factory_wires_headroom_compressor():
    config = DevOrchestratorConfig(compressor="headroom")
    llm = build_copilot_llm(config, token_provider=StaticTokenProvider("t"))
    assert isinstance(llm._compressor, HeadroomCompressor)


def test_factory_proxy_mode_overrides_base_url():
    config = DevOrchestratorConfig(headroom_proxy_url="http://localhost:8899")
    llm = build_copilot_llm(config, token_provider=StaticTokenProvider("t"))
    assert llm._factory_for("plan")._base_url == "http://localhost:8899"


# --- LLM response cache -----------------------------------------------------

def test_configure_llm_cache_toggles_global():
    from langchain_core.globals import get_llm_cache

    try:
        configure_llm_cache("memory")
        assert get_llm_cache() is not None
        configure_llm_cache("none")
        assert get_llm_cache() is None
    finally:
        configure_llm_cache("none")


def test_configure_llm_cache_rejects_unknown():
    with pytest.raises(ValueError):
        configure_llm_cache("bogus")


# --- MVP planner LLM --------------------------------------------------------

def test_mvp_planner_applies_compressor():
    from workflows.llm.factory import CopilotWorkflowLLM

    rec = RecordingCompressor()
    llm = CopilotWorkflowLLM(
        model="chatgpt-5.6-terra",
        base_url="https://api.githubcopilot.com",
        token_provider=StaticTokenProvider("t"),
        compressor=rec,
    )
    messages = llm.prepare_messages("Draft a status report")
    assert rec.calls == ["chatgpt-5.6-terra"]
    assert all(content.startswith("[c]") for _, content in messages)


def test_build_llm_wires_compressor_and_proxy():
    from workflows.llm.factory import CopilotWorkflowLLM, build_llm

    llm = build_llm(
        "github_copilot",
        compressor="headroom",
        headroom_proxy_url="http://localhost:8877",
        token_provider=StaticTokenProvider("t"),
    )
    assert isinstance(llm, CopilotWorkflowLLM)
    assert isinstance(llm._compressor, HeadroomCompressor)
    assert llm._factory._base_url == "http://localhost:8877"
    configure_llm_cache("none")


def test_build_llm_fake_ignores_compression():
    from workflows.llm.factory import FakeWorkflowLLM, build_llm

    llm = build_llm("fake", compressor="headroom")
    assert isinstance(llm, FakeWorkflowLLM)
