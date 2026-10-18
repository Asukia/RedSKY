"""Decide whether a subscription is due on this (possibly delayed) cron tick."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .config import Subscription


def due_since(sub: Subscription, now_utc: datetime, grace_hours: float) -> datetime | None:
    """Return the notify instant (UTC) whose window contains `now_utc`, else None.

    A window is [notify_at local, +grace_hours real time). Yesterday's window is
    also checked so a reminder at 23:30 still fires on a run just after midnight.
    Window arithmetic is done in UTC so DST changes do not stretch or shrink it.
    """
    if now_utc.tzinfo is None:
        raise ValueError("now_utc must be tz-aware")
    tz = sub.tz
    today = now_utc.astimezone(tz).date()
    grace = timedelta(hours=grace_hours)
    for d in (today, today - timedelta(days=1)):
        start = datetime.combine(d, sub.notify_at, tzinfo=tz).astimezone(timezone.utc)
        if start <= now_utc < start + grace:
            return start
    return None
