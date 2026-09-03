import json
import time

from cc_continue import usage_api
from cc_continue.usage_api import ProUsage, WindowUsage, get_pro_usage, parse_window


def test_parse_window_valid():
    window = parse_window({"utilization": 30.0, "resets_at": "2026-09-03T23:29:59.981152+00:00"})
    assert window.utilization_pct == 30.0
    assert window.resets_at.year == 2026


def test_parse_window_missing_fields_returns_none():
    assert parse_window(None) is None
    assert parse_window({}) is None
    assert parse_window({"utilization": 30.0}) is None  # no resets_at


def test_get_pro_usage_no_token_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(usage_api, "CACHE_PATH", tmp_path / "usage_cache.json")
    monkeypatch.setattr(usage_api, "_read_oauth_token", lambda: None)
    assert get_pro_usage() is None


def test_get_pro_usage_fetches_and_caches(monkeypatch, tmp_path):
    cache_path = tmp_path / "usage_cache.json"
    monkeypatch.setattr(usage_api, "CACHE_PATH", cache_path)
    monkeypatch.setattr(usage_api, "_read_oauth_token", lambda: "fake-token")

    calls = {"n": 0}

    def fake_fetch(token):
        calls["n"] += 1
        return ProUsage(
            five_hour=WindowUsage(30.0, __import__("datetime").datetime(2026, 9, 3, 23, 29)),
            seven_day=WindowUsage(47.0, __import__("datetime").datetime(2026, 9, 4, 12, 59)),
        )

    monkeypatch.setattr(usage_api, "fetch_live_usage", fake_fetch)

    usage = get_pro_usage()
    assert usage.five_hour.utilization_pct == 30.0
    assert calls["n"] == 1
    assert cache_path.exists()

    # second call within TTL should hit the cache, not fetch again
    usage2 = get_pro_usage()
    assert usage2.five_hour.utilization_pct == 30.0
    assert calls["n"] == 1


def test_get_pro_usage_expired_cache_refetches(monkeypatch, tmp_path):
    cache_path = tmp_path / "usage_cache.json"
    monkeypatch.setattr(usage_api, "CACHE_PATH", cache_path)
    monkeypatch.setattr(usage_api, "_read_oauth_token", lambda: "fake-token")
    cache_path.write_text(
        json.dumps(
            {
                "timestamp": time.time() - 999,
                "data": {
                    "five_hour": {"utilization": 1.0, "resets_at": "2026-09-03T23:29:59+00:00"},
                    "seven_day": None,
                },
            }
        )
    )

    calls = {"n": 0}

    def fake_fetch(token):
        calls["n"] += 1
        return ProUsage(five_hour=WindowUsage(99.0, __import__("datetime").datetime(2026, 9, 3, 23, 29)), seven_day=None)

    monkeypatch.setattr(usage_api, "fetch_live_usage", fake_fetch)

    usage = get_pro_usage()
    assert usage.five_hour.utilization_pct == 99.0
    assert calls["n"] == 1


def test_get_pro_usage_force_refresh_bypasses_cache(monkeypatch, tmp_path):
    cache_path = tmp_path / "usage_cache.json"
    monkeypatch.setattr(usage_api, "CACHE_PATH", cache_path)
    monkeypatch.setattr(usage_api, "_read_oauth_token", lambda: "fake-token")
    cache_path.write_text(
        json.dumps(
            {
                "timestamp": time.time(),
                "data": {
                    "five_hour": {"utilization": 1.0, "resets_at": "2026-09-03T23:29:59+00:00"},
                    "seven_day": None,
                },
            }
        )
    )

    def fake_fetch(token):
        return ProUsage(five_hour=WindowUsage(77.0, __import__("datetime").datetime(2026, 9, 3, 23, 29)), seven_day=None)

    monkeypatch.setattr(usage_api, "fetch_live_usage", fake_fetch)

    usage = get_pro_usage(force_refresh=True)
    assert usage.five_hour.utilization_pct == 77.0
