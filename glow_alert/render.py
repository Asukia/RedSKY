"""Plain-text email rendering (Chinese or English, per subscription `language`).

Subject:  霞信｜东京 · 今日晚霞「良好」0.55 · 17:01
          Redsky | Tokyo · Sunset today: Good (0.55) · 17:01
Body: per event a heading, one lead sentence, an aligned facts table and (for
alerts) when to arrive and which way to face; then a footer with the location,
data sources and subscription id.
"""

from __future__ import annotations

from datetime import date, datetime

from .config import Subscription
from .runner import EventDecision

_ZH_PAD = "　"  # full-width space, keeps CJK labels aligned

TEXT = {
    "zh": {
        "event": {"sunrise": "朝霞", "sunset": "晚霞"},
        "event_time": {"sunrise": "日出时刻", "sunset": "日落时刻"},
        "grade": {"poor": "欠佳", "fair": "一般", "good": "良好", "great": "优秀", "excellent": "绝佳"},
        "weekday": ("周一", "周二", "周三", "周四", "周五", "周六", "周日"),
        "compass": ("北", "东北", "东", "东南", "南", "西南", "西", "西北"),
        "days": {0: "今日", 1: "明日", 2: "后日"},
        "subject": "霞信｜{name} · {parts}", "joiner": "；",
        "subj_alert": "{day}{event}「{grade}」{q:.2f} · {hm}",
        "subj_degraded": "{day}{event}暂无预测 · {hm}",
        "heading": "{name} · {day}{event}",
        "lead_alert": "{when}{event}预测为「{grade}」，质量指数 {q:.2f}，已达到您设定的提醒阈值 {threshold:.2f}。",
        "lead_degraded": "{when}暂未取得{event}预测（原因：{reason}）。以下仅列出云量，并非{event}预测，请您自行判断。",
        "golden": "黄金时刻", "blue": "蓝调时刻", "direction": "太阳方位", "clouds": "云　　量",
        "direction_value": "{deg:.0f}°（{compass}）",
        "sh_clouds": "{pct:.0f}%（Sunsethue）",
        "om_clouds": "低 {low:.0f}% · 中 {mid:.0f}% · 高 {high:.0f}%（Open-Meteo）",
        "advice": "建议于 {hm} 前抵达，面向{facing}方取景。",
        "footer": ["——",
                   "地点：{name}（{lat:.4f}, {lon:.4f}，{tz}）",
                   "预测：Sunsethue（ICON 模型，0.25° 网格）；云量：Open-Meteo",
                   "预测仅供参考，以实际天象为准。",
                   "订阅 {id} · 发送于 {sent}"],
    },
    "en": {
        "event": {"sunrise": "Sunrise", "sunset": "Sunset"},
        "event_time": {"sunrise": "Sunrise", "sunset": "Sunset"},
        "grade": {"poor": "Poor", "fair": "Fair", "good": "Good", "great": "Great", "excellent": "Excellent"},
        "weekday": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
        "month": ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
        "compass": ("N", "NE", "E", "SE", "S", "SW", "W", "NW"),
        "facing": ("north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"),
        "days": {0: "today", 1: "tomorrow"},
        "subject": "Redsky | {name} · {parts}", "joiner": "; ",
        "subj_alert": "{event} {day}: {grade} ({q:.2f}) · {hm}",
        "subj_degraded": "{event} {day}: forecast unavailable · {hm}",
        "heading": "{name} · {event} {day}",
        "lead_alert": "The {event_lc} {when} is forecast as {grade}, with a quality score of {q:.2f}, "
                      "meeting your alert threshold of {threshold:.2f}.",
        "lead_degraded": "No glow forecast is available for the {event_lc} {when}. Reason: {reason}. "
                         "Cloud cover is listed below for reference only; it is not a glow forecast.",
        "golden": "Golden hour", "blue": "Blue hour", "direction": "Sun azimuth", "clouds": "Cloud cover",
        "direction_value": "{deg:.0f}° ({compass})",
        "sh_clouds": "{pct:.0f}% (Sunsethue)",
        "om_clouds": "low {low:.0f}% · mid {mid:.0f}% · high {high:.0f}% (Open-Meteo)",
        "advice": "Arrive by {hm} and face {facing}.",
        "footer": ["--",
                   "Location: {name} ({lat:.4f}, {lon:.4f}, {tz})",
                   "Forecast: Sunsethue (ICON model, 0.25° grid); cloud cover: Open-Meteo",
                   "Forecasts are for reference only; actual sky conditions may differ.",
                   "Subscription {id} · sent {sent}"],
    },
}
LANGUAGES = tuple(TEXT)


