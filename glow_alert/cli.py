"""Command line entry point.

    python -m glow_alert search-city "Hangzhou"
    python -m glow_alert run --config config.toml [--dry-run] [--ignore-schedule]
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import openmeteo, sunsethue
from .config import load_config
from .mailer import SmtpSettings, send_email
from .render import render_email
from .runner import run_tick
from .state import State


def _cmd_search_city(args) -> int:
    results = openmeteo.search_city(args.name, count=args.count, language=args.language)
    if not results:
        print(f"no match for {args.name!r}", file=sys.stderr)
        return 1
    for r in results:
        admin = " / ".join(x for x in (r.get("admin1"), r.get("admin2")) if x)
        print(f"{r['name']}  [{r.get('country', '?')} {admin}]  pop={r.get('population', '?')}")
        print(f"    latitude = {r['latitude']}\n    longitude = {r['longitude']}\n"
              f"    timezone = \"{r['timezone']}\"")
    return 0


def _parse_now(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise SystemExit("--now must include a UTC offset, e.g. 2026-10-18T00:17:00+00:00")
    return dt.astimezone(timezone.utc)


def _cmd_run(args) -> int:
    config = load_config(Path(args.config))
    state = State(Path(args.state))
    now_utc = _parse_now(args.now)

    api_key = os.environ.get("SUNSETHUE_API_KEY")
    if not api_key and not args.dry_run:
        raise SystemExit("SUNSETHUE_API_KEY is not set")

    def glow_fetcher(sub, ev):
        if not api_key:
            raise sunsethue.SunsethueUnavailable("SUNSETHUE_API_KEY not set (dry run)")
        return sunsethue.fetch_event(api_key, sub.latitude, sub.longitude, ev.local_date, ev.type)

    def weather_fetcher(sub):
        return openmeteo.fetch_local_weather(sub.latitude, sub.longitude, sub.tz)

    if args.dry_run:
        def send(sub, subject, body):
            print(f"--- would mail {', '.join(sub.emails)} ---\nSubject: {subject}\n\n{body}")
    else:
        smtp = SmtpSettings.from_env()

        def send(sub, subject, body):
            send_email(smtp, sub.emails, subject, body)
            logging.info("%s: mailed %d recipient(s)", sub.id, len(sub.emails))

    record = not (args.dry_run or args.ignore_schedule)
    errors = run_tick(config, state, now_utc, weather_fetcher, glow_fetcher, send, render_email,
                      ignore_schedule=args.ignore_schedule, record=record)
    if record:
        state.save()
    for e in errors:
        print(f"ERROR {e}", file=sys.stderr)
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="glow_alert", description="Sunrise/sunset glow email reminder")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("search-city", help="look up coordinates and timezone for a place name")
    p.add_argument("name")
    p.add_argument("--count", type=int, default=5)
    p.add_argument("--language", default="en", help="result language, e.g. en, zh, de")
    p.set_defaults(func=_cmd_search_city)

    p = sub.add_parser("run", help="process one scheduler tick")
    p.add_argument("--config", default="config.toml")
    p.add_argument("--state", default="state/sent.json")
    p.add_argument("--dry-run", action="store_true", help="print emails instead of sending; do not write state")
    p.add_argument("--ignore-schedule", action="store_true",
                   help="treat every subscription as due now and ignore the log; does not write state")
    p.add_argument("--now", help="override current time (ISO 8601 with offset), for testing")
    p.set_defaults(func=_cmd_run)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    return args.func(args)
