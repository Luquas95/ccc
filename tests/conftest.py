import pytest


@pytest.fixture(autouse=True)
def _no_live_usage_api(monkeypatch):
    # The daemon reads the account's usage (a live HTTPS request) before
    # starting items and after rate limits. Tests must never hit the
    # network: default to "usage unknown"; tests that need figures patch it.
    monkeypatch.setattr("cc_continue.orchestrator.get_pro_usage", lambda force_refresh=False: None)
