#!/usr/bin/env python3
"""Load the built dashboard in headless Chrome and fail if it doesn't render.

publish.sh runs this before every push, so a broken page never reaches the
live site. The page tests itself when opened with ?smoke (see the bottom of
template.html): it renders every runner, head-to-head and every wrapped
year, then writes a JSON report into <pre id="smoke">. No report at all means
the script died at load, which is a failure too.

    python3 scripts/smoke_test.py [path/to/index.html]

Exits 0 on pass, 1 on fail. Set CHROME to use a different browser binary.
"""
import html
import json
import os
import re
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def fail(msg):
    print(f"SMOKE TEST FAILED: {msg}")
    sys.exit(1)


def dump_dom(url, limit=120):
    """Headless Chrome's rendered DOM for url.

    Chrome prints the DOM but on some setups never exits afterwards, so read
    the output as it streams and stop it as soon as the document is complete,
    rather than waiting on the process.
    """
    profile = tempfile.mkdtemp(prefix="parkrun-smoke-")   # never touch the real Chrome profile
    proc = subprocess.Popen(
        [CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
         f"--user-data-dir={profile}", "--virtual-time-budget=20000", "--dump-dom", url],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True,
    )
    out, deadline = b"", time.monotonic() + limit
    try:
        sel = selectors.DefaultSelector()
        sel.register(proc.stdout, selectors.EVENT_READ)
        while b"</html>" not in out:
            left = deadline - time.monotonic()
            if left <= 0:
                fail(f"Chrome didn't finish rendering the page within {limit}s")
            if not sel.select(timeout=min(left, 1.0)):
                if proc.poll() is not None:
                    break
                continue
            chunk = os.read(proc.stdout.fileno(), 1 << 16)
            if not chunk:
                break
            out += chunk
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)   # Chrome and all its helper processes
        except ProcessLookupError:
            pass
        proc.wait()
        shutil.rmtree(profile, ignore_errors=True)
    return out.decode("utf-8", "replace")


def main():
    page = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "docs" / "index.html").resolve()
    if not page.exists():
        fail(f"{page} doesn't exist")
    if not Path(CHROME).exists():
        fail(f"no Chrome at {CHROME} (set CHROME to another Chromium-based browser)")

    dom = dump_dom(page.as_uri() + "?smoke=1")
    m = re.search(r'<pre id="smoke"[^>]*>(.*?)</pre>', dom, re.DOTALL)
    if not m:
        fail("the page never finished its self-test, so a script probably crashed at load")
    report = json.loads(html.unescape(m.group(1)))
    if report["errors"]:
        fail("\n  " + "\n  ".join(report["errors"]))
    if not report["passed"]:
        fail("the self-test ran no checks")
    print(f"smoke test passed: {len(report['passed'])} checks ({', '.join(report['passed'])})")


if __name__ == "__main__":
    main()
