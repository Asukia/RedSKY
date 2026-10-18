"""Offline tests. Fixtures:
- sunsethue_event_example.json: example response copied from the Sunsethue Postman docs
- openmeteo_nyc.json: live Open-Meteo response for New York, fetched 2026-10-18
"""

import json
import tempfile
import unittest
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from glow_alert import render
from glow_alert.config import LANGUAGES, Config, ConfigError, Subscription, load_config
from glow_alert.openmeteo import parse_local_weather
from glow_alert.render import render_email
from glow_alert.runner import run_tick
from glow_alert.schedule import due_since
from glow_alert.state import State, event_key
from glow_alert.sunsethue import GlowForecast, SunsethueUnavailable, parse_event

FIX = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).parent.parent
NY = ZoneInfo("America/New_York")
UTC = timezone.utc


def make_sub(**kw) -> Subscription:
    base = dict(id="nyc", name="New York", latitude=40.7, longitude=-74.0, timezone="America/New_York",
                events=("sunset",), notify_at=time(8, 0), min_quality=0.41, emails=("me@example.com",),
                language="zh")
    base.update(kw)
    return Subscription(**base)


def nyc_weather():
    return parse_local_weather(json.loads((FIX / "openmeteo_nyc.json").read_text()), NY)


def fake_forecast(ev, quality):
    return GlowForecast(type=ev.type, time=ev.time.astimezone(UTC), quality=quality, quality_text="good",
                        cloud_cover=0.4, direction=250.0,
                        golden_hour=(ev.time - timedelta(minutes=15), ev.time + timedelta(minutes=15)),
                        blue_hour=(ev.time + timedelta(minutes=20), ev.time + timedelta(minutes=35)))


class ConfigTests(unittest.TestCase):
    def write(self, text):
        f = tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False)
        f.write(text)
        f.close()
        return Path(f.name)

    def test_example_config_loads(self):
        cfg = load_config(ROOT / "config.example.toml")
        self.assertEqual(len(cfg.subscriptions), 1)
        s = cfg.subscriptions[0]
        self.assertEqual((s.notify_at, s.events, s.emails), (time(8, 0), ("sunset",), ("you@example.com",)))

    def _sub_toml(self, **override):
        fields = dict(id='"a"', latitude="10", longitude="10", timezone='"UTC"', events='["sunset"]',
                      notify_at='"08:00"', email='"a@b.co"')
        fields.update(override)
        return "[[subscription]]\n" + "\n".join(f"{k} = {v}" for k, v in fields.items())

    def test_rejects_latitude_outside_sunsethue_band(self):
        with self.assertRaisesRegex(ConfigError, "outside Sunsethue"):
            load_config(self.write(self._sub_toml(latitude="78.2")))

    def test_rejects_bad_timezone_event_time(self):
        for override, msg in [(dict(timezone='"Mars/Base"'), "timezone"), (dict(events='["noon"]'), "events"),
                              (dict(notify_at='"8:00"'), "HH:MM"), (dict(email='"nope"'), "email")]:
            with self.subTest(override=override), self.assertRaisesRegex(ConfigError, msg):
                load_config(self.write(self._sub_toml(**override)))

    def test_language_default_and_validation(self):
        self.assertEqual(load_config(self.write(self._sub_toml())).subscriptions[0].language, "en")
        self.assertEqual(load_config(self.write(self._sub_toml(language='"zh"'))).subscriptions[0].language, "zh")
        with self.assertRaisesRegex(ConfigError, "language"):
            load_config(self.write(self._sub_toml(language='"fr"')))

    def test_every_config_language_has_email_text(self):
        self.assertEqual(set(LANGUAGES), set(render.TEXT))

    def test_rejects_duplicate_ids(self):
        with self.assertRaisesRegex(ConfigError, "duplicate"):
            load_config(self.write(self._sub_toml() + "\n" + self._sub_toml()))


