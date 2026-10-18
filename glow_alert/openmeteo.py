"""Open-Meteo: city search, sunrise/sunset times, and layered cloud cover.

Free, no API key. With an explicit `timezone`, the forecast API returns times
as naive local ISO strings (e.g. "2026-10-18T17:25"), verified 2026-10-18; we
attach the subscription's ZoneInfo to them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from .http import get_json

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


@dataclass(frozen=True)
class SunEvent:
    type: str  # "sunrise" | "sunset"
    local_date: date
    time: datetime  # tz-aware, subscription timezone


@dataclass(frozen=True)
class CloudLayers:
    low: float  # percent 0..100
    mid: float
    high: float


@dataclass(frozen=True)
class LocalWeather:
    events: tuple[SunEvent, ...]  # sorted by time
    clouds_by_hour: dict[datetime, CloudLayers]  # tz-aware hour start -> layers

    def next_event(self, event_type: str, after: datetime) -> SunEvent | None:
        for ev in self.events:
            if ev.type == event_type and ev.time > after:
                return ev
        return None

    def clouds_at(self, when: datetime) -> CloudLayers | None:
        hour = when.replace(minute=0, second=0, microsecond=0)
        return self.clouds_by_hour.get(hour)


def search_city(name: str, count: int = 5, language: str = "en") -> list[dict]:
    data = get_json(GEOCODING_URL, {"name": name, "count": count,
                                    "language": language, "format": "json"})
    return data.get("results", [])


def fetch_local_weather(lat: float, lon: float, tz: ZoneInfo, days: int = 3) -> LocalWeather:
    data = get_json(FORECAST_URL, {
        "latitude": lat,
        "longitude": lon,
        "daily": "sunrise,sunset",
        "hourly": "cloud_cover_low,cloud_cover_mid,cloud_cover_high",
        "timezone": tz.key,
        "forecast_days": days,
    })
    return parse_local_weather(data, tz)


def parse_local_weather(data: dict, tz: ZoneInfo) -> LocalWeather:
    if data.get("timezone") != tz.key:
        raise ValueError(f"Open-Meteo answered in timezone {data.get('timezone')!r}, expected {tz.key!r}")

    daily = data["daily"]
    events = []
    for day_str, rise, sset in zip(daily["time"], daily["sunrise"], daily["sunset"], strict=True):
        d = date.fromisoformat(day_str)
        for ev_type, value in (("sunrise", rise), ("sunset", sset)):
            # Polar day/night: no event that day. Sunsethue's band ends at 70N,
            # so this only matters near the edge; skip rather than invent a time.
            if not value:
                continue
            events.append(SunEvent(ev_type, d, datetime.fromisoformat(value).replace(tzinfo=tz)))
    events.sort(key=lambda e: e.time)

    hourly = data["hourly"]
    clouds = {}
    for t, lo, mi, hi in zip(hourly["time"], hourly["cloud_cover_low"],
                             hourly["cloud_cover_mid"], hourly["cloud_cover_high"], strict=True):
        if None in (lo, mi, hi):
            continue
        clouds[datetime.fromisoformat(t).replace(tzinfo=tz)] = CloudLayers(float(lo), float(mi), float(hi))

    return LocalWeather(tuple(events), clouds)
