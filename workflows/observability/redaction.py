"""Central redaction of secrets and PII for logs, errors and captured output.

Single source of truth for "what must never appear in a log line". Used by:

* the Copilot token provider (sanitized exception messages),
* the PHP toolchain (captured stdout/stderr may echo repo secrets),
* :class:`SecretRedactingFilter`, attached to the logging stack so *anything*
  that reaches a handler is scrubbed as a last line of defense.

Redaction is deliberately conservative: it replaces matches with typed
placeholders rather than dropping them, so logs stay useful for debugging.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass


def _placeholder(label: str) -> str:
    return f"[REDACTED:{label}]"


@dataclass(frozen=True)
class _Rule:
    """One redaction rule: match ``pattern`` and rewrite it via ``replacement``.

    ``replacement`` is anything ``re.sub`` accepts (a template string or a
    function), so each rule owns how it rewrites — no per-label branching in the
    redact loop. Add a credential type by appending a rule here.
    """

    label: str
    pattern: re.Pattern[str]
    replacement: object  # str template or Callable[[re.Match], str]


def _keep_key(label: str):
    # Keep the captured prefix (key + separator) for debuggability; the value is
    # the uncaptured remainder, so it is dropped and replaced by the placeholder.
    def repl(m: re.Match) -> str:
        prefix = "".join(g for g in m.groups() if g)
        return f"{prefix}{_placeholder(label)}"
    return repl


# Ordered; earlier, more specific rules win. Case-insensitive where relevant.
_RULES: list[_Rule] = [
    # GitHub tokens (classic, fine-grained, and OAuth/app: gho_/ghu_/ghs_/ghp_/ghr_)
    _Rule("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b"), _placeholder("github_token")),
    _Rule("github_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), _placeholder("github_pat")),
    # OpenAI-style keys
    _Rule("openai_key", re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b"), _placeholder("openai_key")),
    # JWTs (three base64url segments)
    _Rule("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"), _placeholder("jwt")),
    # GitHub Copilot session token blob (tid=...;exp=...;...)
    _Rule("copilot_token", re.compile(r"\btid=[^\s\"';]+(?:;[a-z0-9]+=[^\s\"';]+)+"), _placeholder("copilot_token")),
    # Authorization / X-API-Key headers: keep the key, redact the value
    _Rule("auth_header", re.compile(r"(?i)\b(authorization|x-api-key)\b(\s*[:=]\s*)\S+"), _keep_key("auth_header")),
    # bearer/token <value>: keep the prefix, redact the value
    _Rule("bearer", re.compile(r"(?i)\b(bearer|token)(\s+)[A-Za-z0-9._\-]{8,}"), _keep_key("bearer")),
    # Emails (PII)
    _Rule("email", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), _placeholder("email")),
]


def redact(text: str) -> str:
    """Return ``text`` with secrets and PII replaced by typed placeholders."""
    if not text:
        return text
    result = text
    for rule in _RULES:
        result = rule.pattern.sub(rule.replacement, result)
    return result


def redact_snippet(text: str, *, limit: int = 500) -> str:
    """Redact and truncate untrusted upstream text before it enters an error."""
    if text is None:
        return ""
    snippet = text if len(text) <= limit else text[:limit] + "…[truncated]"
    return redact(snippet)


class SecretRedactingFilter(logging.Filter):
    """Logging filter that scrubs secrets/PII from every record it sees.

    Rewrites the fully-rendered message (``record.getMessage()``) and clears
    ``args`` so downstream formatters cannot re-expose the raw values.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - never let logging redaction crash the app
            return True
        redacted = redact(message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def install_log_redaction(logger_names: tuple[str, ...] = ()) -> None:
    """Attach :class:`SecretRedactingFilter` to the root and key noisy loggers.

    Call once at startup. Covers loggers known to log request headers/bodies
    (httpx, openai, uvicorn) so an accidentally-enabled DEBUG level cannot leak
    Authorization headers.
    """
    targets = ("", "httpx", "httpcore", "openai", "uvicorn", "uvicorn.access") + logger_names
    log_filter = SecretRedactingFilter()
    for name in targets:
        logger = logging.getLogger(name)
        if not any(isinstance(f, SecretRedactingFilter) for f in logger.filters):
            logger.addFilter(log_filter)
        for handler in logger.handlers:
            if not any(isinstance(f, SecretRedactingFilter) for f in handler.filters):
                handler.addFilter(log_filter)
