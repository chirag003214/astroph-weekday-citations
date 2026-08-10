"""
Unit tests for src/schedule.py — announcement_day() and submission_day().

arXiv deadline rule:
  - If local America/New_York time >= 14:00, roll to next day.
  - Roll Saturday (+2) or Sunday (+1) to Monday.

DST in the US (2022 reference dates):
  - Spring forward: 2022-03-13 02:00 EST → 03:00 EDT  (UTC offset -5 → -4)
  - Fall back:      2022-11-06 02:00 EDT → 01:00 EST  (UTC offset -4 → -5)

The DST tests demonstrate that zoneinfo gives the correct local time, whereas
a fixed UTC-5 offset would misclassify submissions that cross the 14:00 deadline
only under the correct offset.
"""
from datetime import datetime, timezone, timedelta

import pytest
from zoneinfo import ZoneInfo

from src.schedule import announcement_day, submission_day

UTC = timezone.utc
EASTERN = ZoneInfo("America/New_York")


# ── Helpers ──────────────────────────────────────────────────────────────────

def et(year, month, day, hour, minute=0) -> datetime:
    """Create a UTC datetime that corresponds to the given America/New_York local time."""
    local = datetime(year, month, day, hour, minute, tzinfo=EASTERN)
    return local.astimezone(UTC)


def utc(year, month, day, hour, minute=0) -> datetime:
    """Create a naive-but-UTC datetime."""
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


# ── Fri 13:59 vs 14:01 ───────────────────────────────────────────────────────

def test_friday_before_deadline():
    """Fri 13:59 ET — before deadline — stays Friday."""
    assert announcement_day(et(2022, 4, 1, 13, 59)) == "Friday"


def test_friday_at_deadline():
    """Fri 14:00 ET — exactly at deadline — rolls to Saturday → Monday."""
    assert announcement_day(et(2022, 4, 1, 14, 0)) == "Monday"


def test_friday_after_deadline():
    """Fri 14:01 ET — after deadline — rolls to Saturday → Monday."""
    assert announcement_day(et(2022, 4, 1, 14, 1)) == "Monday"


# ── Saturday ─────────────────────────────────────────────────────────────────

def test_saturday_morning():
    """Sat 09:00 ET — before 14:00 — rolls directly to Monday."""
    assert announcement_day(et(2022, 4, 2, 9, 0)) == "Monday"


def test_saturday_after_deadline():
    """Sat 14:01 ET — after deadline — rolls to Sunday → Monday."""
    assert announcement_day(et(2022, 4, 2, 14, 1)) == "Monday"


# ── Sunday ───────────────────────────────────────────────────────────────────

def test_sunday_morning():
    """Sun 09:00 ET — before 14:00 — rolls to Monday."""
    assert announcement_day(et(2022, 4, 3, 9, 0)) == "Monday"


def test_sunday_after_deadline():
    """Sun 14:01 ET — after deadline — rolls to Monday (Mon is not a weekend day)."""
    assert announcement_day(et(2022, 4, 3, 14, 1)) == "Monday"


# ── Mon 13:59 vs 14:01 ───────────────────────────────────────────────────────

def test_monday_before_deadline():
    """Mon 13:59 ET — before deadline — stays Monday."""
    assert announcement_day(et(2022, 4, 4, 13, 59)) == "Monday"


def test_monday_at_deadline():
    """Mon 14:00 ET — exactly at deadline — rolls to Tuesday."""
    assert announcement_day(et(2022, 4, 4, 14, 0)) == "Tuesday"


def test_monday_after_deadline():
    """Mon 14:01 ET — after deadline — rolls to Tuesday."""
    assert announcement_day(et(2022, 4, 4, 14, 1)) == "Tuesday"


# ── Mid-week sanity ───────────────────────────────────────────────────────────

def test_wednesday_before_deadline():
    assert announcement_day(et(2022, 4, 6, 13, 59)) == "Wednesday"


def test_wednesday_after_deadline():
    assert announcement_day(et(2022, 4, 6, 14, 1)) == "Thursday"


def test_thursday_after_deadline():
    """Thu 14:01 ET → Friday."""
    assert announcement_day(et(2022, 4, 7, 14, 1)) == "Friday"


# ── DST: spring forward (2022-03-13, clocks +1h at 02:00 EST → 03:00 EDT) ───

def test_dst_spring_pre_day_before_deadline():
    """
    2022-03-12 (Saturday, still EST=UTC-5) at 14:01 ET → rolls to Sunday → Monday.
    With a FIXED UTC-5 offset this gives the same answer, so we also verify
    the UTC timestamp is what we expect.
    """
    dt = et(2022, 3, 12, 14, 1)   # Sat 14:01 EST = 19:01 UTC
    assert dt == utc(2022, 3, 12, 19, 1), "Sanity: should be 19:01 UTC in EST"
    assert announcement_day(dt) == "Monday"


