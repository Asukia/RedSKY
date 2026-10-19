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

## Setup

1. **Make your own private copy**: click **Use this template → Create a new repository** and choose
   **Private**. Keep it private: `config.toml` holds your email address, and the decision log
   `state/sent.json` reveals your location.
2. **Get a Sunsethue API key**: sign up at https://sunsethue.com/dev-api and generate a key in the portal
   (one per account; it is shown only once). The free tier is for personal use.
3. **Get SMTP credentials for a sending mailbox.** A separate mailbox just for sending is a good idea.
   Use an app password or SMTP authorization code, not your login password. Examples (check your provider's docs):
   - Gmail: `smtp.gmail.com`, port 465, needs 2-step verification and an app password
   - QQ Mail: `smtp.qq.com`, port 465, enable SMTP in settings to get an authorization code
4. **Write your config.** Find your coordinates and timezone, either locally:
   ```bash
   python -m glow_alert search-city "Hangzhou"      # pick the right match from the list
   ```
   or with the [Open-Meteo geocoding API](https://open-meteo.com/en/docs/geocoding-api) in a browser.
   For an exact viewing spot instead of a city centre, see [Choosing a precise spot](#choosing-a-precise-spot).
   Then in your repo on GitHub, **Add file → Create new file**, name it `config.toml`, paste
   [`config.example.toml`](config.example.toml), fill it in, and commit.
5. **Add Secrets**: your repo → Settings → Secrets and variables → Actions → New repository secret:
   `SUNSETHUE_API_KEY`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, and optionally `MAIL_FROM`.
6. **Test it**: Actions → glow-alert → Run workflow.
   - First keep both `dry_run` and `ignore_schedule` ticked: the email is printed in the log, nothing is sent or recorded.
   - Then untick `dry_run` to really send. `ignore_schedule` only skips the "is it time yet" check; the threshold
     still applies, so on a poor day you get no email. Set `min_quality = 0` temporarily to force one.
7. That's it. The workflow runs every hour and acts when a reminder is due.

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

## Why hourly, and running less often

The schedule (`cron`) in `.github/workflows/glow-alert.yml` is in UTC and the same for everyone, while each person's
`notify_at` is local. Hourly runs serve any time in any timezone without editing the workflow, handle daylight
saving time, and give spare tries when GitHub runs late or skips a run.

If you prefer fewer runs, edit the `cron` line so that each run lands in `[notify_at, notify_at + grace_hours)`.
Example for Hangzhou (UTC+8) with reminders at 08:00 and 21:00 local, i.e. 00:00 and 13:00 UTC:

```yaml
    - cron: "17 0,1,13,14 * * *"   # one run per reminder plus one backup an hour later
```

The backup run never sends twice: each event is only decided once. Without it, a run GitHub skips means no
reminder that day. In a timezone with daylight saving time, check that your times still fall inside the window
in both summer and winter. Private repos have a monthly Actions minutes allowance (see GitHub's billing docs);
hourly runs use about 720 minutes a month, because each run is billed as at least one minute.

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
