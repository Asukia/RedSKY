# glow-alert — constraints for future work

Self-hosted sunrise/sunset glow email reminder. Stdlib-only Python (>=3.11),
run on a schedule by GitHub Actions. Modules: `config` (TOML) → `schedule` (due window)
→ `openmeteo` (event times, clouds) → `sunsethue` (quality) → `runner` (decide)
→ `render` / `mailer`; `state` is the dedupe + decision log.

## Sunsethue API (from Postman docs, read 2026-10-18)
- Auth: `x-api-key` header. Keep it out of URLs/logs.
- `/event?latitude&longitude&date&type`: `date` is the location's LOCAL date;
  all response datetimes are UTC.
- `quality`/`quality_text`/`cloud_cover` only when `model_data=true`. False when
  outside 55°S–70°N, beyond ~78 h horizon, or provider issues → degraded mail.
- quality_text cutoffs: poor ≤0.20, fair ≤0.40, good ≤0.60, great ≤0.80, excellent.
- Cost: 5 credits/event with model data, 1 without. Free tier 1000/day,
  personal use only (no commercial use) — matters if this goes multi-user.
- Model: ICON (DWD), 0.25°, runs 00/06/12/18z. Accuracy in any region is
  NOT independently verified by us.

## Open-Meteo
- With explicit `timezone`, forecast times are naive local ISO strings
  (verified 2026-10-18); code attaches ZoneInfo and checks the echoed timezone.
- Geocoding only via `search-city` CLI; never resolve names at run time.

## Scheduling / GitHub Actions
- Scheduled runs can be delayed or dropped under load; only `grace_hours`
  (default 3) absorbs delays. Events already passed are logged as `missed`.
- The workflow schedule uses the `timezone` key (IANA; documented by GitHub,
  read 2026-10-19) so cron hours equal notify_at hours. Upstream default:
  twice a day, `17 8,21` Asia/Shanghai, matching config.example.toml.
  Each user must edit it to their own notify_at (README "Schedule").
- Observed 2026-10-19: upstream's hourly schedule fired only 4 times in ~17 h,
  and a private copy's two daily slots both never fired. Treat any single
  scheduled run as unreliable; README suggests a backup run an hour later.
- Dedupe key = (subscription id, event type, event LOCAL date).
- Docs say scheduled workflows auto-disable after 60 days of inactivity in
  PUBLIC repos. Use a private repo (config holds email addresses).
- Exit code ≠ 0 only for unexpected failures (GitHub then mails the owner);
  Sunsethue outages produce degraded emails with exit 0.

## Open-source / self-hosted model
- Upstream is a public template; each user makes a PRIVATE copy ("Use this
  template"), commits their own config.toml and adds their own Secrets.
  Private because config.toml holds emails and state/sent.json (sub ids, event
  times) reveals locations. Never commit a real config.toml or state/ upstream.
- Sunsethue and Open-Meteo free tiers are personal / non-commercial, which is
  why every user brings their own Sunsethue key. Open-Meteo data is CC BY 4.0
  (credited in every email footer and the README).
- The workflow skips (warning, exit 0) when config.toml is missing, so a fresh
  copy and upstream itself don't fail on every scheduled run.
- Email text lives in `render.TEXT`; `config.LANGUAGES` must match its keys
  (enforced by a test). Subject format chosen by the user (2026-10-19):
  `霞信｜<city> · 今日晚霞「良好」0.55 · 17:01` / `Redsky | <city> · Sunset today: Good (0.55) · 17:01`.
  Tests pin exact subjects; change them only on purpose.
- A multi-user hosted version (Cloudflare Workers) was built and dropped; it
  lives in the history of the author's private repo, not here.
