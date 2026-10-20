from datetime import datetime

import pytest

from ccc.cron import Cron

TUESDAY = datetime(2026, 10, 20, 17, 30)


@pytest.mark.parametrize("pattern,expected", [
    ("0 22 * * *", datetime(2026, 10, 20, 22, 0)),
    ("*/30 * * * *", datetime(2026, 10, 20, 18, 0)),
    ("0 18 * * 1-5", datetime(2026, 10, 20, 18, 0)),
    ("0 8 * * mon", datetime(2026, 10, 26, 8, 0)),
    ("0 8 * * 0", datetime(2026, 10, 25, 8, 0)),
    ("0 8 * * 7", datetime(2026, 10, 25, 8, 0)),  # 7 is Sunday too
    ("15 9 1 jan *", datetime(2027, 1, 1, 9, 15)),
    ("0 0 29 2 *", datetime(2028, 2, 29, 0, 0)),
    # Both day fields restricted: either one runs (classic cron).
    ("0 9 1 * mon", datetime(2026, 10, 26, 9, 0)),
    ("0,30 9-10/1 * * *", datetime(2026, 10, 21, 9, 0)),
])
def test_next_after(pattern, expected):
    assert Cron.parse(pattern).next_after(TUESDAY) == expected


def test_next_is_strictly_after():
    at = datetime(2026, 10, 20, 22, 0, 30)
    assert Cron.parse("0 22 * * *").next_after(at) == datetime(2026, 10, 21, 22, 0)


@pytest.mark.parametrize("pattern,message", [
    ("x", "5 fields"),
    ("* * * *", "5 fields"),
    ("0 25 * * *", "isn't a cron pattern"),
    ("*/0 * * * *", "isn't a cron pattern"),
    ("5-1 * * * *", "isn't a cron pattern"),
    ("0 0 * * foo", "isn't a cron pattern"),
    ("0 0 31 2 *", "never runs"),
])
def test_bad_patterns(pattern, message):
    with pytest.raises(ValueError, match=message):
        Cron.parse(pattern)
