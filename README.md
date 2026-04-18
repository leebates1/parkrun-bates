# BATES family parkrun dashboard

Auto-generated interactive dashboard for the Bates family's Widnes parkrun results.

**Live site:** https://leebates1.github.io/parkrun-bates/

## How it works

- A GitHub Action runs every Saturday at 12:00 UTC
- [`scripts/build.py`](scripts/build.py) tries the parkrun app API when credentials are available, then falls back to scraping each runner's parkrun results page
- Historical weather for each run date is fetched from [Open-Meteo](https://open-meteo.com)
- [`scripts/template.html`](scripts/template.html) is rendered with the data to `docs/index.html`
- GitHub Pages serves `docs/` as the live site

## Running locally

```bash
python3 scripts/build.py
open docs/index.html
```

To try the app API locally, set your parkrun login before running:

```bash
export PARKRUN_USERNAME=A1234567
export PARKRUN_PASSWORD='your-parkrun-password'
python3 scripts/build.py
```

For GitHub Actions, add repository secrets named `PARKRUN_USERNAME` and `PARKRUN_PASSWORD`. If the app API fails or the secrets are missing, the build falls back to the existing scraper/cache path.

## Adding a runner

Edit [`scripts/runners.json`](scripts/runners.json).
