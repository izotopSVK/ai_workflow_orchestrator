"""Shared GitHub Copilot (enterprise) auth + chat plumbing.

Lives in the lower ``workflows.llm`` layer so both the MVP workflow graph and the
dev orchestrator route their LLM calls through GitHub Copilot's
OpenAI-compatible API without depending on each other.

SSO model: the user authenticates once via GitHub's **OAuth device flow**. When
the Copilot subscription is owned by an org/enterprise enforcing SAML SSO, the
device-flow authorization enforces that SSO, so the resulting OAuth token is
SSO-authorized. That token is exchanged for a short-lived Copilot token (~30 min)
which :class:`GitHubCopilotTokenProvider` caches and refreshes.

For headless/CI, provide a pre-authorized OAuth token via
``GH_COPILOT_OAUTH_TOKEN`` (or inject a :class:`StaticTokenProvider`).
"""

from __future__ import annotations

import os
import time
from typing import Protocol

import httpx

GITHUB_DEVICE_CODE_URL = "https://github.com/login/device/code"
GITHUB_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
COPILOT_TOKEN_URL = "https://api.github.com/copilot_internal/v2/token"

# Well-known Copilot OAuth client id used by editor integrations. Override with
# the enterprise's own OAuth app client id for tighter SSO control.
DEFAULT_COPILOT_CLIENT_ID = "Iv1.b507a08c87ecfe98"


class CopilotAuthError(RuntimeError):
    """Raised when Copilot authentication or token exchange fails."""


class TokenProvider(Protocol):
    """Supplies a currently-valid bearer token for the Copilot API."""

    def get_token(self) -> str: ...


class StaticTokenProvider:
    """Returns a fixed Copilot token. For tests and pre-provisioned tokens."""

    def __init__(self, token: str):
        self._token = token

    def get_token(self) -> str:
        return self._token


class GitHubCopilotTokenProvider:
    """Obtains and refreshes short-lived Copilot tokens from a GitHub OAuth token.

    ``client`` is injectable so the exchange logic is unit-testable with an
    ``httpx.MockTransport`` and never touches the network in tests.
    """

    # Refresh this many seconds before the token actually expires.
    _REFRESH_SKEW = 120

    def __init__(
        self,
        *,
        oauth_token: str | None = None,
        client_id: str = DEFAULT_COPILOT_CLIENT_ID,
        client: httpx.Client | None = None,
        editor_version: str = "vscode/1.95.0",
        integration_id: str = "vscode-chat",
    ):
        self._oauth_token = oauth_token or os.environ.get("GH_COPILOT_OAUTH_TOKEN")
        self._client_id = client_id
        self._client = client or httpx.Client(timeout=30.0)
        self._editor_version = editor_version
        self._integration_id = integration_id
        self._copilot_token: str | None = None
        self._expires_at: float = 0.0

    # -- OAuth device flow (interactive, SSO-aware) ------------------------

    def start_device_flow(self) -> dict:
        """Begin device flow; returns user_code + verification_uri to show."""
        resp = self._client.post(
            GITHUB_DEVICE_CODE_URL,
            headers={"Accept": "application/json"},
            data={"client_id": self._client_id, "scope": "read:user"},
        )
        resp.raise_for_status()
        return resp.json()

    def poll_device_flow(self, device_code: str, interval: int = 5, timeout: int = 900) -> str:
        """Poll until the user authorizes; returns the GitHub OAuth token."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = self._client.post(
                GITHUB_ACCESS_TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": self._client_id,
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
            )
            data = resp.json()
            if "access_token" in data:
                self._oauth_token = data["access_token"]
                return self._oauth_token
            error = data.get("error")
            if error in ("authorization_pending", "slow_down"):
                time.sleep(interval + (5 if error == "slow_down" else 0))
                continue
            raise CopilotAuthError(f"Device flow failed: {error or data}")
        raise CopilotAuthError("Device flow timed out awaiting authorization")

    def login_device_flow(self, prompt=print) -> str:  # pragma: no cover - interactive
        """Run the full device flow, prompting the user via ``prompt``."""
        flow = self.start_device_flow()
        prompt(f"Open {flow['verification_uri']} and enter code: {flow['user_code']}")
        return self.poll_device_flow(flow["device_code"], interval=int(flow.get("interval", 5)))

    # -- Copilot token exchange -------------------------------------------

    def _exchange(self) -> None:
        if not self._oauth_token:
            raise CopilotAuthError(
                "No GitHub OAuth token. Set GH_COPILOT_OAUTH_TOKEN or run "
                "login_device_flow() once (this enforces org SAML SSO)."
            )
        resp = self._client.get(
            COPILOT_TOKEN_URL,
            headers={
                "Authorization": f"token {self._oauth_token}",
                "Accept": "application/json",
                "Editor-Version": self._editor_version,
                "Copilot-Integration-Id": self._integration_id,
            },
        )
        if resp.status_code != 200:
            raise CopilotAuthError(
                f"Copilot token exchange failed ({resp.status_code}): {resp.text}"
            )
        data = resp.json()
        self._copilot_token = data["token"]
        self._expires_at = float(data.get("expires_at", time.time() + 1800))

    def get_token(self) -> str:
        if self._copilot_token is None or time.time() >= self._expires_at - self._REFRESH_SKEW:
            self._exchange()
        assert self._copilot_token is not None
        return self._copilot_token


class CopilotChatFactory:
    """Builds a ``ChatOpenAI`` bound to Copilot, rotating with the token.

    ``langchain-openai`` is imported lazily so the Fake LLM paths used in tests
    never require it.
    """

    def __init__(
        self,
        *,
        token_provider: TokenProvider,
        model: str = "gpt-4o",
        base_url: str = "https://api.githubcopilot.com",
        editor_version: str = "vscode/1.95.0",
        integration_id: str = "vscode-chat",
        temperature: float = 0.0,
    ):
        self._tokens = token_provider
        self._model = model
        self._base_url = base_url
        self._temperature = temperature
        self._headers = {
            "Editor-Version": editor_version,
            "Copilot-Integration-Id": integration_id,
        }
        self._cached_token: str | None = None
        self._chat = None

    def chat(self):
        token = self._tokens.get_token()
        if self._chat is None or token != self._cached_token:
            from langchain_openai import ChatOpenAI

            self._chat = ChatOpenAI(
                model=self._model,
                base_url=self._base_url,
                api_key=token,
                temperature=self._temperature,
                default_headers=self._headers,
            )
            self._cached_token = token
        return self._chat
