"""Masks secrets (API keys, tokens, passwords, private keys) in text that
leaves ccc: notifications sent to Telegram / Discord and exported
conversations. A conversation can quote a `.env`, a `curl -H
"Authorization: …"` or a key Claude just generated; none of that should end
up in a chat app or a file you share.

Each match is replaced by `[redacted]`, keeping a recognisable prefix
(`sk-ant-…`, `ghp_…`, `password=`) so the text still makes sense. It's a
safety net, not a guarantee: a secret with no known shape and no telling
name next to it gets through."""
from __future__ import annotations

import re
from typing import Iterable

MASK = "[redacted]"

# Secrets recognisable by their own shape. Group 1, when present, is kept.
_SHAPED = [
    # PEM private keys, whole block.
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|\Z)", re.S),
    re.compile(r"\b(sk-ant-)[A-Za-z0-9_-]{16,}"),                       # Anthropic
    re.compile(r"\b(sk-(?:proj-|svcacct-)?)[A-Za-z0-9_-]{20,}"),         # OpenAI and alike
    re.compile(r"\b(gh[pousr]_)[A-Za-z0-9]{20,}"),                      # GitHub
    re.compile(r"\b(github_pat_)[A-Za-z0-9_]{20,}"),
    re.compile(r"\b(glpat-)[A-Za-z0-9_-]{20,}"),                         # GitLab
    re.compile(r"\b(xox[abprse]-)[A-Za-z0-9-]{10,}"),                    # Slack
    re.compile(r"\b((?:AKIA|ASIA))[A-Z0-9]{16}\b"),                      # AWS access key id
    re.compile(r"\b(AIza)[A-Za-z0-9_-]{35}"),                            # Google API key
    re.compile(r"\b((?:sk|rk)_(?:live|test)_)[A-Za-z0-9]{16,}"),         # Stripe
    re.compile(r"\b(npm_)[A-Za-z0-9]{30,}"),
    re.compile(r"\b(hf_)[A-Za-z0-9]{30,}"),                              # Hugging Face
    re.compile(r"\b(\d{6,12}:)[A-Za-z0-9_-]{35}\b"),                     # Telegram bot token
    re.compile(r"(https://(?:\w+\.)?discord(?:app)?\.com/api/webhooks/\d+/)[A-Za-z0-9_-]+"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),  # JWT
    re.compile(r"(://[^/\s:@]+:)[^@\s/]+(?=@)"),                         # password in a URL
    re.compile(r"(\b(?:Bearer|Basic)\s+)[A-Za-z0-9._~+/=-]{12,}", re.I),
]

# `NAME=value`, `name: value`, `"name": "value"` where the name says it's a secret.
_NAMED = re.compile(
    r"""(?P<keep>(?P<name>\b[A-Za-z0-9_.-]*(?:pass(?:word|wd)|secret|token|api[_-]?key|apikey|
         access[_-]?key|private[_-]?key|client[_-]?secret|authorization|credentials?)[A-Za-z0-9_.-]*)
         ["']?\s*[:=]\s*["']?)
        (?P<value>[^\s"'`,;]{6,})""",
    re.I | re.X,
)

# Values that look like an assignment but aren't a secret worth hiding.
_HARMLESS = re.compile(r"^(?:\$\{?\w+\}?|<[^>]*>|\*+|x+|true|false|null|none|required|optional|bearer|basic|\[redacted\])$", re.I)


def _keep_prefix(match: re.Match) -> str:
    return (match.group(1) if match.re.groups else "") + MASK


def _named(match: re.Match) -> str:
    value = match.group("value")
    if _HARMLESS.match(value) or MASK in value:
        return match.group(0)
    return match.group("keep") + MASK


def redact(text: str, known: Iterable[str | None] = ()) -> str:
    """`text` with secrets masked. `known` are exact values that must never
    appear (ccc's own Telegram token, Discord webhook, …)."""
    if not text:
        return text
    for secret in known:
        if secret and len(secret) >= 6:
            text = text.replace(secret, MASK)
    for pattern in _SHAPED:
        text = pattern.sub(_keep_prefix, text)
    return _NAMED.sub(_named, text)
