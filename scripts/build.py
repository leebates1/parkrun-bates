#!/usr/bin/env python3
"""Fetch parkrun results, fetch historical weather from Open-Meteo, and render
a self-contained HTML dashboard into docs/index.html."""
import base64
import json
import os
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "scripts" / "runners.json").read_text())
TEMPLATE = (ROOT / "scripts" / "template.html").read_text()
OUT = ROOT / "docs" / "index.html"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
APP_UA = "parkrun/1.2.7 CFNetwork/1121.2.2 Darwin/19.3.0"
API_BASE = os.environ.get("PARKRUN_API_BASE", "https://api.parkrun.com").rstrip("/")
API_CLIENT_ID = os.environ.get("PARKRUN_API_CLIENT_ID", "netdreams-iphone-s01")
API_CLIENT_SECRET = os.environ.get(
    "PARKRUN_API_CLIENT_SECRET",
    "gfKbDD6NJkYoFmkisR(iVFopQCKWzbQeQgZAZZKK",
)


def fetch(url):
    req = Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
        },
    )
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def fetch_json(url, *, headers=None, data=None):
    req = Request(url, headers=headers or {}, data=data)
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_previous_payload():
    if not OUT.exists():
        return None
    m = re.search(
        r"const PAYLOAD = (\{.*?\});\s+let activeRunner",
        OUT.read_text(),
        re.DOTALL,
    )
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def parse_runner(html, runner_id):
    out = {"id": runner_id}
    m = re.search(r"<h2>([^<]+?)\s*<span[^>]*>\s*\(A\d+\)", html)
    out["name"] = m.group(1).strip() if m else "Unknown"
    m = re.search(r"(\d+)\s+parkruns total", html)
    out["totalRuns"] = int(m.group(1)) if m else 0
    m = re.search(r"(\d+)\s+parkruns at\s+([^<]+?)</h4>", html)
    out["homeRuns"] = int(m.group(1)) if m else 0
    out["homeEvent"] = m.group(2).strip() if m else ""
    m = re.search(r"Most recent age category was\s+([^<\s]+)", html)
    out["ageCat"] = m.group(1) if m else ""
    out["club100"] = "parkrun 100 Club" in html
    out["club250"] = "parkrun 250 Club" in html
    out["club500"] = "parkrun 500 Club" in html

    rows = re.findall(
        r'format-date">(\d{2}/\d{2}/\d{4})</span></a></td>'
        r'<td><a[^>]*>(\d+)</a></td>'
        r'<td>(\d+)</td>'
        r'<td>([\d:]+)</td>'
        r'<td>([\d.]+)%</td>'
        r'<td>(.*?)</td>',
        html, re.DOTALL,
    )
    results = []
    for d, runnum, pos, t, ag, pb in rows:
        results.append({
            "date": d,
            "run": int(runnum),
            "pos": int(pos),
            "time": t,
            "ageGrade": float(ag),
            "pb": "PB" in pb,
        })
    out["results"] = results
    return out


