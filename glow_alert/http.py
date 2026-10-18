"""Minimal JSON-over-HTTP helper (stdlib only)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "glow-alert/0.1 (personal sunrise/sunset reminder)"


class HttpError(RuntimeError):
    pass


def get_json(url: str, params: dict, headers: dict | None = None,
             timeout: float = 20.0, retries: int = 1) -> dict:
    """GET `url?params` and decode JSON. Retries once on network errors and 5xx.

    Error messages never include request headers, so API keys passed as headers
    do not leak into logs.
    """
    full = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(full, headers={"User-Agent": USER_AGENT, **(headers or {})})
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            body = exc.read(500).decode("utf-8", "replace")
            if exc.code < 500:
                raise HttpError(f"HTTP {exc.code} from {url}: {body}") from exc
            last_exc = HttpError(f"HTTP {exc.code} from {url}: {body}")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_exc = HttpError(f"request to {url} failed: {exc}")
        if attempt < retries:
            time.sleep(2)
    raise last_exc  # type: ignore[misc]
