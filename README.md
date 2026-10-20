# redsky · 霞信

> *Red sky at night, sailor's delight; red sky in morning, sailor's warning.*

[中文说明](README.zh-CN.md)

A self-hosted email reminder for colourful sunrises and sunsets. At a local time you choose,
it checks the [Sunsethue](https://sunsethue.com/dev-api) quality forecast for the next
sunrise or sunset and **emails you only when the score reaches your threshold**, so ordinary
days stay quiet. Works anywhere Sunsethue covers (55°S to 70°N).

- Forecast: Sunsethue API (quality score 0–1, ICON model)
- Extras: [Open-Meteo](https://open-meteo.com/) (city lookup, sunrise/sunset times, low/mid/high cloud cover; no key needed)
- Runs on GitHub Actions in your own copy of this repo: no server, no domain. Pure Python standard library.
- Emails in English or Chinese.

## What you get

On a day that reaches your threshold, an email like this (example: the times are real, the scores are illustrative):

```text
Subject: Redsky | New York · Sunset today: Great (0.72) · 18:11

New York · Sunset today

The sunset today (Sun 18 Oct) is forecast as Great, with a quality score of 0.72, meeting your alert threshold of 0.41.

  Sunset        18:11
  Golden hour   17:56 – 18:26
  Blue hour     18:31 – 18:46
  Sun azimuth   252° (W)
  Cloud cover   35% (Sunsethue)
                low 5% · mid 30% · high 55% (Open-Meteo)

Arrive by 17:56 and face west.

--
Location: New York (40.7000, -74.0000, America/New_York)
Forecast: Sunsethue (ICON model, 0.25° grid); cloud cover: Open-Meteo
Forecasts are for reference only; actual sky conditions may differ.
Subscription nyc-sunset · sent 2026-10-18 12:17 EDT
```

On other days, nothing.

## Setup

1. **Make your own private copy**: click **Use this template → Create a new repository** and choose
   **Private**. Keep it private: `config.toml` holds your email address, and the decision log
   `state/sent.json` reveals your location.
2. **Get a Sunsethue API key**: sign up at https://sunsethue.com/dev-api and generate a key in the portal
   (one per account; it is shown only once). The free tier is for personal use.
3. **Get SMTP credentials for a sending mailbox.** A separate mailbox just for sending is a good idea.
   You only obtain one thing, a password for apps (app password / authorization code), never your login password;
   the other values are fixed per provider. Check your provider's docs:

   | Provider | `SMTP_HOST` | `SMTP_PORT` | Password to obtain |
   |---|---|---|---|
   | Gmail | `smtp.gmail.com` | `465` | App password (turn on 2-Step Verification first); 16 characters, no spaces |
   | QQ Mail | `smtp.qq.com` | `465` | Authorization code (enable SMTP in mailbox settings) |
   | NetEase 163 | `smtp.163.com` | `465` | Authorization code (enable POP3/SMTP in mailbox settings) |
   | Outlook / Hotmail | | | Not supported: Microsoft requires OAuth for SMTP on personal accounts |
   | Proton Mail | `smtp.protonmail.ch` | `587` | Only on paid plans, for a custom-domain address (SMTP token) |
4. **Write your config.** Find your coordinates and timezone, either locally:
   ```bash
   python -m glow_alert search-city "Hangzhou"      # pick the right match from the list
   ```
   or with the [Open-Meteo geocoding API](https://open-meteo.com/en/docs/geocoding-api) in a browser.
   For an exact viewing spot instead of a city centre, see [Choosing a precise spot](#choosing-a-precise-spot).
   Then in your repo on GitHub, **Add file → Create new file**, name it `config.toml`, paste
   [`config.example.toml`](config.example.toml), fill it in, and commit.
5. **Set the schedule** in `.github/workflows/glow-alert.yml` (pencil icon to edit on GitHub). It runs twice a day,
   at 08:17 and 21:17 Shanghai time, to match the example config. Change it to your own `notify_at` times:
   ```yaml
       - cron: "17 8,21 * * *"        # minute 17 of hours 8 and 21
         timezone: "Asia/Shanghai"    # the timezone of your subscriptions
   ```
   For `notify_at = "12:00"` and `"21:00"`, write `"17 12,21 * * *"`. See [Schedule](#schedule) for backups and
   other timezones.
6. **Add Secrets**: your repo → Settings → Secrets and variables → Actions → **Secrets** tab →
   **New repository secret**, one per row. Names must match exactly.

   | Secret | Value |
   |---|---|
   | `SUNSETHUE_API_KEY` | your Sunsethue key |
   | `SMTP_HOST`, `SMTP_PORT` | from the table in step 3 |
   | `SMTP_USER` | the full sending address, e.g. `you@163.com` |
   | `SMTP_PASSWORD` | the app password / authorization code |
   | `MAIL_FROM` | optional display name, e.g. `Redsky <you@163.com>` (same address as `SMTP_USER`) |

   Keys only belong in Secrets; never paste them into issues, chats or `config.toml`.
7. **Test it**: Actions → glow-alert → **Run workflow**. When it finishes, open the run, click **tick** on the left,
   then expand the step **Check forecast and send**.
   - **First keep `dry_run` and `ignore_schedule` both ticked.** Nothing is sent or recorded. Each subscription
     gets one line, e.g. `INFO my-sunset: sunset 2026-10-19 -> below_threshold (q=0.05)`:
     - `alert`: the score reached your threshold; the email that would be sent is printed below it.
     - `below_threshold`: no email this time. This is normal, and most days look like this.
     - `degraded (reason)`: no forecast. `SUNSETHUE_API_KEY not set` means the secret is missing or misnamed;
       in the step's `env:` block a secret that was found shows as `***`, a missing one is blank.
   - To see an email whatever the score, set `min_quality = 0` in `config.toml` temporarily.
   - **Then untick `dry_run`** (keep `ignore_schedule`) to really send. Look for `mailed 1 recipient(s)` in the log,
     and check the spam folder the first time.
   - Put `min_quality` back afterwards, before the next scheduled run, or that run mails regardless of the score.
8. That's it. The workflow runs at the times in its schedule and mails you when a forecast reaches your threshold.

Until `config.toml` exists, scheduled runs skip with a warning instead of failing.

## Choosing a precise spot

`latitude` / `longitude` can be any point, not just a city centre: use the place you actually watch from.

1. In Google Maps, **right-click the spot**; the first line of the menu is its coordinates (e.g. `35.62700, 139.77600`).
   Click it to copy. On OpenStreetMap, right-click → "Show address" shows them too.
2. Paste the first number as `latitude` and the second as `longitude`. Five decimals (about 1 m) is plenty.
3. Find the spot's timezone by opening
   `https://api.open-meteo.com/v1/forecast?latitude=<lat>&longitude=<lon>&timezone=auto` and reading `"timezone"`.
4. Several spots are fine: add one `[[subscription]]` per spot and event, each with a unique `id`.

Don't rely on `search-city` for a spot: it knows cities and districts, and a neighbourhood name can match a namesake
elsewhere (a search for "Odaiba" returns a place in Hokkaido, not the one in Tokyo).

What a precise spot changes, and what it doesn't:
- **Same:** the glow score is very likely the same across one city. Sunsethue's model grid is 0.25° (about 28 × 23 km
  at Tokyo's latitude), so points a few kilometres apart usually fall in the same cell. This is inferred from the grid
  size; whether Sunsethue interpolates between grid points has not been checked.
- **Different:** sunrise/sunset time, sun azimuth and Open-Meteo cloud cover follow your exact point, and the email
  names the place you will actually go to.
- **Not covered by any forecast:** whether buildings, hills or trees block your view to the west (sunset) or east
  (sunrise). That depends on the spot you pick.

## How it behaves

- `notify_at` is local time in the subscription's timezone. When it is reached, the **first** sunrise/sunset
  after it is checked: an 08:00 reminder covers that day's sunset, a 21:00 reminder covers the next sunrise.
- GitHub may delay scheduled runs. Runs within `grace_hours` (default 3) after `notify_at` still count;
  if the event has already passed when the run starts, it is logged as `missed`.
- Each event is decided once. If Sunsethue is unavailable (error, quota, no model data), you get one email
  saying no forecast is available, with only Open-Meteo cloud cover.
- Every decision (sent / below threshold / degraded / missed) is recorded in `state/sent.json` and committed by
  the workflow. Compare it with the real sky later to tune your threshold.
- Cost: 5 Sunsethue credits per event. The free tier gives 1000 per day, far more than one person needs.

## Schedule

The `cron` line in `.github/workflows/glow-alert.yml` decides when the workflow runs; `notify_at` decides which runs
act. A run acts on a reminder when it lands in `[notify_at, notify_at + grace_hours)`, so pick a cron minute at or
just after the `notify_at` minute. With `timezone` set, cron hours are local hours, and daylight saving time is
handled by GitHub.

GitHub runs scheduled workflows on a best-effort basis: they can start late, and under load some are dropped.
When the one run for a reminder is dropped, that reminder is skipped silently. For reliable timing use an
[external trigger](#more-reliable-an-external-trigger); at least add a backup run an hour later. It never sends twice, because each event is decided only once:

```yaml
    - cron: "17 8,9,21,22 * * *"   # each reminder plus a backup an hour later
      timezone: "Asia/Shanghai"
```

Subscriptions in different timezones need one `- cron:` entry (with its own `timezone`) per timezone.
Private repos have a monthly Actions minutes allowance (see GitHub's billing docs). Each run is billed as at least
one minute, so two runs a day use about 60 minutes a month.

### More reliable: an external trigger

GitHub's own schedule can fail for days: in testing, a new private copy got no scheduled runs at all for two days,
while manual runs worked. An external cron service can start the workflow through the GitHub API at the time you
choose instead. Keep the `cron` schedule as a backup; each event is decided once, so you never get two emails.
[cron-job.org](https://cron-job.org) (free) is used below; any service that can send a POST request with custom
headers works.

1. **Create a token** for the external service: GitHub → your avatar → Settings → Developer settings →
   Personal access tokens → **Fine-grained tokens** → Generate new token.
   - Repository access: **Only select repositories** → your private copy.
   - Permissions: **Actions: Read and write**, nothing else. The token can then start and cancel runs of that repo,
     but not change its code or config.
   - Set an expiration and write the date down. When it expires, the requests fail; generate a new one and replace it.
   - The token is shown only once. Paste it straight into the cron service.
2. **Create a cron job** (cron-job.org field names may differ slightly):

   | Field | Value |
   |---|---|
   | URL | `https://api.github.com/repos/OWNER/REPO/actions/workflows/glow-alert.yml/dispatches` (your user and repo name) |
   | Schedule | `5 8,21 * * *`: minute 5 of each `notify_at` hour |
   | Timezone | your subscriptions' timezone, e.g. `Asia/Shanghai`. cron-job.org defaults to UTC |
   | Method | `POST` |
   | Body | `{"ref":"main","inputs":{"dry_run":"false","ignore_schedule":"false"}}` |
   | Notifications | turn on email on failure |

   Headers, one per row, name and value in separate fields:

   | Header | Value |
   |---|---|
   | `Authorization` | `Bearer github_pat_...` (the word `Bearer`, one space, the whole token; no `<>` or quotes) |
   | `Accept` | `application/vnd.github+json` |
   | `X-GitHub-Api-Version` | `2022-11-28` |
   | `Content-Type` | `application/json` |

   Minute 5 keeps the external run apart from the backup at minute 17. Both must land in
   `[notify_at, notify_at + grace_hours)`.
3. **Test it.** First set the body's two values to `"true"` and run the job once by hand. The response should be
   **204**, and Actions shows a new `workflow_dispatch` run whose **Check forecast and send** command ends in
   `--dry-run --ignore-schedule`. Then put the body back to `"false"` and run it again: the command now ends with no
   flags. Outside the reminder window the log says `not due`, which is expected. After the next reminder time, the repo
   gets a `state: record glow-alert decisions` commit.

If the response is **401**, open the failed request in the job's history and read `"message"`:
- `Requires authentication`: the `Authorization` header is missing or lacks `Bearer `.
- `Bad credentials`: the token is wrong, truncated, expired or deleted.

The values are strings because that is how the cron service sends them. The workflow treats an input as on only when
it is `true` or `"true"`.

## Run locally

```bash
python -m unittest discover -s tests                     # offline tests
python -m glow_alert run --dry-run --ignore-schedule     # print emails, send nothing (degraded path without a key)
```

## Credits and licence

- Glow forecasts from [Sunsethue](https://sunsethue.com/). Use your own key and follow their terms.
- Weather data by [Open-Meteo.com](https://open-meteo.com/), licensed under
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Their free API is for non-commercial use.
- Code: [MIT](LICENSE).

Forecasts are guidance only. This project has not verified Sunsethue's accuracy in any region.
