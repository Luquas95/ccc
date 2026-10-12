from cc_continue.launch_options import (
    DEFAULT_SELECTION, FORK, SESSION_CONTINUE, SESSION_NEW, describe_flags,
    persistent_flags, session_mode, toggle,
)


def test_default_is_new_session_with_skip_permissions():
    assert session_mode(DEFAULT_SELECTION) == SESSION_NEW
    assert persistent_flags(DEFAULT_SELECTION) == ["--dangerously-skip-permissions"]


def test_exclusive_group_replaces_previous_choice():
    sel = toggle(DEFAULT_SELECTION, "model_opus", True)
    sel = toggle(sel, "model_sonnet", True)
    assert "model_opus" not in sel and "model_sonnet" in sel


def test_optional_exclusive_group_can_be_cleared():
    sel = toggle(DEFAULT_SELECTION, "effort_max", True)
    sel = toggle(sel, "effort_max", False)
    assert not any(k.startswith("effort_") for k in sel)


def test_required_group_cannot_be_emptied():
    sel = toggle(DEFAULT_SELECTION, "perm_skip", False)
    assert "perm_skip" in sel


def test_fork_only_with_a_resuming_session_mode():
    assert FORK not in toggle(DEFAULT_SELECTION, FORK, True)
    sel = toggle(toggle(DEFAULT_SELECTION, SESSION_CONTINUE, True), FORK, True)
    assert FORK in sel
    assert FORK not in toggle(sel, SESSION_NEW, True)


def test_persistent_flags_in_group_order_without_session_flags():
    sel = DEFAULT_SELECTION
    for key in ("model_opus", "effort_max", "other_chrome", SESSION_CONTINUE, FORK):
        sel = toggle(sel, key, True)
    assert persistent_flags(sel) == [
        "--dangerously-skip-permissions", "--model", "opus", "--effort", "max", "--chrome",
    ]


def test_describe_flags():
    assert describe_flags(None) == "legacy (skip permissions)"
    assert describe_flags(["--permission-mode", "plan", "--model", "haiku"]) == "plan only · Haiku"
    assert describe_flags(["--weird"]) == "--weird"
