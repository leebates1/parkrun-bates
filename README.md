# BATES family parkrun dashboard

Auto-generated interactive dashboard for the Bates family's Widnes parkrun results.

**Live site:** https://leebates1.github.io/parkrun-bates/

## How it works

- A GitHub Action runs on Saturdays after results publish
- [`scripts/build.py`](scripts/build.py) updates the dashboard data when live parkrun data is available, otherwise it keeps the last published dashboard
- Historical weather for each run date is fetched from [Open-Meteo](https://open-meteo.com)
- [`scripts/template.html`](scripts/template.html) is rendered with the data to `docs/index.html`
- GitHub Pages serves `docs/` as the live site

## Running locally

```bash
python3 scripts/build.py
open docs/index.html
```

## Adding a runner

Edit [`scripts/runners.json`](scripts/runners.json).
