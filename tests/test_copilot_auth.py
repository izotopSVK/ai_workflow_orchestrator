from __future__ import annotations

import time

import httpx
import pytest

from workflows.dev_orchestrator.config import DevOrchestratorConfig
from workflows.dev_orchestrator.dev_llm import GitHubCopilotLLM
from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.factory import build_copilot_llm, build_real_deps
from workflows.llm.copilot import (
    COPILOT_TOKEN_URL,
    CopilotAuthError,
    GitHubCopilotTokenProvider,
    StaticTokenProvider,
)


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_static_token_provider():
    assert StaticTokenProvider("tok").get_token() == "tok"


def test_token_exchange_and_caching():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL(COPILOT_TOKEN_URL)
        assert request.headers["Authorization"] == "token oauth-xyz"
        calls["n"] += 1
        return httpx.Response(200, json={"token": "copilot-1", "expires_at": time.time() + 1800})

    provider = GitHubCopilotTokenProvider(oauth_token="oauth-xyz", client=_client(handler))

    assert provider.get_token() == "copilot-1"
    assert provider.get_token() == "copilot-1"  # cached
    assert calls["n"] == 1  # only one exchange


def test_token_refreshes_after_expiry():
    tokens = iter(["copilot-old", "copilot-new"])

    def handler(request: httpx.Request) -> httpx.Response:
        # Already expired so a refresh is forced on every call.
        return httpx.Response(200, json={"token": next(tokens), "expires_at": time.time() - 1})

    provider = GitHubCopilotTokenProvider(oauth_token="oauth-xyz", client=_client(handler))

    assert provider.get_token() == "copilot-old"
    assert provider.get_token() == "copilot-new"  # re-exchanged


def test_missing_oauth_token_raises():
    provider = GitHubCopilotTokenProvider(oauth_token=None, client=_client(lambda r: httpx.Response(200)))
    provider._oauth_token = None  # ensure env didn't populate it
    with pytest.raises(CopilotAuthError):
        provider.get_token()


def test_failed_exchange_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="Bad credentials")

    provider = GitHubCopilotTokenProvider(oauth_token="oauth-xyz", client=_client(handler))
    with pytest.raises(CopilotAuthError):
        provider.get_token()


def test_device_flow_polls_until_authorized():
    responses = iter([
        {"error": "authorization_pending"},
        {"access_token": "gho_realtoken"},
    ])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=next(responses))

    provider = GitHubCopilotTokenProvider(oauth_token="placeholder", client=_client(handler))
    token = provider.poll_device_flow("device-code", interval=0, timeout=5)
    assert token == "gho_realtoken"


def test_build_copilot_llm_from_config_uses_static_provider():
    config = DevOrchestratorConfig(copilot_model="claude-3.5-sonnet")
    llm = build_copilot_llm(config, token_provider=StaticTokenProvider("tok"))
    assert isinstance(llm, GitHubCopilotLLM)
    # Model/base_url are threaded into the chat factory without any network call.
    assert llm.model_for("plan") == "claude-3.5-sonnet"
    assert llm._factory_for("plan")._base_url == config.copilot_base_url


def test_build_real_deps_wires_copilot_llm():
    config = DevOrchestratorConfig(target_repo_path="/tmp/fake-yii")
    deps = build_real_deps(config, token_provider=StaticTokenProvider("tok"))
    assert isinstance(deps, DevOrchestratorDeps)
    assert isinstance(deps.llm, GitHubCopilotLLM)


def test_build_real_deps_requires_target_repo():
    with pytest.raises(ValueError):
        build_real_deps(DevOrchestratorConfig(), token_provider=StaticTokenProvider("tok"))


# --- Per-agent model configuration ------------------------------------------

def test_all_agents_default_to_copilot_model():
    llm = GitHubCopilotLLM(token_provider=StaticTokenProvider("t"), model="gpt-4o")
    for role in ("analyze", "plan", "implement", "review_solid", "reflect"):
        assert llm.model_for(role) == "gpt-4o"


def test_per_agent_model_overrides():
    llm = GitHubCopilotLLM(
        token_provider=StaticTokenProvider("t"),
        model="gpt-4o",
        role_models={"implement": "claude-3.5-sonnet", "reflect": "o3-mini"},
    )
    assert llm.model_for("implement") == "claude-3.5-sonnet"
    assert llm.model_for("reflect") == "o3-mini"
    assert llm.model_for("analyze") == "gpt-4o"  # falls back to default


def test_one_factory_per_distinct_model_sharing_token_provider():
    provider = StaticTokenProvider("t")
    llm = GitHubCopilotLLM(
        token_provider=provider,
        model="gpt-4o",
        role_models={"implement": "claude-3.5-sonnet"},
    )
    # analyze + plan share the default model -> same cached factory.
    assert llm._factory_for("analyze") is llm._factory_for("plan")
    # implement uses a different model -> a distinct factory.
    assert llm._factory_for("implement") is not llm._factory_for("analyze")
    assert llm._factory_for("implement")._model == "claude-3.5-sonnet"
    # All agents share the one SSO token provider.
    assert llm._factory_for("implement")._tokens is provider
    assert llm._factory_for("analyze")._tokens is provider


def test_parse_agent_models():
    from workflows.dev_orchestrator.config import parse_agent_models

    parsed = parse_agent_models("implement=claude-3.5-sonnet, reflect=o3-mini")
    assert parsed == {"implement": "claude-3.5-sonnet", "reflect": "o3-mini"}
    assert parse_agent_models("") == {}
    assert parse_agent_models(None) == {}


def test_build_copilot_llm_threads_agent_models_from_config():
    config = DevOrchestratorConfig(agent_models={"review_solid": "o3-mini"})
    llm = build_copilot_llm(config, token_provider=StaticTokenProvider("t"))
    assert llm.model_for("review_solid") == "o3-mini"
    assert llm.model_for("implement") == config.copilot_model
