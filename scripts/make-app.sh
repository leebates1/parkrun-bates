#!/bin/zsh
# Build "Update parkrun dashboard.app" into ~/Applications.
#
# Click it (Dock, Launchpad, Spotlight) and it fetches the latest Widnes
# results, rebuilds the dashboard and pushes it live, then tells you what it
# found. Re-run this script if you ever move the repo.

set -euo pipefail

REPO="${0:A:h:h}"
APP="$HOME/Applications/Update parkrun dashboard.app"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Update parkrun dashboard</string>
  <key>CFBundleDisplayName</key><string>Update parkrun dashboard</string>
  <key>CFBundleIdentifier</key><string>com.leebates.parkrun-updater</string>
  <key>CFBundleExecutable</key><string>updater</string>
  <key>CFBundleIconFile</key><string>appicon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>LSUIElement</key><true/>
</dict>
</plist>
PLIST

cat > "$APP/Contents/MacOS/updater" <<UPDATER
#!/bin/zsh
# Thin wrapper: run the publish script, report the outcome in the UI.
REPO="$REPO"
UPDATER
cat >> "$APP/Contents/MacOS/updater" <<'UPDATER'
LOG="$HOME/Library/Logs/parkrun-dashboard.log"
TITLE="parkrun dashboard"

notify() { osascript -e "display notification \"$1\" with title \"$TITLE\"" >/dev/null 2>&1; }

notify "Fetching the latest results…"

out="$("$REPO/scripts/publish.sh" 2>&1)"
print -r -- "$out" >> "$LOG"

line="$(print -r -- "$out" | grep '^RESULT:' | tail -n 1)"
outcome="${${line#RESULT:}%%|*}"
message="${line#*|}"

case "$outcome" in
  published) body="Published.

$message

leebates1.github.io/parkrun-bates" ; icon=note ;;
  uptodate)  body="Already up to date.

$message" ; icon=note ;;
  nodata)    body="$message" ; icon=caution ;;
  *)         body="Something went wrong.

${message:-No result reported. Check the log.}" ; icon=stop ;;
esac

choice="$(osascript -e "display dialog \"$body\" with title \"$TITLE\" \
  buttons {\"Show log\", \"OK\"} default button \"OK\" with icon $icon" 2>/dev/null)"

if [[ "$choice" == *"Show log"* ]]; then
  open -a Console "$LOG" 2>/dev/null || open -t "$LOG"
fi
UPDATER

chmod +x "$APP/Contents/MacOS/updater"

# Dock icon, reusing the dashboard's own artwork.
SRC="$REPO/docs/icon-1024.png"
if [[ -f "$SRC" ]] && command -v iconutil >/dev/null; then
  SET="$(mktemp -d)/appicon.iconset"
  mkdir -p "$SET"
  for sz in 16 32 128 256 512; do
    sips -z $sz $sz "$SRC" --out "$SET/icon_${sz}x${sz}.png" >/dev/null 2>&1
    sips -z $((sz*2)) $((sz*2)) "$SRC" --out "$SET/icon_${sz}x${sz}@2x.png" >/dev/null 2>&1
  done
  iconutil -c icns "$SET" -o "$APP/Contents/Resources/appicon.icns" 2>/dev/null \
    && print "  icon: built from docs/icon-1024.png"
fi

touch "$APP"
print "Built: $APP"
print "Drag it to your Dock, or find it in Launchpad / Spotlight as \"Update parkrun dashboard\"."
