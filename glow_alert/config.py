"""Load and validate the subscription config (TOML).

Every subscription carries explicit coordinates and an IANA timezone; city names
are never resolved at run time (use `python -m glow_alert search-city` once and
paste the result), so an ambiguous name can never silently pick the wrong place.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from datetime import time
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

EVENT_TYPES = ("sunrise", "sunset")
LANGUAGES = ("en", "zh")  # must match render.TEXT

# Sunsethue only produces model forecasts inside this latitude band (API docs).
SUNSETHUE_MIN_LAT = -55.0
SUNSETHUE_MAX_LAT = 70.0

_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Subscription:
    id: str
    name: str
    latitude: float
    longitude: float
    timezone: str
    events: tuple[str, ...]
    notify_at: time  # wall-clock time in `timezone`
    min_quality: float  # 0..1; 0 means "always send"
    emails: tuple[str, ...]
    language: str = "en"  # email language, one of LANGUAGES

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@dataclass(frozen=True)
class Config:
    grace_hours: float
    subscriptions: tuple[Subscription, ...]


def _parse_hhmm(value: object, where: str) -> time:
    if not isinstance(value, str) or not re.fullmatch(r"\d{2}:\d{2}", value):
        raise ConfigError(f"{where}: notify_at must be 'HH:MM', got {value!r}")
    hh, mm = int(value[:2]), int(value[3:])
    if hh > 23 or mm > 59:
        raise ConfigError(f"{where}: notify_at out of range: {value!r}")
    return time(hh, mm)


def _parse_subscription(raw: dict, index: int) -> Subscription:
    where = f"subscription[{index}]"
    required = ("id", "latitude", "longitude", "timezone", "events", "notify_at", "email")
    missing = [k for k in required if k not in raw]
    if missing:
        raise ConfigError(f"{where}: missing keys {missing}")

    sub_id = raw["id"]
    if not isinstance(sub_id, str) or not _ID_RE.match(sub_id):
        raise ConfigError(f"{where}: id must match [A-Za-z0-9_-]+, got {sub_id!r}")
    where = f"subscription '{sub_id}'"

    lat, lon = raw["latitude"], raw["longitude"]
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (lat, lon)):
        raise ConfigError(f"{where}: latitude/longitude must be numbers")
    if not -180 <= lon <= 180:
        raise ConfigError(f"{where}: longitude {lon} out of range")
    if not SUNSETHUE_MIN_LAT <= lat <= SUNSETHUE_MAX_LAT:
        raise ConfigError(
            f"{where}: latitude {lat} is outside Sunsethue's forecast band "
            f"[{SUNSETHUE_MIN_LAT}, {SUNSETHUE_MAX_LAT}]"
        )

    tz_name = raw["timezone"]
    try:
        ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
        raise ConfigError(f"{where}: unknown timezone {tz_name!r}") from exc

    events = raw["events"]
    if isinstance(events, str):
        events = [events]
    if not events or any(e not in EVENT_TYPES for e in events) or len(set(events)) != len(events):
        raise ConfigError(f"{where}: events must be a non-empty subset of {EVENT_TYPES}, got {events!r}")

    min_quality = raw.get("min_quality", 0.41)
    if not isinstance(min_quality, (int, float)) or not 0 <= min_quality <= 1:
        raise ConfigError(f"{where}: min_quality must be in [0, 1], got {min_quality!r}")

    emails = raw["email"]
    if isinstance(emails, str):
        emails = [emails]
    if not emails or any(not isinstance(e, str) or not _EMAIL_RE.match(e) for e in emails):
        raise ConfigError(f"{where}: invalid email {raw['email']!r}")

    language = raw.get("language", "en")
    if language not in LANGUAGES:
        raise ConfigError(f"{where}: language must be one of {LANGUAGES}, got {language!r}")

    return Subscription(
        id=sub_id,
        name=str(raw.get("name", sub_id)),
        latitude=float(lat),
        longitude=float(lon),
        timezone=tz_name,
        events=tuple(events),
        notify_at=_parse_hhmm(raw["notify_at"], where),
        min_quality=float(min_quality),
        emails=tuple(emails),
        language=language,
    )


def load_config(path: Path) -> Config:
    with open(path, "rb") as f:
        raw = tomllib.load(f)

    grace_hours = raw.get("grace_hours", 3)
    if not isinstance(grace_hours, (int, float)) or not 0 < grace_hours <= 12:
        raise ConfigError(f"grace_hours must be in (0, 12], got {grace_hours!r}")

    subs_raw = raw.get("subscription", [])
    if not subs_raw:
        raise ConfigError("config has no [[subscription]] entries")
    subs = tuple(_parse_subscription(s, i) for i, s in enumerate(subs_raw))

    ids = [s.id for s in subs]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ConfigError(f"duplicate subscription ids: {sorted(dupes)}")

    return Config(grace_hours=float(grace_hours), subscriptions=subs)
