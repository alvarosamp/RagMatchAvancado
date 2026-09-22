from datetime import datetime, timezone
import os

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/test")

from app.jobs.queue import _month_bounds_utc, monthly_quota_reached


def test_monthly_quota_is_unlimited_when_unset():
    assert monthly_quota_reached(None, 1_000_000) is False


def test_monthly_quota_blocks_at_limit_including_zero():
    assert monthly_quota_reached(0, 0) is True
    assert monthly_quota_reached(10, 9) is False
    assert monthly_quota_reached(10, 10) is True


def test_month_bounds_roll_over_year_in_utc():
    start, end = _month_bounds_utc(datetime(2026, 12, 31, 23, 0, tzinfo=timezone.utc))
    assert start == datetime(2026, 12, 1)
    assert end == datetime(2027, 1, 1)
