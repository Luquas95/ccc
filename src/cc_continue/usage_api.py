from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"
CACHE_PATH = Path.home() / ".local" / "share" / "cc-continue" / "usage_cache.json"
CACHE_TTL_SECONDS = 60
USAGE_ENDPOINT = "https://api.anthropic.com/api/oauth/usage"


@dataclass
class WindowUsage:
    utilization_pct: float
    resets_at: datetime


@dataclass
class ProUsage:
    five_hour: WindowUsage | None
    seven_day: WindowUsage | None


def _read_oauth_token() -> str | None:
    try:
        with open(CREDENTIALS_PATH) as f:
            creds = json.load(f)
        return creds.get("claudeAiOauth", {}).get("accessToken")
    except (OSError, json.JSONDecodeError, KeyError):
        return None


def parse_window(data: dict | None) -> WindowUsage | None:
    if not data:
        return None
    pct = data.get("utilization")
    resets_at = data.get("resets_at")
    if pct is None or not resets_at:
        return None
    try:
        dt = datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    return WindowUsage(utilization_pct=pct, resets_at=dt)


def fetch_live_usage(token: str) -> ProUsage | None:
    """Query the same OAuth usage endpoint Claude Code's own status line
    uses. Token is passed to curl via stdin (--config -), never as a CLI
    arg, so it never appears in `ps` output. Returns None on any failure
    (offline, non-OAuth auth, API error) — never raises."""
    try:
        result = subprocess.run(
            [
                "curl",
                "-s",
                "-f",
                "--config",
                "-",
                "-H",
                "Accept: application/json",
                "-H",
                "Content-Type: application/json",
                "-H",
                "anthropic-beta: oauth-2025-04-20",
                USAGE_ENDPOINT,
            ],
            input=f'header = "Authorization: Bearer {token}"\n',
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None

    return ProUsage(
        five_hour=parse_window(data.get("five_hour")),
        seven_day=parse_window(data.get("seven_day")),
    )


def _window_to_cache(window: WindowUsage | None) -> dict | None:
    if window is None:
        return None
    return {"utilization": window.utilization_pct, "resets_at": window.resets_at.isoformat()}


def _usage_to_cache(usage: ProUsage) -> dict:
    return {"five_hour": _window_to_cache(usage.five_hour), "seven_day": _window_to_cache(usage.seven_day)}


def _cache_to_usage(data: dict) -> ProUsage:
    return ProUsage(five_hour=parse_window(data.get("five_hour")), seven_day=parse_window(data.get("seven_day")))


def get_pro_usage(force_refresh: bool = False) -> ProUsage | None:
    """Current Claude Pro/Max usage-limit status (5-hour and 7-day
    windows). Cached on disk for CACHE_TTL_SECONDS to avoid hammering the
    API every time the analytics screen renders. Returns None when
    unavailable (API-key auth instead of OAuth login, offline, etc.) —
    callers should treat that as "unknown", not an error."""
    if not force_refresh:
        try:
            with open(CACHE_PATH) as f:
                cache = json.load(f)
            if time.time() - cache.get("timestamp", 0) < CACHE_TTL_SECONDS:
                return _cache_to_usage(cache["data"])
        except (OSError, json.JSONDecodeError, KeyError):
            pass

    token = _read_oauth_token()
    if not token:
        return None
    usage = fetch_live_usage(token)
    if usage is None:
        return None

    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_PATH, "w") as f:
            json.dump({"timestamp": time.time(), "data": _usage_to_cache(usage)}, f)
    except OSError:
        pass

    return usage