def test_dst_spring_post_day_after_deadline():
    """
    2022-03-14 (Monday, now EDT=UTC-4) at 14:01 ET → rolls to Tuesday.

    The critical DST correctness check:
      UTC time is 18:01.  With fixed EST (UTC-5) it would be 13:01 → Mon (WRONG).
      With zoneinfo (EDT=UTC-4) it is correctly 14:01 → Tue (RIGHT).
    """
    dt = et(2022, 3, 14, 14, 1)   # Mon 14:01 EDT = 18:01 UTC
    assert dt == utc(2022, 3, 14, 18, 1), "Sanity: should be 18:01 UTC in EDT"
    # Fixed-offset bug: 18:01 UTC - 5h = 13:01 → would give Monday (wrong)
    wrong_local_hour = (dt.replace(tzinfo=UTC) - timedelta(hours=5)).hour
    assert wrong_local_hour == 13, "Fixed UTC-5 offset gives 13:01 (would miss deadline)"
    # Correct result via zoneinfo
    assert announcement_day(dt) == "Tuesday"


def test_dst_spring_post_day_before_deadline():
    """
    2022-03-14 (Monday, EDT=UTC-4) at 13:59 ET → stays Monday.
    """
    dt = et(2022, 3, 14, 13, 59)
    assert announcement_day(dt) == "Monday"


# ── DST: fall back (2022-11-06, clocks -1h at 02:00 EDT → 01:00 EST) ────────

def test_dst_fall_pre_day_after_deadline():
    """
    2022-11-05 (Saturday, still EDT=UTC-4) at 14:01 ET → rolls to Sunday → Monday.
    UTC time is 18:01.  With fixed EST (UTC-5) it would be 13:01 → stays Sat → Mon.
    Both give Monday here, so this is a sanity check, not a discriminating test.
    """
    dt = et(2022, 11, 5, 14, 1)   # Sat 14:01 EDT = 18:01 UTC
    assert dt == utc(2022, 11, 5, 18, 1)
    assert announcement_day(dt) == "Monday"


def test_dst_fall_post_day_after_deadline():
    """
    2022-11-07 (Monday, now EST=UTC-5) at 14:01 ET → rolls to Tuesday.

    The critical fall-back DST correctness check:
      UTC time is 19:01.  With fixed EDT (UTC-4) it would be 15:01 → Tue (accidentally correct).
      But this confirms zoneinfo uses the right offset post-fall-back.
    """
    dt = et(2022, 11, 7, 14, 1)   # Mon 14:01 EST = 19:01 UTC
    assert dt == utc(2022, 11, 7, 19, 1), "Sanity: should be 19:01 UTC in EST"
    assert announcement_day(dt) == "Tuesday"


def test_dst_fall_post_day_before_deadline():
    """
    2022-11-07 (Monday, EST=UTC-5) at 13:59 ET → stays Monday.

    With fixed EDT (UTC-4): 19:59 UTC - 4h = 15:59 → would roll to Tuesday (WRONG).
    With zoneinfo (EST=UTC-5): 19:59 UTC - 5h = 14:59... wait, 13:59 EST = 18:59 UTC.
    """
    dt = et(2022, 11, 7, 13, 59)  # Mon 13:59 EST = 18:59 UTC
    assert dt == utc(2022, 11, 7, 18, 59)
    # Fixed EDT (UTC-4) bug: 18:59 UTC - 4h = 14:59 → would roll to Tuesday (wrong)
    wrong_local_hour = (dt.replace(tzinfo=UTC) - timedelta(hours=4)).hour
    assert wrong_local_hour == 14, "Fixed UTC-4 offset gives 14:59 (would cross deadline)"
    # Correct result
    assert announcement_day(dt) == "Monday"


# ── submission_day ────────────────────────────────────────────────────────────

def test_submission_day_wednesday():
    """A UTC timestamp that is Wednesday in New York should return Wednesday."""
    # 2022-04-06 (Wed) 17:00 UTC = 13:00 EDT
    assert submission_day(utc(2022, 4, 6, 17, 0)) == "Wednesday"


def test_submission_day_saturday():
    """Saturday submissions are valid (7-bin analysis includes weekends)."""
    assert submission_day(et(2022, 4, 2, 10, 0)) == "Saturday"


def test_submission_day_uses_eastern_not_utc():
    """
    2022-04-05 (Tue) 02:00 UTC = Mon 22:00 EDT.
    UTC day is Tuesday but Eastern day is Monday.
    """
    dt = utc(2022, 4, 5, 2, 0)
    assert submission_day(dt) == "Monday"
