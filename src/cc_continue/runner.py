from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

from cc_continue.models import RunStatus

RATE_LIMIT_PATTERNS = (
    "usage limit",
    "limit reached",
    "resets at",
    "rate limit",
    "quota",
)


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


def classify_output(stdout: str, stderr: str, exit_code: int) -> RunResult:
    combined = f"{stdout}\n{stderr}".lower()

    if exit_code == 0 and stdout.strip():
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return RunResult(status=RunStatus.ERROR, error_text=f"unparseable stdout: {stdout[:500]}")

        if data.get("is_error"):
            if any(p in combined for p in RATE_LIMIT_PATTERNS):
                return RunResult(
                    status=RunStatus.RATE_LIMITED,
                    error_text=data.get("result") or stderr,
                    session_id=data.get("session_id"),
                )
            return RunResult(
                status=RunStatus.ERROR,
                error_text=data.get("result") or stderr,
                session_id=data.get("session_id"),
            )

        usage = data.get("usage", {})
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
        )

    if any(p in combined for p in RATE_LIMIT_PATTERNS):
        return RunResult(status=RunStatus.RATE_LIMITED, error_text=stderr.strip() or stdout.strip())

    return RunResult(
        status=RunStatus.ERROR,
        error_text=stderr.strip() or stdout.strip() or f"exit code {exit_code}",
    )


async def execute(project_path: str, session_id: str, prompt: str, resume: bool) -> RunResult:
    session_flag = ["--resume", session_id] if resume else ["--session-id", session_id]
    proc = await asyncio.create_subprocess_exec(
        "claude",
        *session_flag,
        "-p",
        prompt,
        "--output-format",
        "json",
        "--dangerously-skip-permissions",
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
