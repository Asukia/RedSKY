"""Plain-text email rendering (Chinese or English, per subscription `language`)."""

from __future__ import annotations

from datetime import datetime

from .config import Subscription
from .runner import EventDecision

TEXT = {
    "zh": {
        "event": {"sunrise": "日出·朝霞", "sunset": "日落·晚霞"},
        "quality": {"poor": "差", "fair": "一般", "good": "好", "great": "很好", "excellent": "极佳"},
        "weekday": tuple(f"周{c}" for c in "一二三四五六日"),
        "compass": ("北", "东北", "东", "东南", "南", "西南", "西", "西北"),
        "days": {0: "今天", 1: "明天", 2: "后天"},
        "head": "【{event}】{date} {weekday}（{day}）{hm}",
        "subj_alert": "{day}{hm} {event} {quality_local} {q:.2f}",
        "subj_degraded": "{day}{hm} {event} 无预测",
        "quality_line": "  预测质量：{q:.2f} / 1（{quality_text} {quality_local}；你的阈值 {threshold:.2f}）",
        "golden": "  黄金时刻：{start}–{end}",
        "blue": "  蓝调时刻：{start}–{end}",
        "direction": "  太阳方位：{deg:.0f}°（{compass}）",
        "sh_clouds": "  Sunsethue 云量：{pct:.0f}%",
        "degraded": ["  ⚠ 降级：Sunsethue 预测不可用（{reason}）",
                     "  下面只有云量，不是朝霞/晚霞预测，请自行判断。"],
        "om_clouds": "  Open-Meteo 当时云量：低 {low:.0f}% · 中 {mid:.0f}% · 高 {high:.0f}%",
        "tag": "朝晚霞提醒", "tag_degraded": "朝晚霞提醒·降级",
        "subject": "[{tag}] {name}：{parts}", "joiner": "；",
        "footer": ["地点：{name}（{lat:.4f}, {lon:.4f}，{tz}）",
                   "数据：Sunsethue 预测（ICON 模型，0.25° 网格）；云量参考 Open-Meteo。预测仅供参考。",
                   "订阅：{id} · 生成于 {generated}"],
    },
    "en": {
        "event": {"sunrise": "Sunrise", "sunset": "Sunset"},
        "quality": {"poor": "poor", "fair": "fair", "good": "good", "great": "great", "excellent": "excellent"},
        "weekday": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
        "compass": ("N", "NE", "E", "SE", "S", "SW", "W", "NW"),
        "days": {0: "today", 1: "tomorrow"},
        "head": "[{event}] {weekday} {date} ({day}) {hm}",
        "subj_alert": "{event} {day} {hm} ({quality_local} {q:.2f})",
        "subj_degraded": "{event} {day} {hm} (no forecast)",
        "quality_line": "  Quality: {q:.2f} / 1 ({quality_text}; your threshold {threshold:.2f})",
        "golden": "  Golden hour: {start}–{end}",
        "blue": "  Blue hour: {start}–{end}",
        "direction": "  Sun azimuth: {deg:.0f}° ({compass})",
        "sh_clouds": "  Sunsethue cloud cover: {pct:.0f}%",
        "degraded": ["  ⚠ Degraded: Sunsethue forecast unavailable ({reason})",
                     "  Only cloud cover below; this is not a glow forecast, judge for yourself."],
        "om_clouds": "  Open-Meteo cloud cover at that time: low {low:.0f}% · mid {mid:.0f}% · high {high:.0f}%",
        "tag": "Glow alert", "tag_degraded": "Glow alert · degraded",
        "subject": "[{tag}] {name}: {parts}", "joiner": "; ",
        "footer": ["Location: {name} ({lat:.4f}, {lon:.4f}, {tz})",
                   "Data: Sunsethue forecast (ICON model, 0.25° grid); cloud cover from Open-Meteo. "
                   "Forecasts are guidance only.",
                   "Subscription: {id} · generated {generated}"],
    },
}
LANGUAGES = tuple(TEXT)


def _compass(deg: float, t: dict) -> str:
    return t["compass"][int((deg % 360) / 45 + 0.5) % 8]


def _day_label(ev_date, now_local: datetime, t: dict) -> str:
    delta = (ev_date - now_local.date()).days
    return t["days"].get(delta, ev_date.isoformat())


def _hm(dt: datetime, sub: Subscription) -> str:
    return dt.astimezone(sub.tz).strftime("%H:%M")


def render_email(sub: Subscription, decisions: list[EventDecision], now_utc: datetime) -> tuple[str, str]:
    t = TEXT[sub.language]
    now_local = now_utc.astimezone(sub.tz)
    degraded = any(d.outcome == "degraded" for d in decisions)

    subject_parts, lines = [], []
    for d in decisions:
        ev = d.event
        common = dict(event=t["event"][ev.type], day=_day_label(ev.local_date, now_local, t), hm=_hm(ev.time, sub))
        lines.append(t["head"].format(date=ev.local_date.isoformat(),
                                      weekday=t["weekday"][ev.local_date.weekday()], **common))
        if d.outcome == "alert":
            f = d.forecast
            quality_local = t["quality"].get(f.quality_text, f.quality_text)
            subject_parts.append(t["subj_alert"].format(quality_local=quality_local, q=f.quality, **common))
            lines.append(t["quality_line"].format(q=f.quality, quality_text=f.quality_text,
                                                  quality_local=t["quality"].get(f.quality_text, ""),
                                                  threshold=sub.min_quality))
            if f.golden_hour:
                lines.append(t["golden"].format(start=_hm(f.golden_hour[0], sub), end=_hm(f.golden_hour[1], sub)))
            if f.blue_hour:
                lines.append(t["blue"].format(start=_hm(f.blue_hour[0], sub), end=_hm(f.blue_hour[1], sub)))
            lines.append(t["direction"].format(deg=f.direction, compass=_compass(f.direction, t)))
            lines.append(t["sh_clouds"].format(pct=f.cloud_cover * 100))
        else:
            subject_parts.append(t["subj_degraded"].format(**common))
            lines += [line.format(reason=d.reason) for line in t["degraded"]]
        if d.clouds:
            c = d.clouds
            lines.append(t["om_clouds"].format(low=c.low, mid=c.mid, high=c.high))
        lines.append("")

    subject = t["subject"].format(tag=t["tag_degraded"] if degraded else t["tag"], name=sub.name,
                                  parts=t["joiner"].join(subject_parts))
    lines += [line.format(name=sub.name, lat=sub.latitude, lon=sub.longitude, tz=sub.timezone, id=sub.id,
                          generated=now_local.strftime("%Y-%m-%d %H:%M %Z"))
              for line in t["footer"]]
    return subject, "\n".join(lines) + "\n"