def _octant(deg: float) -> int:
    return int((deg % 360) / 45 + 0.5) % 8


def _hm(dt: datetime, sub: Subscription) -> str:
    return dt.astimezone(sub.tz).strftime("%H:%M")


def _day_and_when(lang: str, t: dict, ev_date: date, today: date) -> tuple[str, str]:
    """Return (day word for subject/heading, day phrase with the full date for the lead sentence)."""
    weekday = t["weekday"][ev_date.weekday()]
    word = t["days"].get((ev_date - today).days)
    if lang == "zh":
        md = f"{ev_date.month}月{ev_date.day}日"
        return (word, f"{word}（{md} {weekday}）") if word else (md, f"{md}（{weekday}）")
    dmy = f"{weekday} {ev_date.day} {t['month'][ev_date.month - 1]}"
    return (word, f"{word} ({dmy})") if word else (f"on {dmy}", f"on {dmy}")


def _row(lang: str, label: str, value: str) -> str:
    if lang == "zh":
        return f"{_ZH_PAD}{label}{_ZH_PAD}{value}"
    return f"  {label:<13} {value}"


def _continuation(lang: str, value: str) -> str:
    return (_ZH_PAD * 6 if lang == "zh" else " " * 16) + value


def _event_section(sub: Subscription, d: EventDecision, t: dict, today: date) -> tuple[str, list[str]]:
    lang, ev = sub.language, d.event
    day, when = _day_and_when(lang, t, ev.local_date, today)
    event = t["event"][ev.type]
    hm = _hm(ev.time, sub)
    lines = [t["heading"].format(name=sub.name, day=day, event=event), ""]
    rows = [_row(lang, t["event_time"][ev.type], hm)]
    om = t["om_clouds"].format(low=d.clouds.low, mid=d.clouds.mid, high=d.clouds.high) if d.clouds else None

    if d.outcome == "alert":
        f = d.forecast
        grade = t["grade"].get(f.quality_text, f.quality_text)
        subject = t["subj_alert"].format(day=day, event=event, grade=grade, q=f.quality, hm=hm)
        lines.append(t["lead_alert"].format(when=when, event=event, event_lc=event.lower(), grade=grade,
                                            q=f.quality, threshold=sub.min_quality))
        if f.golden_hour:
            rows.append(_row(lang, t["golden"], f"{_hm(f.golden_hour[0], sub)} – {_hm(f.golden_hour[1], sub)}"))
        if f.blue_hour:
            rows.append(_row(lang, t["blue"], f"{_hm(f.blue_hour[0], sub)} – {_hm(f.blue_hour[1], sub)}"))
        compass = t["compass"][_octant(f.direction)]
        rows.append(_row(lang, t["direction"], t["direction_value"].format(deg=f.direction, compass=compass)))
        rows.append(_row(lang, t["clouds"], t["sh_clouds"].format(pct=f.cloud_cover * 100)))
        if om:
            rows.append(_continuation(lang, om))
        # Earliest useful light: blue hour precedes sunrise, golden hour precedes sunset.
        starts = [w[0] for w in (f.golden_hour, f.blue_hour) if w] or [ev.time]
        facing = t.get("facing", t["compass"])[_octant(f.direction)]
        advice = t["advice"].format(hm=_hm(min(starts), sub), facing=facing)
    else:
        subject = t["subj_degraded"].format(day=day, event=event, hm=hm)
        lines.append(t["lead_degraded"].format(when=when, event=event, event_lc=event.lower(), reason=d.reason))
        if om:
            rows.append(_row(lang, t["clouds"], om))
        advice = None

    lines += [""] + rows
    if advice:
        lines += ["", advice]
    return subject, lines


def render_email(sub: Subscription, decisions: list[EventDecision], now_utc: datetime) -> tuple[str, str]:
    t = TEXT[sub.language]
    now_local = now_utc.astimezone(sub.tz)
    subject_parts, lines = [], []
    for d in decisions:
        part, section = _event_section(sub, d, t, now_local.date())
        subject_parts.append(part)
        lines += section + [""]

    subject = t["subject"].format(name=sub.name, parts=t["joiner"].join(subject_parts))
    lines += [line.format(name=sub.name, lat=sub.latitude, lon=sub.longitude, tz=sub.timezone, id=sub.id,
                          sent=now_local.strftime("%Y-%m-%d %H:%M %Z"))
              for line in t["footer"]]
    return subject, "\n".join(lines) + "\n"
