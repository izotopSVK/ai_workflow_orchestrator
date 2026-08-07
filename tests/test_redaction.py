from __future__ import annotations

import logging

import httpx
import pytest

from workflows.dev_orchestrator.tools.php_toolchain import SubprocessPhpToolchain
from workflows.llm.copilot import (
    COPILOT_TOKEN_URL,
    CopilotAuthError,
    GitHubCopilotTokenProvider,
    StaticTokenProvider,
)
from workflows.observability.redaction import (
    SecretRedactingFilter,
    install_log_redaction,
    redact,
    redact_snippet,
)


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


# --- redact() ---------------------------------------------------------------

@pytest.mark.parametrize("secret", [
    "gho_16C7e42F292c6912E7710c838347Ae178B4a",
    "ghp_1234567890abcdef1234567890abcdef1234",
    "github_pat_11ABCDEFG0abcdef1234567890_abcdefABCDEF1234567890abcd",
    "sk-proj-abcdefghijklmnopqrstuvwxyz012345",
])
def test_redact_strips_tokens(secret):
    out = redact(f"leaked token = {secret} here")
    assert secret not in out
    assert "[REDACTED:" in out


def test_redact_authorization_header_keeps_key_drops_value():
    out = redact("Authorization: token gho_16C7e42F292c6912E7710c838347Ae178B4a")
    assert "gho_" not in out
    assert "Authorization" in out  # key preserved for debugging


def test_redact_jwt_and_email_pii():
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc-DEF_123"
    out = redact(f"user john.doe@example.com token {jwt}")
    assert jwt not in out
    assert "john.doe@example.com" not in out
    assert "[REDACTED:email]" in out


def test_redact_copilot_token_blob():
    blob = "tid=abc123;exp=1700000000;sku=copilot;ssc=1;chat=1;token=deadbeef"
    out = redact(f"cookie {blob}")
    assert "deadbeef" not in out
    assert "tid=abc123" not in out


def test_redact_snippet_truncates():
    out = redact_snippet("A" * 1000, limit=100)
    assert out.endswith("…[truncated]")
    assert len(out) < 200


# --- logging filter ---------------------------------------------------------

def test_logging_filter_scrubs_records(caplog):
    logger = logging.getLogger("test.redaction")
    logger.addFilter(SecretRedactingFilter())
    logger.setLevel(logging.INFO)
    with caplog.at_level(logging.INFO, logger="test.redaction"):
        logger.info("token=%s", "gho_16C7e42F292c6912E7710c838347Ae178B4a")
    assert "gho_" not in caplog.text
    assert "[REDACTED:github_token]" in caplog.text


def test_install_log_redaction_is_idempotent():
    install_log_redaction()
    install_log_redaction()
    root_filters = [f for f in logging.getLogger().filters if isinstance(f, SecretRedactingFilter)]
    assert len(root_filters) == 1


# --- token provider never leaks tokens --------------------------------------

def test_token_provider_repr_hides_secret():
    provider = GitHubCopilotTokenProvider(oauth_token="gho_supersecrettokenvalue1234567890")
    assert "gho_" not in repr(provider)
    assert "supersecret" not in repr(provider)
    assert "state=" in repr(provider)


def test_static_provider_repr_hides_secret():
    provider = StaticTokenProvider("gho_supersecrettokenvalue1234567890")
    assert "supersecret" not in repr(provider)
    assert provider.get_token() == "gho_supersecrettokenvalue1234567890"


def test_exchange_error_redacts_upstream_body():
    def handler(request):
        # Simulate an upstream error body that echoes a token.
        return httpx.Response(
            403, text="denied for token gho_16C7e42F292c6912E7710c838347Ae178B4a"
        )

    provider = GitHubCopilotTokenProvider(oauth_token="gho_oauthtoken1234567890abcdef", client=_client(handler))
    with pytest.raises(CopilotAuthError) as exc:
        provider.get_token()
    assert "gho_16C7e42F292c6912E7710c838347Ae178B4a" not in str(exc.value)
    assert "[REDACTED:" in str(exc.value)


def test_device_flow_error_does_not_dump_response():
    def handler(request):
        return httpx.Response(200, json={"error": "expired_token", "secret_field": "gho_leak12345678901234"})

    provider = GitHubCopilotTokenProvider(oauth_token="x", client=_client(handler))
    with pytest.raises(CopilotAuthError) as exc:
        provider.poll_device_flow("code", interval=0, timeout=5)
    assert "gho_leak" not in str(exc.value)
    assert "expired_token" in str(exc.value)


# --- PHP toolchain output redaction -----------------------------------------

def test_php_tool_output_is_redacted(monkeypatch):
    import subprocess

    class _Proc:
        returncode = 1
        stdout = "PHPStan error: DB_PASSWORD=gho_16C7e42F292c6912E7710c838347Ae178B4a in config"
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc())
    result = SubprocessPhpToolchain().phpstan("/ws", ["file.php"], "5")
    assert "gho_" not in result.output
    assert "[REDACTED:" in result.output