def slugify(value):
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def truthy(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def api_date(value):
    raw = str(value).replace("Z", "+00:00")
    if "T" not in raw:
        return datetime.strptime(raw[:10], "%Y-%m-%d").date()
    return datetime.fromisoformat(raw).date()


def api_date_display(value):
    return api_date(value).strftime("%d/%m/%Y")


def api_credentials():
    username = os.environ.get("PARKRUN_USERNAME") or os.environ.get("PARKRUN_ID")
    password = os.environ.get("PARKRUN_PASSWORD")
    if not username or not password:
        return None
    return username, password


def api_headers(access_token=None):
    headers = {
        "User-Agent": APP_UA,
        "Accept": "application/json",
        "X-Powered-By": "parkrun-bates",
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def api_auth(username, password):
    basic = base64.b64encode(f"{API_CLIENT_ID}:{API_CLIENT_SECRET}".encode()).decode()
    data = urlencode({
        "username": username,
        "password": password,
        "scope": "app",
        "grant_type": "password",
    }).encode()
    payload = fetch_json(
        f"{API_BASE}/user_auth.php",
        data=data,
        headers={
            **api_headers(),
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    return payload["access_token"]


def api_get(path, access_token, params=None):
    all_params = {
        "expandedDetails": "true",
        "access_token": access_token,
        "scope": "app",
    }
    all_params.update(params or {})
    return fetch_json(
        f"{API_BASE}{path}?{urlencode(all_params)}",
        headers=api_headers(access_token),
    )


def api_get_results(access_token, athlete_id):
    out = []
    offset = 0
    while True:
        payload = api_get(
            "/v1/results",
            access_token,
            {"athleteId": athlete_id, "offset": offset, "limit": 100},
        )
        data = payload.get("data", {}).get("Results", [])
        out.extend(data)

        range_data = payload.get("Content-Range", {}).get("ResultsRange", [])
        max_items = None
        if range_data:
            max_items = int(range_data[0].get("max") or 0)
        if not data or not max_items or len(out) >= max_items:
            return out
        offset += len(data)


def runner_from_api(raw_results, runner_config, previous_runner=None):
    event_slug = slugify(CONFIG["event"])
    adult_runs = [
        res for res in raw_results
        if str(res.get("SeriesID", "1")) == "1"
    ]
    adult_runs.sort(key=lambda res: api_date(res["EventDate"]), reverse=True)

    event_runs = [
        res for res in adult_runs
        if event_slug in {
            slugify(str(res.get("EventLongName", ""))),
            slugify(str(res.get("EventShortName", ""))),
            slugify(str(res.get("EventName", ""))),
        }
    ]
    if not event_runs:
        raise ValueError(f"No {CONFIG['event']} results found for A{runner_config['id']}")

    latest = adult_runs[0] if adult_runs else event_runs[0]
    event_latest = event_runs[0]
    first_name = str(latest.get("FirstName", "")).strip().title()
    last_name = str(latest.get("LastName", "")).strip()
    total_runs = int(latest.get("RunTotal") or len(adult_runs))
    home_event = event_latest.get("EventLongName") or previous_runner.get("homeEvent", "") if previous_runner else event_latest.get("EventLongName", "")

    return {
        "id": runner_config["id"],
        "name": f"{first_name} {last_name}".strip() or runner_config["name"],
        "totalRuns": total_runs,
        "homeRuns": len(event_runs),
        "homeEvent": home_event,
        "ageCat": latest.get("AgeCategory", ""),
        "club100": total_runs >= 100,
        "club250": total_runs >= 250,
        "club500": total_runs >= 500,
        "results": [
            {
                "date": api_date_display(res["EventDate"]),
                "run": int(res.get("EventNumber") or 0),
                "pos": int(res.get("FinishPosition") or 0),
                "time": res.get("RunTime", ""),
                "ageGrade": float(res.get("AgeGrading") or 0),
                "pb": truthy(res.get("WasPbRun")) or truthy(res.get("GenuinePB")),
            }
            for res in event_runs
        ],
        "short": runner_config["short"],
    }


def fetch_api_runners(previous_runners):
    creds = api_credentials()
    if not creds:
        print("PARKRUN_USERNAME/PARKRUN_PASSWORD not set; skipping app API.", file=sys.stderr)
        return []

    print("Fetching parkrun app API token", file=sys.stderr)
    access_token = api_auth(*creds)
    runners = []
    for r in CONFIG["runners"]:
        print(f"Fetching {r['name']} via app API", file=sys.stderr)
        raw_results = api_get_results(access_token, r["id"])
        runners.append(runner_from_api(raw_results, r, previous_runners.get(str(r["id"]))))
    return runners


def to_iso(d):
    dd, mm, yy = d.split("/")
    return f"{yy}-{mm}-{dd}"


def fetch_weather(lat, lon, start, end):
    url = (
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={start}&end_date={end}"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max"
        "&timezone=Europe%2FLondon"
    )
    data = json.loads(fetch(url))["daily"]
    out = {}
    for i, d in enumerate(data["time"]):
        out[d] = {
            "tmax": data["temperature_2m_max"][i],
            "tmin": data["temperature_2m_min"][i],
            "rain": data["precipitation_sum"][i],
            "wind": data["wind_speed_10m_max"][i],
        }
    return out


def main():
    runners = []
    all_iso_dates = []
    live_data = False
    previous = load_previous_payload()
    previous_runners = {}
    if previous:
        previous_runners = {
            str(runner["id"]): runner
            for runner in previous.get("runners", [])
            if "id" in runner
        }

    try:
        runners = fetch_api_runners(previous_runners)
        live_data = bool(runners)
    except (HTTPError, URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError) as e:
        print(f"App API failed: {e}", file=sys.stderr)
        runners = []

    if not runners:
        for r in CONFIG["runners"]:
            url = f"https://www.parkrun.org.uk/{CONFIG['event']}/parkrunner/{r['id']}/"
            print(f"Fetching {r['name']}: {url}", file=sys.stderr)
            try:
                html = fetch(url)
            except (HTTPError, URLError, TimeoutError) as e:
                print(f"  ERROR: {e}", file=sys.stderr)
                cached = previous_runners.get(str(r["id"]))
                if not cached:
                    continue
                print(f"  Using cached data for {r['name']}", file=sys.stderr)
                cached["short"] = r["short"]
                runners.append(cached)
                continue
            parsed = parse_runner(html, r["id"])
            parsed["short"] = r["short"]
            runners.append(parsed)
            live_data = True
            time.sleep(2)  # be polite

    if not runners:
        print("No runners scraped and no cached dashboard data — aborting.", file=sys.stderr)
        sys.exit(1)

    if not live_data:
        print("No live parkrun data scraped; keeping existing dashboard.", file=sys.stderr)
        return

    for runner in runners:
        all_iso_dates.extend(to_iso(res["date"]) for res in runner["results"])
    all_iso_dates.sort()
    weather_start = all_iso_dates[0]
    weather_end = all_iso_dates[-1]
    print(f"Fetching weather {weather_start} → {weather_end}", file=sys.stderr)
    weather = fetch_weather(
        CONFIG["event_coords"]["lat"],
        CONFIG["event_coords"]["lon"],
        weather_start, weather_end,
    )

    for runner in runners:
        for res in runner["results"]:
            res["weather"] = weather.get(to_iso(res["date"]))

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "event": CONFIG["event"],
        "runners": runners,
    }
    html = TEMPLATE.replace("__DATA__", json.dumps(payload))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html)
    print(f"Wrote {OUT} ({len(html):,} bytes)", file=sys.stderr)


if __name__ == "__main__":
    main()
