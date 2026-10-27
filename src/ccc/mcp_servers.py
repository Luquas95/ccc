"""Which MCP servers a conversation may use. Claude Code loads every server
it finds (user, project, local, claude.ai connectors) and puts all their
tool definitions into the context of every turn; with `--strict-mcp-config`
it loads only the servers handed over with `--mcp-config`.

A conversation stores just the *names* it allows, as one marker flag
(MARKER) in its launch flags. The server definitions — which can hold
tokens in `env` / `headers` — are looked up when `claude` is started
(resolve_flags) and never stored, shown or logged by ccc."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Launch-flag marker: "--ccc-mcp=a,b" allows servers a and b, "--ccc-mcp="
# none (ccc's own server is always attached by the orchestrator).
MARKER = "--ccc-mcp="
OWN_SERVER = "ccc"


def claude_json_path() -> Path:
    base = os.environ.get("CLAUDE_CONFIG_DIR")
    return (Path(base) if base else Path.home()) / ".claude.json"


def _read_servers(path: Path, project_path: str | None = None) -> dict[str, dict]:
    """The `mcpServers` of a JSON file — top level, or of one project's
    entry (`projects[project_path]`) in ~/.claude.json."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if project_path is not None:
        data = (data.get("projects") or {}).get(project_path) if isinstance(data, dict) else None
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    if not isinstance(servers, dict):
        return {}
    return {name: cfg for name, cfg in servers.items() if isinstance(cfg, dict) and valid_name(name)}


def valid_name(name: str) -> bool:
    return bool(name) and name != OWN_SERVER and "," not in name and "=" not in name


def discover(project_path: str) -> dict[str, dict]:
    """Servers Claude Code would load in `project_path`, by name: user
    config, then the project's .mcp.json, then local (per project) config —
    the later one wins, as in Claude Code."""
    project = str(Path(project_path).expanduser())
    servers = _read_servers(claude_json_path())
    servers |= _read_servers(Path(project) / ".mcp.json")
    servers |= _read_servers(claude_json_path(), project)
    return servers


def names(project_path: str) -> list[str]:
    return sorted(discover(project_path))


def marker(selected) -> str:
    return MARKER + ",".join(sorted(selected))


def selected_names(flags: list[str] | None) -> list[str] | None:
    """Names allowed by the marker in `flags`; None when there is none
    (all servers, as before)."""
    for flag in flags or []:
        if flag.startswith(MARKER):
            return [n for n in flag[len(MARKER):].split(",") if n]
    return None


def resolve_flags(flags: list[str] | None, project_path: str) -> list[str] | None:
    """`flags` with the marker replaced by what `claude` understands:
    --strict-mcp-config plus --mcp-config for the allowed servers that still
    exist. Without a marker `flags` come back unchanged."""
    if flags is None or not any(f.startswith(MARKER) for f in flags):
        return flags
    wanted = selected_names(flags) or []
    found = discover(project_path)
    for name in wanted:
        if name not in found:
            logger.warning("MCP server '%s' is no longer configured; skipped", name)
    config = {"mcpServers": {name: found[name] for name in wanted if name in found}}
    resolved: list[str] = []
    for flag in flags:
        if flag.startswith(MARKER):
            resolved.append("--strict-mcp-config")
            if config["mcpServers"]:
                resolved += ["--mcp-config", json.dumps(config)]
        else:
            resolved.append(flag)
    return resolved
