#!/usr/bin/env python3
"""Scrape parkrun results for each configured runner, fetch historical weather
from Open-Meteo, and render a self-contained HTML dashboard into docs/index.html."""
import json
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "scripts" / "runners.json").read_text())
TEMPLATE = (ROOT / "scripts" / "template.html").read_text()
OUT = ROOT / "docs" / "index.html"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def fetch(url):
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


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

    for r in CONFIG["runners"]:
        url = f"https://www.parkrun.org.uk/{CONFIG['event']}/parkrunner/{r['id']}/"
        print(f"Fetching {r['name']}: {url}", file=sys.stderr)
        try:
            html = fetch(url)
        except HTTPError as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            continue
        parsed = parse_runner(html, r["id"])
        parsed["short"] = r["short"]
        runners.append(parsed)
        all_iso_dates.extend(to_iso(res["date"]) for res in parsed["results"])
        time.sleep(2)  # be polite

    if not runners:
        print("No runners scraped — aborting.", file=sys.stderr)
        sys.exit(1)

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
