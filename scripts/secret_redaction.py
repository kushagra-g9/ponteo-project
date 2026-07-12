"""Redact secrets from CI logs, stderr, and Google Chat / AI report summaries."""

from __future__ import annotations

import os
import re

_REGISTERED: set[str] = set()

# Patterns for values that may appear in AI summaries or HTTP error text
_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"https://chat\.googleapis\.com/v1/spaces/[^\s\"'<>]+", re.I),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-.]+", re.I),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}", re.I),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}", re.I),
    re.compile(r"squ_[a-f0-9]{40}", re.I),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(
        r"(?i)(api[_-]?key|token|password|secret|webhook)[\"']?\s*[:=]\s*[\"']?[^\s\"'<>]{8,}"
    ),
]

ENV_SECRET_NAMES = (
    "GOOGLE_CHAT_WEBHOOK_URL",
    "SONAR_TOKEN",
    "GITHUB_TOKEN",
    "GITOPS_PAT",
    "AWS_SECRET_ACCESS_KEY",
)


def _emit_github_mask(value: str) -> None:
    if os.environ.get("GITHUB_ACTIONS") == "true" and value:
        print(f"::add-mask::{value}")


def register_secret(value: str | None) -> None:
    if not value or len(value) < 4:
        return
    if value not in _REGISTERED:
        _REGISTERED.add(value)
        _emit_github_mask(value)


def register_secrets_from_env(*names: str) -> None:
    for name in names:
        register_secret(os.environ.get(name))


def register_ci_secrets() -> None:
    register_secrets_from_env(*ENV_SECRET_NAMES)


def redact(text: str, *, placeholder: str = "[REDACTED]") -> str:
    if not text:
        return text
    result = text
    for secret in sorted(_REGISTERED, key=len, reverse=True):
        if secret in result:
            result = result.replace(secret, placeholder)
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub(placeholder, result)
    return result
