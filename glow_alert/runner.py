"""One cron tick: find due subscriptions, evaluate their next events, mail, log.

External calls are injected (`weather_fetcher`, `glow_fetcher`, `send`) so the
decision logic is testable offline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from .config import Config, Subscription
from .openmeteo import CloudLayers, LocalWeather, SunEvent
from .schedule import due_since
from .state import State, event_key
from .sunsethue import GlowForecast, SunsethueUnavailable

log = logging.getLogger(__name__)

# Outcomes: "alert" and "degraded" are mailed; the rest are only logged.
MAILED = ("alert", "degraded")

WeatherFetcher = Callable[[Subscription], LocalWeather]
GlowFetcher = Callable[[Subscription, SunEvent], GlowForecast]
Sender = Callable[[Subscription, str, str], None]


@dataclass(frozen=True)
class EventDecision:
    event: SunEvent
    outcome: str  # alert | below_threshold | degraded | missed
    forecast: GlowForecast | None = None
    clouds: CloudLayers | None = None
    reason: str | None = None

    def log_entry(self, sub: Subscription, now_utc: datetime, mailed: bool) -> dict:
        entry = {
            "outcome": self.outcome,
            "mailed": mailed,
            "event_time": self.event.time.isoformat(),
            "decided_at": now_utc.isoformat(timespec="seconds"),
            "min_quality": sub.min_quality,
        }
        if self.forecast:
            entry |= {"quality": self.forecast.quality, "quality_text": self.forecast.quality_text,
                      "cloud_cover": self.forecast.cloud_cover}
        if self.clouds:
            entry["clouds_low_mid_high"] = [self.clouds.low, self.clouds.mid, self.clouds.high]
        if self.reason:
            entry["reason"] = self.reason
        return entry


def evaluate(sub: Subscription, notify_utc: datetime, now_utc: datetime, weather: LocalWeather,
             glow_fetcher: GlowFetcher, skip: Callable[[str], bool]) -> list[EventDecision]:
    decisions = []
    for ev_type in sub.events:
        ev = weather.next_event(ev_type, after=notify_utc)
        if ev is None:
            raise RuntimeError(f"{sub.id}: no {ev_type} in the Open-Meteo forecast window")
        if skip(event_key(sub.id, ev.type, ev.local_date)):
            continue
        clouds = weather.clouds_at(ev.time)
        if ev.time <= now_utc:
            # The run was delayed past the event itself; a late mail is useless.
            decisions.append(EventDecision(ev, "missed", clouds=clouds, reason="run started after the event"))
            continue
        try:
            fc = glow_fetcher(sub, ev)
        except SunsethueUnavailable as exc:
            decisions.append(EventDecision(ev, "degraded", clouds=clouds, reason=str(exc)))
            continue
        outcome = "alert" if fc.quality >= sub.min_quality else "below_threshold"
        decisions.append(EventDecision(ev, outcome, forecast=fc, clouds=clouds))
    return decisions


def run_tick(config: Config, state: State, now_utc: datetime, weather_fetcher: WeatherFetcher,
             glow_fetcher: GlowFetcher, send: Sender, render, *, ignore_schedule: bool = False,
             record: bool = True) -> list[str]:
    """Process all subscriptions. Returns error messages (one per failed subscription).

    ignore_schedule: treat every subscription as due now and ignore the dedupe log
    (manual test runs). Recording is the caller's choice via `record`.
    """
    errors = []
    for sub in config.subscriptions:
        notify_utc = now_utc if ignore_schedule else due_since(sub, now_utc, config.grace_hours)
        if notify_utc is None:
            log.info("%s: not due", sub.id)
            continue
        try:
            weather = weather_fetcher(sub)
            skip = (lambda _k: False) if ignore_schedule else state.has
            decisions = evaluate(sub, notify_utc, now_utc, weather, glow_fetcher, skip)
            to_mail = [d for d in decisions if d.outcome in MAILED]
            for d in decisions:
                log.info("%s: %s %s -> %s%s", sub.id, d.event.type, d.event.local_date, d.outcome,
                         f" (q={d.forecast.quality:.2f})" if d.forecast else f" ({d.reason})" if d.reason else "")
            if to_mail:
                subject, body = render(sub, to_mail, now_utc)
                send(sub, subject, body)
            if record:
                for d in decisions:
                    state.record(event_key(sub.id, d.event.type, d.event.local_date),
                                 d.log_entry(sub, now_utc, mailed=d.outcome in MAILED))
        except Exception as exc:  # one broken subscription must not block the others
            log.exception("%s: failed", sub.id)
            errors.append(f"{sub.id}: {exc}")
    return errors
