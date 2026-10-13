from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

from ccc.models import RunStatus

RATE_LIMIT_PATTERNS = (
    "usage limit",
    "session limit",
    "limit reached",
    "resets ",
    "rate limit",
    "quota",
)

# HTTP 429 (Too Many Requests) is Claude Code's own signal for a rate/usage
# limit — far more reliable than matching the human-readable message text,
# which has changed wording before ("usage limit reached" vs "session
# limit ... resets 8:30pm" observed in production on 2026-09-03).
RATE_LIMIT_API_ERROR_STATUS = 429


@dataclass
class RunResult:
    status: RunStatus
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    duration_ms: int = 0
    num_turns: int = 0
    result_text: str | None = None
    error_text: str | None = None
    session_id: str | None = None
    # {canonical_model_name: {input_tokens, output_tokens, cache_read_tokens,
    # cache_creation_tokens}}, from Claude Code's "modelUsage" field — lets a
    # run be attributed to the specific model(s) it actually used.
    model_usage: dict[str, dict[str, int]] = field(default_factory=dict)


def _is_rate_limited(data: dict | None, combined_lower: str) -> bool:
    if data is not None and data.get("api_error_status") == RATE_LIMIT_API_ERROR_STATUS:
        return True
    return any(p in combined_lower for p in RATE_LIMIT_PATTERNS)


def classify_output(stdout: str, stderr: str, exit_code: int) -> RunResult:
    combined = f"{stdout}\n{stderr}".lower()

    # Claude Code prints a JSON result envelope on stdout even when it's
    # reporting an error (rate limit, API error, ...) with a non-zero exit
    # code — parse it whenever stdout looks like JSON, regardless of
    # exit_code, so fields like api_error_status/result/session_id are
    # available for classification instead of falling back to raw text.
    data: dict | None = None
    if stdout.strip():
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            data = None

    if data is not None:
        if data.get("is_error"):
            status = RunStatus.RATE_LIMITED if _is_rate_limited(data, combined) else RunStatus.ERROR
            return RunResult(
                status=status,
                error_text=data.get("result") or stderr,
                session_id=data.get("session_id"),
            )

        usage = data.get("usage", {})
        model_usage = {
            model_name: {
                "input_tokens": mu.get("inputTokens", 0),
                "output_tokens": mu.get("outputTokens", 0),
                "cache_read_tokens": mu.get("cacheReadInputTokens", 0),
                "cache_creation_tokens": mu.get("cacheCreationInputTokens", 0),
            }
            for model_name, mu in (data.get("modelUsage") or {}).items()
            if isinstance(mu, dict)
        }
        return RunResult(
            status=RunStatus.SUCCESS,
            cost_usd=data.get("total_cost_usd", 0.0),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cache_read_tokens=usage.get("cache_read_input_tokens", 0),
            cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
            duration_ms=data.get("duration_ms", 0),
            num_turns=data.get("num_turns", 0),
            result_text=data.get("result"),
            session_id=data.get("session_id"),
            model_usage=model_usage,
        )

    if _is_rate_limited(None, combined):
        return RunResult(status=RunStatus.RATE_LIMITED, error_text=stderr.strip() or stdout.strip())

    if exit_code == 0 and stdout.strip():
        return RunResult(status=RunStatus.ERROR, error_text=f"unparseable stdout: {stdout[:500]}")

    return RunResult(
        status=RunStatus.ERROR,
        error_text=stderr.strip() or stdout.strip() or f"exit code {exit_code}",
    )


# Flags used for queues created before launch attributes existed (NULL
# launch_flags) — exactly what every run used before.
LEGACY_FLAGS = ["--dangerously-skip-permissions"]

# First-run flags that themselves say which session to talk to; the
# queue's own (placeholder) session id must not be passed alongside them.
_SESSION_SELECTING_FLAGS = ("--resume", "--from-pr")


def build_command(
    session_id: str,
    prompt: str,
    resume: bool,
    launch_flags: list[str] | None = None,
    first_run_flags: list[str] | None = None,
) -> list[str]:
    first = list(first_run_flags or [])
    if any(flag in first for flag in _SESSION_SELECTING_FLAGS):
        session_flag: list[str] = []
    else:
        session_flag = ["--resume", session_id] if resume else ["--session-id", session_id]
    flags = LEGACY_FLAGS if launch_flags is None else list(launch_flags)
    return ["claude", *session_flag, *first, "-p", prompt, "--output-format", "json", *flags]


async def execute(
    project_path: str,
    session_id: str,
    prompt: str,
    resume: bool,
    launch_flags: list[str] | None = None,
    first_run_flags: list[str] | None = None,
) -> RunResult:
    proc = await asyncio.create_subprocess_exec(
        *build_command(session_id, prompt, resume, launch_flags, first_run_flags),
        cwd=project_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = await proc.communicate()
    result = classify_output(
        stdout_bytes.decode("utf-8", errors="replace"),
        stderr_bytes.decode("utf-8", errors="replace"),
        proc.returncode or 0,
    )
    if result.session_id is None:
        result.session_id = session_id
    return result
