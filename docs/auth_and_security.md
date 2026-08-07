# Authentication & security

## GitHub Copilot auth (SSO-compatible)

All LLM calls route through GitHub Copilot's OpenAI-compatible API
(`https://api.githubcopilot.com`). Authentication:

1. **OAuth device flow.** The user authorizes once. When the Copilot subscription
   belongs to an org/enterprise that enforces SAML SSO, the device-flow
   authorization enforces that SSO, so the resulting OAuth token is SSO-authorized.
2. **Token exchange.** `GitHubCopilotTokenProvider` exchanges the OAuth token for
   a short-lived Copilot token (~30 min) and refreshes it before expiry.

```python
from workflows.llm.copilot import GitHubCopilotTokenProvider
token = GitHubCopilotTokenProvider().login_device_flow()   # prints URL + code
```

Store the returned token as `GH_COPILOT_OAUTH_TOKEN` (secret manager / `.env`);
do not print it to a logged shell. For CI/headless, provide a pre-authorized
token via that env var and no device flow runs.

**Enterprise OAuth app:** override the default editor client id with your org's
own OAuth app for tighter SSO control:

```python
DevOrchestratorConfig(copilot_oauth_client_id="Iv1.your_org_app")
```

Tokens are wrapped in `pydantic.SecretStr` and the providers have redacting
`__repr__`, so they never surface in reprs or traceback locals.

## Secret & PII redaction

`workflows/observability/redaction.py` centrally scrubs GitHub tokens, OpenAI
keys, JWTs, the Copilot token blob, `Authorization` headers, and emails from
logs, error messages and captured tool output. `install_log_redaction()` (called
at app startup) attaches the filter to the root/httpx/openai/uvicorn loggers so
even an accidental DEBUG level cannot leak Authorization headers.

Full threat model, findings and residual risks (state-at-rest, artifacts):
[logging_security.md](logging_security.md).

## Operational notes

- Do not enable `OPENAI_LOG=debug` or httpx DEBUG in production (redaction
  mitigates it, but avoid it).
- Treat the checkpoint DB, `Workflow.state_json`, and `ARTIFACT_DIR` as sensitive
  at rest — diffs/goals can contain target-repo secrets/PII. Encrypt at rest and
  restrict access.
