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

_PLACEHOLDER = "[REDACTED:{}]"

# Ordered (label, pattern). Applied in sequence; earlier, more specific rules
# win. Case-insensitive where relevant.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # GitHub tokens (classic, fine-grained, and OAuth/app: gho_/ghu_/ghs_/ghp_/ghr_)
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b")),
    ("github_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    # OpenAI-style keys
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b")),
    # JWTs (three base64url segments)
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+")),
    # GitHub Copilot session token blob (tid=...;exp=...;...)
    ("copilot_token", re.compile(r"\btid=[^\s\"';]+(?:;[a-z0-9]+=[^\s\"';]+)+")),
    # Authorization / token / bearer headers: keep the key, redact the value
    (
        "auth_header",
        re.compile(r"(?i)\b(authorization|x-api-key)\b(\s*[:=]\s*)\S+"),
    ),
    ("bearer", re.compile(r"(?i)\b(bearer|token)\s+[A-Za-z0-9._\-]{8,}")),
    # Emails (PII)
    ("email", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
]


def redact(text: str) -> str:
    """Return ``text`` with secrets and PII replaced by typed placeholders."""
    if not text:
        return text
    result = text
    for label, pattern in _PATTERNS:
        if label in ("auth_header",):
            result = pattern.sub(rf"\1\2{_PLACEHOLDER.format(label)}", result)
        elif label == "bearer":
            result = pattern.sub(
                lambda m: f"{m.group(1)} {_PLACEHOLDER.format('bearer')}", result
            )
        else:
            result = pattern.sub(_PLACEHOLDER.format(label), result)
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
