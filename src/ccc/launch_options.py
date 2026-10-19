"""Fixed catalogue of attributes a new conversation can be started with,
and the pure logic turning a set of ticked keys into `claude` flags."""
from __future__ import annotations

from dataclasses import dataclass

from ccc.i18n import N_, _

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
    # label and short are English, marked with N_(): shown through _().


@dataclass(frozen=True)
class OptionGroup:
    key: str
    title: str
    options: tuple[LaunchOption, ...]
    exclusive: bool  # ticking one unticks the rest of the group
    required: bool  # exactly one must stay ticked


GROUPS: tuple[OptionGroup, ...] = (
    OptionGroup("session", N_("Session"), (
        LaunchOption(SESSION_NEW, N_("New session"), (), N_("new")),
        LaunchOption(SESSION_CONTINUE, N_("Continue last in directory"), (), N_("continue")),
        LaunchOption(SESSION_RESUME, N_("Resume selected…"), (), N_("resume")),
        LaunchOption(SESSION_FROM_PR, N_("From pull request…"), (), N_("from PR")),
    ), exclusive=True, required=True),
    OptionGroup("session_extra", "", (
        LaunchOption(FORK, N_("As a copy (fork)"), ("--fork-session",), N_("fork")),
    ), exclusive=False, required=False),
    OptionGroup("permissions", N_("Permissions"), (
        LaunchOption("perm_skip", N_("Skip all permission checks"), ("--dangerously-skip-permissions",), N_("skip permissions")),
        LaunchOption("perm_accept_edits", N_("Auto-accept edits"), ("--permission-mode", "acceptEdits"), N_("accept edits")),
        LaunchOption("perm_plan", N_("Plan only"), ("--permission-mode", "plan"), N_("plan only")),
    ), exclusive=True, required=True),
    OptionGroup("model", N_("Model"), (
        LaunchOption("model_opus", N_("Opus"), ("--model", "opus"), N_("Opus")),
        LaunchOption("model_sonnet", N_("Sonnet"), ("--model", "sonnet"), N_("Sonnet")),
        LaunchOption("model_haiku", N_("Haiku"), ("--model", "haiku"), N_("Haiku")),
        LaunchOption("model_fable", N_("Fable"), ("--model", "fable"), N_("Fable")),
    ), exclusive=True, required=False),
    OptionGroup("effort", N_("Effort"), (
        LaunchOption("effort_high", N_("high"), ("--effort", "high"), N_("effort high")),
        LaunchOption("effort_xhigh", N_("xhigh"), ("--effort", "xhigh"), N_("effort xhigh")),
        LaunchOption("effort_max", N_("max"), ("--effort", "max"), N_("effort max")),
    ), exclusive=True, required=False),
    OptionGroup("other", N_("Other"), (
        LaunchOption("other_fallback_sonnet", N_("Fallback to Sonnet when overloaded"), ("--fallback-model", "sonnet"), N_("fallback Sonnet")),
        LaunchOption("other_chrome", N_("Claude in Chrome"), ("--chrome",), N_("Chrome")),
        LaunchOption("other_safe_mode", N_("Safe mode (no customizations)"), ("--safe-mode",), N_("safe mode")),
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
        return _("legacy (skip permissions)")
    remaining = list(flags)
    parts: list[str] = []
    for group in GROUPS:
        if group.key in SESSION_GROUP_KEYS:
            continue
        for option in group.options:
            n = len(option.flags)
            for i in range(len(remaining) - n + 1):
                if tuple(remaining[i:i + n]) == option.flags:
                    parts.append(_(option.short))
                    del remaining[i:i + n]
                    break
    parts.extend(remaining)
    return " · ".join(parts) if parts else _("default")
