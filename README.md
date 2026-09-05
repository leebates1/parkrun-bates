# BATES family parkrun dashboard

Auto-generated interactive dashboard for the Bates family's Widnes parkrun results.

**Live site:** https://leebates1.github.io/parkrun-bates/

## How it works

- A GitHub Action runs on Saturdays after results publish
- [`scripts/build.py`](scripts/build.py) updates the dashboard data when live parkrun data is available, otherwise it keeps the last published dashboard
- Historical weather for each run date is fetched from [Open-Meteo](https://open-meteo.com)
- [`scripts/template.html`](scripts/template.html) is rendered with the data to `docs/index.html`
- GitHub Pages serves `docs/` as the live site

## Updating the dashboard

parkrun blocks GitHub Actions runner IPs — `api.parkrun.com` returns 403 and the
website returns 405 — so the scheduled workflow **reports success while
publishing nothing**. A green tick is not evidence the site is current; check
the newest date on the dashboard itself. The same code works fine from a normal
machine, so updates are published from there.

**Click the app.** `Update parkrun dashboard` in Launchpad, Spotlight or the
Dock fetches the latest results, rebuilds, pushes, and tells you what it found.
Build it once with:

```bash
./scripts/make-app.sh
```

Re-run that if the repo ever moves. To do the same thing from a terminal:

```bash
./scripts/publish.sh
```

Either way it only commits when the results have actually changed — a rebuild
alone just restamps `generatedAt`. Log: `~/Library/Logs/parkrun-dashboard.log`.

## Running locally without publishing

```bash
python3 scripts/build.py
open docs/index.html
```

## Adding a runner

Edit [`scripts/runners.json`](scripts/runners.json).
