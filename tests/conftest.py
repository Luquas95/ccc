import os

import pytest

# Tests run in English whatever the machine's locale or ccc setting (see ccc.i18n).
os.environ["CCC_LANG"] = "en"



@pytest.fixture(autouse=True)
def _no_live_usage_api(monkeypatch):
    # The daemon reads the account's usage (a live HTTPS request) before
    # starting items and after rate limits. Tests must never hit the
    # network: default to "usage unknown"; tests that need figures patch it.
    monkeypatch.setattr("ccc.orchestrator.get_pro_usage", lambda force_refresh=False: None)


@pytest.fixture(autouse=True)
def _no_real_tmux(monkeypatch):
    # Interactive conversations start a real `claude` in tmux (and paste
    # prompts into it) — a test that reached that code once sent a real
    # prompt. Every test fakes managed_sessions / cli_pane at the level it
    # needs; reaching the real tmux fails loudly instead.
    def refuse(args, input_text=None):
        raise RuntimeError(f"test tried to run real tmux: {args}")

    monkeypatch.setattr("ccc.managed_sessions._run", refuse)
    # Tests may run inside tmux: never split the developer's own window.
    monkeypatch.delenv("TMUX", raising=False)
    monkeypatch.delenv("TMUX_PANE", raising=False)