class ScheduleTests(unittest.TestCase):
    def test_window_bounds(self):
        sub = make_sub(notify_at=time(8, 0))
        at = lambda h, m: datetime(2026, 10, 18, h, m, tzinfo=NY).astimezone(UTC)
        self.assertIsNone(due_since(sub, at(7, 59), 3))
        self.assertEqual(due_since(sub, at(8, 0), 3), at(8, 0))
        self.assertEqual(due_since(sub, at(10, 59), 3), at(8, 0))
        self.assertIsNone(due_since(sub, at(11, 0), 3))

    def test_window_crosses_midnight(self):
        sub = make_sub(notify_at=time(23, 30))
        now = datetime(2026, 10, 19, 0, 20, tzinfo=NY).astimezone(UTC)
        self.assertEqual(due_since(sub, now, 3), datetime(2026, 10, 18, 23, 30, tzinfo=NY).astimezone(UTC))

    def test_window_is_real_hours_across_dst(self):
        # US spring-forward 2026-03-08 02:00 EST -> 03:00 EDT. 01:30 EST = 06:30Z; 3h grace ends 09:30Z.
        sub = make_sub(notify_at=time(1, 30))
        self.assertIsNotNone(due_since(sub, datetime(2026, 3, 8, 9, 29, tzinfo=UTC), 3))
        self.assertIsNone(due_since(sub, datetime(2026, 3, 8, 9, 30, tzinfo=UTC), 3))

    def test_naive_now_rejected(self):
        with self.assertRaises(ValueError):
            due_since(make_sub(), datetime(2026, 10, 18, 12), 3)


