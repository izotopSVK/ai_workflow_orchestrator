# Logging & data-leak security review

Scope: ensure tokens (GitHub OAuth / Copilot) and PII never leak into logs,
error messages, persisted state, or artifacts. Central control:
`workflows/observability/redaction.py`.

## Threat model

| Asset | Where it lives | Leak channel if unprotected |
|-------|----------------|-----------------------------|
| GitHub OAuth token | `GitHubCopilotTokenProvider` | repr / traceback locals, exception text, logs |
| Copilot session token | token provider, `Authorization` header | httpx/openai DEBUG logs, exception text |
| Target-repo secrets (DB creds, `.env`) | PHP tool stdout, diffs | `verify_report` → persisted state, logs |
| PII (emails, goal text) | `goal`, events, artifacts | logs, persisted state |

## Findings and fixes

### 1. Secrets in exception messages — FIXED
`_exchange` embedded the raw upstream body (`resp.text`) and `poll_device_flow`
dumped the entire response dict into `CopilotAuthError`. Both could carry token
material into any handler that logs the exception.
- Token-exchange errors now pass the body through `redact_snippet()` (scrub +
  truncate).
- Device-flow errors surface only the `error` *code*, never the response dict.

### 2. Tokens as plain `str` — FIXED
`_oauth_token` / `_copilot_token` are now `pydantic.SecretStr`, so they render as
`**********` in reprs and traceback locals. `StaticTokenProvider` too. Both
providers have explicit `__repr__` that never expose token material. The raw
value is unwrapped only at the point of use (`Authorization` header, API key).

### 3. PHP tool output echoing repo secrets — FIXED
`SubprocessPhpToolchain._run` captured full stdout+stderr verbatim, and it flows
into the persisted `verify_report`. PHPStan/PHPUnit output can print config
values (DB passwords, `.env`). Output is now `redact()`-ed and capped (8 KB)
at capture time.

### 4. Debug logging exposing Authorization headers — MITIGATED
`OPENAI_LOG=debug` or `logging.getLogger("httpx").setLevel(DEBUG)` would log
request headers/bodies. `install_log_redaction()` (called at app startup)
attaches `SecretRedactingFilter` to the root plus `httpx`, `httpcore`, `openai`,
`uvicorn*` loggers, so even DEBUG lines are scrubbed as a last line of defense.
Still: do not enable those debug levels in production.

### 5. README leaked the OAuth token to stdout — FIXED
The quickstart previously `print()`-ed the token from the device flow. It now
appends it straight into `.env` without echoing to the terminal/history.

## `redact()` coverage

GitHub tokens (`gho_/ghu_/ghs_/ghp_/ghr_`, `github_pat_`), OpenAI keys (`sk-…`),
JWTs, the Copilot `tid=…;…` blob, `Authorization`/`X-API-Key` header values,
`Bearer`/`token <value>`, and emails (PII). Matches become typed placeholders
(`[REDACTED:github_token]`) so logs stay debuggable. Tested in
`tests/test_redaction.py` (15 cases).

## Residual risks (accepted / operational)

- **State & checkpoint store are sensitive at rest.** `diff` is persisted
  unredacted because the orchestrator needs it to commit; it can contain
  target-repo secrets. Treat the checkpoint DB and `Workflow.state_json` as a
  secret store: encrypt at rest, restrict access, set retention. Redacting diffs
  would break commits, so it is intentionally not done.
- **Artifacts on disk** (`ARTIFACT_DIR`) contain `goal`/`plan` (possible PII).
  Apply filesystem permissions / lifecycle policy.
- `redact()` is pattern-based; a novel secret format not in the pattern set can
  slip through. Add patterns as new credential types are introduced.

## For contributors

- Never `print()` or log a token, `resp.text`, or a full response object.
- Route any untrusted upstream text through `redact()` / `redact_snippet()`
  before it enters an exception, log, or persisted field.
- Keep secrets in `SecretStr`; unwrap only at the call site.
