"""Fixed catalogue of attributes a new conversation can be started with,
and the pure logic turning a set of ticked keys into `claude` flags."""
from __future__ import annotations

from dataclasses import dataclass

SESSION_NEW = "session_new"
SESSION_CONTINUE = "session_continue"
SESSION_RESUME = "session_resume"
SESSION_FROM_PR = "session_from_pr"
FORK = "fork"


@dataclass(frozen=True)
class LaunchOption:
    key: str
    label: str
    flags: tuple[str, ...]
    short: str  # compact label for headers / queue detail


@dataclass(frozen=True)
class OptionGroup:
    key: str
    title: str
    options: tuple[LaunchOption, ...]
    exclusive: bool  # ticking one unticks the rest of the group
    required: bool  # exactly one must stay ticked


GROUPS: tuple[OptionGroup, ...] = (
    OptionGroup("session", "Session", (
        LaunchOption(SESSION_NEW, "New session", (), "new"),
        LaunchOption(SESSION_CONTINUE, "Continue last in directory", (), "continue"),
        LaunchOption(SESSION_RESUME, "Resume selected…", (), "resume"),
        LaunchOption(SESSION_FROM_PR, "From pull request…", (), "from PR"),
    ), exclusive=True, required=True),
    OptionGroup("session_extra", "", (
        LaunchOption(FORK, "As a copy (fork)", ("--fork-session",), "fork"),
    ), exclusive=False, required=False),
    OptionGroup("permissions", "Permissions", (
        LaunchOption("perm_skip", "Skip all permission checks", ("--dangerously-skip-permissions",), "skip permissions"),
        LaunchOption("perm_accept_edits", "Auto-accept edits", ("--permission-mode", "acceptEdits"), "accept edits"),
        LaunchOption("perm_plan", "Plan only", ("--permission-mode", "plan"), "plan only"),
    ), exclusive=True, required=True),
    OptionGroup("model", "Model", (
        LaunchOption("model_opus", "Opus", ("--model", "opus"), "Opus"),
        LaunchOption("model_sonnet", "Sonnet", ("--model", "sonnet"), "Sonnet"),
        LaunchOption("model_haiku", "Haiku", ("--model", "haiku"), "Haiku"),
        LaunchOption("model_fable", "Fable", ("--model", "fable"), "Fable"),
    ), exclusive=True, required=False),
    OptionGroup("effort", "Effort", (
        LaunchOption("effort_high", "high", ("--effort", "high"), "effort high"),
        LaunchOption("effort_xhigh", "xhigh", ("--effort", "xhigh"), "effort xhigh"),
        LaunchOption("effort_max", "max", ("--effort", "max"), "effort max"),
    ), exclusive=True, required=False),
    OptionGroup("other", "Other", (
        LaunchOption("other_fallback_sonnet", "Fallback to Sonnet when overloaded", ("--fallback-model", "sonnet"), "fallback Sonnet"),
        LaunchOption("other_chrome", "Claude in Chrome", ("--chrome",), "Chrome"),
        LaunchOption("other_safe_mode", "Safe mode (no customizations)", ("--safe-mode",), "safe mode"),
    ), exclusive=False, required=False),
)

# Groups whose choice decides WHICH session to talk to rather than adding
# flags to every run — handled by orchestrator.start_conversation().
SESSION_GROUP_KEYS = ("session", "session_extra")

DEFAULT_SELECTION: frozenset[str] = frozenset({SESSION_NEW, "perm_skip"})


def group_of(key: str) -> OptionGroup:
    for group in GROUPS:
        if any(o.key == key for o in group.options):
            return group
    raise KeyError(key)


def toggle(selection: frozenset[str], key: str, checked: bool) -> frozenset[str]:
    group = group_of(key)
    sel = set(selection)
    if checked:
        if group.exclusive:
            sel -= {o.key for o in group.options}
        sel.add(key)
    elif not group.required:
        sel.discard(key)
    if SESSION_NEW in sel:
        sel.discard(FORK)  # nothing to copy from
    return frozenset(sel)


def session_mode(selection: frozenset[str]) -> str:
    for option in GROUPS[0].options:
        if option.key in selection:
            return option.key
    return SESSION_NEW


def persistent_flags(selection: frozenset[str]) -> list[str]:
    flags: list[str] = []
    for group in GROUPS:
        if group.key in SESSION_GROUP_KEYS:
            continue
        for option in group.options:
            if option.key in selection:
                flags.extend(option.flags)
    return flags


def describe_flags(flags: list[str] | None) -> str:
    """Compact human summary of a queue's persistent flags."""
    if flags is None:
        return "legacy (skip permissions)"
    remaining = list(flags)
    parts: list[str] = []
    for group in GROUPS:
        if group.key in SESSION_GROUP_KEYS:
            continue
        for option in group.options:
            n = len(option.flags)
            for i in range(len(remaining) - n + 1):
                if tuple(remaining[i:i + n]) == option.flags:
                    parts.append(option.short)
                    del remaining[i:i + n]
                    break
    parts.extend(remaining)
    return " · ".join(parts) if parts else "default"