class SourceParsingTests(unittest.TestCase):
    def test_sunsethue_example(self):
        fc = parse_event(json.loads((FIX / "sunsethue_event_example.json").read_text()))
        self.assertEqual(fc.type, "sunset")
        self.assertAlmostEqual(fc.quality, 0.34)
        self.assertEqual(fc.quality_text, "fair")
        self.assertEqual(fc.time, datetime(2024, 11, 24, 21, 32, tzinfo=UTC))
        self.assertEqual(fc.golden_hour[0], datetime(2024, 11, 24, 21, 17, tzinfo=UTC))
        # 21:32Z is 16:32 EST, a plausible late-November New York sunset.
        self.assertEqual(fc.time.astimezone(NY).strftime("%H:%M"), "16:32")

    def test_sunsethue_without_model_data(self):
        payload = json.loads((FIX / "sunsethue_event_example.json").read_text())
        payload["data"] = {k: v for k, v in payload["data"].items() if k not in ("quality", "quality_text", "cloud_cover")}
        payload["data"]["model_data"] = False
        with self.assertRaises(SunsethueUnavailable):
            parse_event(payload)

    def test_sunsethue_error_body(self):
        with self.assertRaises(SunsethueUnavailable):
            parse_event({"status": 400, "code": 204, "message": "Exceeded daily quota"})

    def test_openmeteo_live_fixture(self):
        w = nyc_weather()
        self.assertEqual(len(w.events), 6)
        self.assertEqual([e.type for e in w.events[:2]], ["sunrise", "sunset"])
        first_sunset = w.events[1]
        self.assertEqual(first_sunset.time, datetime(2026, 10, 18, 18, 11, tzinfo=NY))
        self.assertEqual(len(w.clouds_by_hour), 72)
        c = w.clouds_at(first_sunset.time)
        for v in (c.low, c.mid, c.high):
            self.assertTrue(0 <= v <= 100)

    def test_openmeteo_timezone_mismatch(self):
        data = json.loads((FIX / "openmeteo_nyc.json").read_text())
        with self.assertRaises(ValueError):
            parse_local_weather(data, ZoneInfo("Asia/Shanghai"))

    def test_openmeteo_missing_event_skipped(self):
        data = json.loads((FIX / "openmeteo_nyc.json").read_text())
        data["daily"]["sunrise"][0] = None
        self.assertEqual(len(parse_local_weather(data, NY).events), 5)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.sent = []

    def tick(self, now_local, quality=0.5, subs=None, glow=None, **kw):
        cfg = Config(grace_hours=3, subscriptions=tuple(subs or [make_sub()]))
        state = kw.pop("state", None) or State(self.tmp / "sent.json")
        glow = glow or (lambda sub, ev: fake_forecast(ev, quality))
        errors = run_tick(cfg, state, now_local.astimezone(UTC), lambda sub: nyc_weather(), glow,
                          lambda sub, subj, body: self.sent.append((sub.id, subj, body)), render_email, **kw)
        return state, errors

    def test_alert_when_above_threshold(self):
        state, errors = self.tick(datetime(2026, 10, 18, 8, 17, tzinfo=NY), quality=0.55)
        self.assertEqual(errors, [])
        self.assertEqual(len(self.sent), 1)
        subj, body = self.sent[0][1], self.sent[0][2]
        self.assertIn("今天18:11", subj)
        self.assertIn("预测质量：0.55", body)
        self.assertIn("黄金时刻：17:56–18:26", body)
        rec = state.records[event_key("nyc", "sunset", date(2026, 10, 18))]
        self.assertEqual((rec["outcome"], rec["mailed"]), ("alert", True))

    def test_english_alert(self):
        self.tick(datetime(2026, 10, 18, 8, 17, tzinfo=NY), quality=0.55, subs=[make_sub(language="en")])
        subj, body = self.sent[0][1], self.sent[0][2]
        self.assertEqual(subj, "[Glow alert] New York: Sunset today 18:11 (good 0.55)")
        self.assertIn("Quality: 0.55 / 1 (good; your threshold 0.41)", body)
        self.assertIn("Golden hour: 17:56–18:26", body)
        self.assertIn("Sun azimuth: 250° (W)", body)

    def test_silent_below_threshold_but_logged(self):
        state, _ = self.tick(datetime(2026, 10, 18, 8, 17, tzinfo=NY), quality=0.30)
        self.assertEqual(self.sent, [])
        rec = state.records[event_key("nyc", "sunset", date(2026, 10, 18))]
        self.assertEqual((rec["outcome"], rec["mailed"], rec["quality"]), ("below_threshold", False, 0.30))

    def test_dedupe_across_delayed_runs(self):
        state, _ = self.tick(datetime(2026, 10, 18, 8, 17, tzinfo=NY))
        state.save()
        self.tick(datetime(2026, 10, 18, 9, 17, tzinfo=NY), state=State(self.tmp / "sent.json"))
        self.assertEqual(len(self.sent), 1)

    def test_not_due(self):
        state, _ = self.tick(datetime(2026, 10, 18, 12, 17, tzinfo=NY))
        self.assertEqual((self.sent, state.records), ([], {}))

    def test_evening_reminder_targets_tomorrow_sunrise(self):
        sub = make_sub(events=("sunrise",), notify_at=time(21, 0))
        state, _ = self.tick(datetime(2026, 10, 18, 21, 17, tzinfo=NY), subs=[sub])
        self.assertIn("明天07:11", self.sent[0][1])
        self.assertIn(event_key("nyc", "sunrise", date(2026, 10, 19)), state.records)

    def test_degraded_mail_when_sunsethue_down(self):
        def down(sub, ev):
            raise SunsethueUnavailable("HTTP 500")
        state, errors = self.tick(datetime(2026, 10, 18, 8, 17, tzinfo=NY), glow=down)
        self.assertEqual(errors, [])
        self.assertIn("降级", self.sent[0][1])
        self.assertIn("HTTP 500", self.sent[0][2])
        self.assertEqual(state.records[event_key("nyc", "sunset", date(2026, 10, 18))]["outcome"], "degraded")

    def test_missed_when_run_after_event(self):
        sub = make_sub(notify_at=time(17, 0))
        state, _ = self.tick(datetime(2026, 10, 18, 18, 30, tzinfo=NY), subs=[sub])
        self.assertEqual(self.sent, [])
        self.assertEqual(state.records[event_key("nyc", "sunset", date(2026, 10, 18))]["outcome"], "missed")

    def test_ignore_schedule_does_not_record(self):
        state, _ = self.tick(datetime(2026, 10, 18, 12, 17, tzinfo=NY), ignore_schedule=True, record=False)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(state.records, {})

    def test_one_failing_subscription_does_not_block_others(self):
        def glow(sub, ev):
            if sub.id == "bad":
                raise RuntimeError("boom")
            return fake_forecast(ev, 0.6)
        _, errors = self.tick(datetime(2026, 10, 18, 8, 17, tzinfo=NY),
                              subs=[make_sub(id="bad"), make_sub(id="good")], glow=glow)
        self.assertEqual([s[0] for s in self.sent], ["good"])
        self.assertEqual(len(errors), 1)
        self.assertIn("bad", errors[0])


if __name__ == "__main__":
    unittest.main()
