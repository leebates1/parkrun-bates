#!/bin/zsh
# Rebuild the dashboard from the live parkrun results and publish it.
#
# parkrun blocks GitHub Actions runner IPs (403 on the app API, 405 on the
# website), so the scheduled workflow reports success while publishing
# nothing. Run this from the Mac instead, where parkrun answers normally.
#
# Usually launched by the "Update parkrun dashboard" app (see make-app.sh),
# but fine to run directly. Does nothing if the results haven't changed.
#
# Final line is always  RESULT:<status>|<message>  for the app to read.

set -uo pipefail

REPO="${0:A:h:h}"
cd "$REPO" || exit 1

PY="$REPO/.venv/bin/python"
[[ -x "$PY" ]] || PY="$(command -v python3)"

log()    { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
result() { print -r -- "RESULT:$1|$2"; exit "${3:-0}"; }
die()    { log "ABORT: $*"; result error "$*" 1; }

# True when the freshly built page differs from the published one in more than
# its generatedAt timestamp.
results_changed() {
  "$PY" - "$REPO/docs/index.html" <<'PYEOF'
import json, re, subprocess, sys

def runners(html):
    m = re.search(r"const PAYLOAD = (\{.*?\});\s+let activeRunner", html, re.DOTALL)
    if not m:
        return None
    return json.loads(m.group(1)).get("runners")

new = runners(open(sys.argv[1]).read())
try:
    old = runners(subprocess.run(["git", "show", "HEAD:docs/index.html"],
                                 capture_output=True, text=True, check=True).stdout)
except subprocess.CalledProcessError:
    old = None
# exit 0 (true) when something meaningful changed
sys.exit(0 if new is None or old is None or new != old else 1)
PYEOF
}

# Everyone's most recent run, read back out of the page we just built.
latest_summary() {
  "$PY" - "$REPO/docs/index.html" <<'PYEOF' 2>/dev/null || print "dashboard updated"
import json, re, sys
html = open(sys.argv[1]).read()
m = re.search(r"const PAYLOAD = (\{.*?\});\s+let activeRunner", html, re.DOTALL)
p = json.loads(m.group(1))
runs = [(r["short"], r["results"][0]) for r in p["runners"] if r.get("results")]
newest = max(r[1]["date"] for r in runs)
same = [(s, x) for s, x in runs if x["date"] == newest]
who = " · ".join(f"{s} {x['time']}" for s, x in same)
print(f"{who}  —  #{same[0][1]['run']}, {newest}")
PYEOF
}

log "=== publish start ==="

command -v git >/dev/null || die "git not found"
[[ -x "$PY" ]] || die "no python available"

branch="$(git rev-parse --abbrev-ref HEAD)"
[[ "$branch" == "main" ]] || die "on branch '$branch', not main"

# Never publish over work in progress.
if ! git diff --quiet || ! git diff --staged --quiet; then
  die "you have uncommitted changes — commit or stash them first"
fi

git pull --ff-only --quiet origin main 2>&1 | sed 's/^/    /' \
  || log "note: could not fast-forward from origin (offline, or diverged)"

out="$("$PY" scripts/build.py 2>&1)"; rc=$?
print -r -- "$out" | sed 's/^/    /'
[[ $rc -eq 0 ]] || die "the build failed — see the log"

if print -r -- "$out" | grep -q 'keeping existing dashboard'; then
  log "parkrun returned no usable data"
  result nodata "parkrun didn't return any results. Try again in a bit."
fi

# Every build stamps a fresh generatedAt, so the file always looks modified.
# Only publish when the actual results changed.
if git diff --quiet -- docs/index.html || ! results_changed; then
  git checkout -- docs/index.html 2>/dev/null
  log "no new results"
  result uptodate "$(latest_summary)"
fi

git add docs/index.html
git commit -q -m "chore: weekly dashboard update" || die "commit failed"
git push --quiet origin main 2>&1 | sed 's/^/    /' \
  || die "push failed — the commit is saved locally, push it when you're back online"

log "published $(git rev-parse --short HEAD)"
log "=== publish done ==="
result published "$(latest_summary)"
