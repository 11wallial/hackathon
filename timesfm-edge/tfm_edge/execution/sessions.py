"""Trading calendar. Deliberately small.

WeekdayCalendar treats Monday to Friday as sessions and knows nothing about holidays. That
is acceptable here because every consumer is protected another way: a holiday has no new bar,
so the freshness check (last bar date == last completed session) fails and no plan is made,
and the broker rejects orders on a closed day. Where a holiday matters more than that, wire
in the broker's own calendar endpoint; do not hand-maintain a holiday table.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
MARKET_OPEN, MARKET_CLOSE = time(9, 30), time(16, 0)


def to_et(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("naive datetime: pass an aware one so ET conversion is unambiguous")
    return dt.astimezone(ET)


def parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


class WeekdayCalendar:
    def is_session(self, d: date) -> bool:
        return d.weekday() < 5

    def last_completed_session(self, now: datetime) -> date:
        et = to_et(now)
        d = et.date()
        if self.is_session(d) and et.time() >= MARKET_CLOSE:
            return d
        d -= timedelta(days=1)
        while not self.is_session(d):
            d -= timedelta(days=1)
        return d

    def session_label(self, now: datetime) -> date:
        """The session a timestamp belongs to: today's once the market has opened, otherwise the
        last completed one. Equity snapshots are labelled with this, so the previous session's
        last snapshot is the 'start of day' for the daily loss limit."""
        et = to_et(now)
        if self.is_session(et.date()) and et.time() >= MARKET_OPEN:
            return et.date()
        return self.last_completed_session(now)

    def sessions_between(self, a: date, b: date) -> int:
        """Number of sessions after a, up to and including b."""
        n, d = 0, a
        while d < b:
            d = self.next_session(d)
            n += 1
        return n

    def next_session(self, d: date) -> date:
        d += timedelta(days=1)
        while not self.is_session(d):
            d += timedelta(days=1)
        return d

    def open_utc(self, d: date) -> datetime:
        return datetime.combine(d, MARKET_OPEN, tzinfo=ET).astimezone(timezone.utc)


class EveryDayCalendar(WeekdayCalendar):
    """Every calendar day is a session. For tests, whose synthetic bars include weekends."""
    def is_session(self, d: date) -> bool:
        return True
