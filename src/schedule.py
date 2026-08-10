"""
Day-of-week computation for arXiv submission and announcement days.

arXiv schedule:
  - Submission deadline: 14:00 US/Eastern on weekdays.
  - Announcements: Sunday–Thursday evenings (Mon–Fri listings).
  - Submissions from Fri 14:00 ET through Mon 14:00 ET → Monday listing.

Known limitation: US holidays occasionally shift announcements; not handled here.
"""
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")

_WEEKDAY_NAMES = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]
WEEKDAYS_7 = _WEEKDAY_NAMES          # Mon–Sun (submission_day bins)
WEEKDAYS_5 = _WEEKDAY_NAMES[:5]      # Mon–Fri (announcement_day bins)


def submission_day(utc_dt: datetime) -> str:
    """Return the weekday name of the v1 UTC timestamp converted to America/New_York."""
    local = utc_dt.astimezone(EASTERN)
    return _WEEKDAY_NAMES[local.weekday()]


def announcement_day(utc_dt: datetime) -> str:
    """
    Return the arXiv announcement weekday (Mon–Fri) for a v1 UTC timestamp.

    Algorithm:
      1. Convert to America/New_York using zoneinfo (handles DST correctly).
      2. If local time >= 14:00, advance the effective date by one day
         (submission missed that day's deadline).
      3. Roll Saturday (+2 days) or Sunday (+1 day) forward to Monday,
         since arXiv makes no announcements on weekends.

    Returns one of: "Monday", "Tuesday", "Wednesday", "Thursday", "Friday".

    Known limitation: US federal holidays occasionally delay arXiv announcements;
    this function does not account for them.
    """
    local = utc_dt.astimezone(EASTERN)
    effective = local.date()
    if local.hour >= 14:
        effective += timedelta(days=1)
    wd = effective.weekday()   # 0=Mon … 5=Sat, 6=Sun
    if wd == 5:                # Saturday → Monday
        effective += timedelta(days=2)
    elif wd == 6:              # Sunday → Monday
        effective += timedelta(days=1)
    return _WEEKDAY_NAMES[effective.weekday()]


def announcement_date(utc_dt: datetime) -> date:
    """
    Return the calendar date of the arXiv announcement for a given v1 UTC timestamp.
    Uses the same deadline/weekend-roll logic as announcement_day.
    Used for the listing-size proxy analysis (Dietrich 2007 motivation).
    """
    local = utc_dt.astimezone(EASTERN)
    effective = local.date()
    if local.hour >= 14:
        effective += timedelta(days=1)
    wd = effective.weekday()
    if wd == 5:
        effective += timedelta(days=2)
    elif wd == 6:
        effective += timedelta(days=1)
    return effective
