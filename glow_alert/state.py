"""Decision log, committed back to the repo by the workflow.

One record per (subscription, event type, event local date). It doubles as
dedupe state across delayed/duplicate cron runs and as a log you can later
annotate with what the sky actually did, to calibrate `min_quality`.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

STATE_VERSION = 1


def event_key(sub_id: str, event_type: str, local_date: date) -> str:
    return f"{sub_id}|{event_type}|{local_date.isoformat()}"


class State:
    def __init__(self, path: Path):
        self.path = path
        self.records: dict[str, dict] = {}
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if raw.get("version") != STATE_VERSION:
                raise ValueError(f"{path}: unsupported state version {raw.get('version')!r}")
            self.records = raw["records"]

    def has(self, key: str) -> bool:
        return key in self.records

    def record(self, key: str, entry: dict) -> None:
        if key in self.records:
            raise KeyError(f"state already has {key}")
        self.records[key] = entry

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": STATE_VERSION, "records": self.records},
                                  ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                       encoding="utf-8")
        os.replace(tmp, self.path)
