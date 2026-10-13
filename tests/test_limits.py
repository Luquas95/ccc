from datetime import datetime, timedelta, timezone

from ccc.limits import RESET_BUFFER, exhausted_until, retry_time_after_rate_limit
from ccc.usage_api import ModelUsage, ProUsage, WindowUsage

NOW = datetime(2026, 10, 12, 14, 0)


def _utc(local_naive: datetime) -> datetime:
    """Aware UTC datetime for a naive local time, like the usage API returns."""
    return local_naive.astimezone().astimezone(timezone.utc)


def _usage(five=None, week=None, per_model=()):
    return ProUsage(
        five_hour=WindowUsage(five[0], _utc(five[1])) if five else None,
        seven_day=WindowUsage(week[0], _utc(week[1])) if week else None,
        per_model=[ModelUsage(m, pct, _utc(at)) for m, pct, at in per_model],
    )


def test_no_usage_means_no_information():
    assert exhausted_until(None, NOW) is None
    assert retry_time_after_rate_limit(None, NOW) is None


def test_nothing_exhausted():
    usage = _usage(five=(80, NOW + timedelta(hours=1)), week=(40, NOW + timedelta(days=2)))
    assert exhausted_until(usage, NOW) is None


def test_five_hour_exhausted_waits_for_its_reset_plus_buffer():
    reset = NOW + timedelta(hours=1)
    assert exhausted_until(_usage(five=(100, reset)), NOW) == reset + RESET_BUFFER


def test_several_exhausted_windows_wait_for_the_latest():
    usage = _usage(five=(100, NOW + timedelta(hours=1)), week=(100, NOW + timedelta(days=2)))
    assert exhausted_until(usage, NOW) == NOW + timedelta(days=2) + RESET_BUFFER


def test_per_model_window_counts():
    reset = NOW + timedelta(days=1)
    assert exhausted_until(_usage(five=(10, NOW), per_model=[("Opus", 100, reset)]), NOW) == reset + RESET_BUFFER


def test_reset_already_passed_is_ignored():
    assert exhausted_until(_usage(five=(100, NOW - timedelta(minutes=5))), NOW) is None


def test_after_rate_limit_uses_busiest_window_even_below_100():
    five_reset = NOW + timedelta(hours=2)
    usage = _usage(five=(97, five_reset), week=(50, NOW + timedelta(days=3)))
    assert retry_time_after_rate_limit(usage, NOW) == five_reset + RESET_BUFFER


def test_after_rate_limit_with_past_reset_gives_none():
    assert retry_time_after_rate_limit(_usage(five=(100, NOW - timedelta(hours=1))), NOW) is None
