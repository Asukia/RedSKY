"""Sunsethue `/event` client.

API facts (Postman docs, read 2026-10-18):
- auth: `x-api-key` header
- `date` is the location's LOCAL date; every datetime in the response is UTC
- `quality`, `quality_text`, `cloud_cover` exist only when `model_data` is true
  (false outside 55S..70N, beyond the ~3-day horizon, or on provider issues)
- cost: 5 credits per event with model data, 1 without; free tier 1000/day
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from .http import HttpError, get_json

EVENT_URL = "https://api.sunsethue.com/event"


class SunsethueUnavailable(RuntimeError):
    """No usable model forecast; caller should fall back to a degraded email."""


@dataclass(frozen=True)
class GlowForecast:
    type: str
    time: datetime  # UTC, tz-aware
    quality: float  # 0..1
    quality_text: str  # poor | fair | good | great | excellent
    cloud_cover: float  # 0..1
    direction: float  # degrees
    golden_hour: tuple[datetime, datetime] | None
    blue_hour: tuple[datetime, datetime] | None


def _utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _span(values) -> tuple[datetime, datetime] | None:
    if not values or len(values) != 2:
        return None
    return _utc(values[0]), _utc(values[1])


def parse_event(payload: dict) -> GlowForecast:
    if "data" not in payload:
        raise SunsethueUnavailable(f"unexpected response: {str(payload)[:200]}")
    d = payload["data"]
    if not d.get("model_data"):
        raise SunsethueUnavailable("model_data=false (no Sunsethue forecast for this event)")
    quality = float(d["quality"])
    if not 0 <= quality <= 1:
        raise SunsethueUnavailable(f"quality {quality} outside [0, 1]")
    magics = d.get("magics") or {}
    return GlowForecast(
        type=d["type"],
        time=_utc(d["time"]),
        quality=quality,
        quality_text=str(d["quality_text"]).lower(),
        cloud_cover=float(d["cloud_cover"]),
        direction=float(d["direction"]),
        golden_hour=_span(magics.get("golden_hour")),
        blue_hour=_span(magics.get("blue_hour")),
    )


def fetch_event(api_key: str, lat: float, lon: float, local_date: date, event_type: str) -> GlowForecast:
    try:
        payload = get_json(
            EVENT_URL,
            {"latitude": round(lat, 4), "longitude": round(lon, 4),
             "date": local_date.isoformat(), "type": event_type},
            headers={"x-api-key": api_key},
        )
    except HttpError as exc:
        raise SunsethueUnavailable(str(exc)) from exc
    forecast = parse_event(payload)
    if forecast.type != event_type:
        raise SunsethueUnavailable(f"asked for {event_type}, got {forecast.type}")
    return forecast
