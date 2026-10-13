from datetime import datetime, timedelta

import pytest

from ccc.schedule import format_when, parse_when

NOW = datetime(2026, 10, 13, 14, 30)


def test_empty_means_now():
    assert parse_when("", NOW) is None
    assert parse_when("   ", NOW) is None


def test_hh_mm_today_or_tomorrow():
    assert parse_when("22:00", NOW) == datetime(2026, 10, 13, 22, 0)
    assert parse_when("9:05", NOW) == datetime(2026, 10, 14, 9, 5)


def test_full_datetime():
    assert parse_when("2026-10-20 08:15", NOW) == datetime(2026, 10, 20, 8, 15)


def test_reset_uses_given_reset_time():
    reset = NOW + timedelta(hours=2)
    assert parse_when("reset", NOW, reset_at=reset) == reset
    with pytest.raises(ValueError, match="(?i)usage"):
        parse_when("reset", NOW, reset_at=None)


@pytest.mark.parametrize("bad", ["25:00", "tomorrow", "2026-13-01 10:00", "12"])
def test_invalid(bad):
    with pytest.raises(ValueError):
        parse_when(bad, NOW)


def test_format_when():
    assert format_when(None, NOW) == ""
    assert format_when(datetime(2026, 10, 13, 22, 0), NOW) == "22:00"
    assert format_when(datetime(2026, 10, 14, 9, 5), NOW) == "2026-10-14 09:05"
