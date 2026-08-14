#!/usr/bin/env bash
# Install (or reinstall) the launchd agent that pulls the nightly Gong sync
# into this local clone.
#
# The agent previously existed only on one laptop, hand-made, undocumented,
# running a bare `git pull`. This script makes it reproducible for any SE.
#
# Usage:
#   scripts/install-local-sync.sh              # install, runs daily at 08:00
#   scripts/install-local-sync.sh --at 09:30   # different time
#   scripts/install-local-sync.sh --uninstall

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.sigma-se.gong-context-pull"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
HOUR=8
MINUTE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --at)
      [ $# -ge 2 ] || { echo "error: --at needs HH:MM" >&2; exit 1; }
      HOUR="${2%%:*}"; MINUTE="${2##*:}"
      HOUR=$((10#$HOUR)); MINUTE=$((10#$MINUTE))
      shift 2 ;;
    --uninstall)
      if [ -f "$PLIST" ]; then
        launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
        rm -f "$PLIST"
        echo "uninstalled $LABEL"
      else
        echo "not installed"
      fi
      exit 0 ;;
    *) echo "error: unknown argument: $1" >&2; exit 1 ;;
  esac
done

[ -x "$REPO/scripts/pull-latest.sh" ] || chmod +x "$REPO/scripts/pull-latest.sh"

mkdir -p "$HOME/Library/LaunchAgents"
cat >"$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$REPO/scripts/pull-latest.sh</string>
        <string>$REPO</string>
    </array>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>$HOUR</integer>
        <key>Minute</key>
        <integer>$MINUTE</integer>
    </dict>

    <!-- The wrapper logs with timestamps itself; these catch anything that
         escapes it (e.g. a bash syntax error before logging starts). -->
    <key>StandardOutPath</key>
    <string>$REPO/git-pull.log</string>
    <key>StandardErrorPath</key>
    <string>$REPO/git-pull.log</string>

    <!-- launchd's default PATH is /usr/bin:/bin:/usr/sbin:/sbin, which has no
         Homebrew git. The wrapper resolves git itself, but set this so any
         future addition to the script behaves like an interactive shell. -->
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>

    <!-- Run on load so a fresh install proves itself immediately, and catch
         up after the machine was asleep at the scheduled time. -->
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
PLIST_EOF

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

printf 'installed %s\n' "$LABEL"
printf '  repo     %s\n' "$REPO"
printf '  schedule %02d:%02d daily (and once now, via RunAtLoad)\n' "$HOUR" "$MINUTE"
printf '  log      %s/git-pull.log\n' "$REPO"
printf '\nVerify:  launchctl print gui/%s/%s | grep -E "state|last exit"\n' "$(id -u)" "$LABEL"
