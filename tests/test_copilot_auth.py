from __future__ import annotations

import time

import httpx
import pytest

from workflows.dev_orchestrator.config import DevOrchestratorConfig
from workflows.dev_orchestrator.copilot import GitHubCopilotLLM
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
    assert llm._factory._model == "claude-3.5-sonnet"
    assert llm._factory._base_url == config.copilot_base_url


def test_build_real_deps_wires_copilot_llm():
    config = DevOrchestratorConfig(target_repo_path="/tmp/fake-yii")
    deps = build_real_deps(config, token_provider=StaticTokenProvider("tok"))
    assert isinstance(deps, DevOrchestratorDeps)
    assert isinstance(deps.llm, GitHubCopilotLLM)


def test_build_real_deps_requires_target_repo():
    with pytest.raises(ValueError):
        build_real_deps(DevOrchestratorConfig(), token_provider=StaticTokenProvider("tok"))
