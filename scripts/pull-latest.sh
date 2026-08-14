#!/usr/bin/env bash
# Pull the nightly Gong sync into this local clone.
#
# Replaces the bare `git pull` the launchd agent used to run. That version
# failed silently and often — 30 fatals in git-pull.log over its lifetime:
#
#   26x  Could not resolve host: github.com
#         launchd fires on wake, before the network is up. One attempt, no
#         retry, dead until tomorrow.
#    9x  Your local changes would be overwritten by merge
#         A plain `git pull` is a merge, and a merge aborts outright on a
#         dirty tree. Once that happened the mirror froze until noticed by
#         hand — which is what "the script doesn't run nightly" actually was.
#    5x  Untracked working tree files would be overwritten by merge
#         A local file sitting where the Action later created a tracked one.
#
# This wrapper: waits for the network, rebases with --autostash so a dirty
# tree is never fatal, moves untracked collisions aside instead of aborting,
# timestamps every line, rotates the log, and raises a desktop notification
# when it genuinely cannot proceed.
#
# Usage: pull-latest.sh [repo-path]     (default: this script's repo)

set -uo pipefail

REPO="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
LOG="$REPO/git-pull.log"
MAX_LOG_BYTES=$((1024 * 1024))   # rotate at 1 MB, keep one previous
NET_RETRIES=6                    # ~2 min of backoff, covers wake-from-sleep
GIT_BIN="$(command -v git || echo /usr/bin/git)"

log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$LOG"; }

notify() {
  # Best-effort desktop notification; never fail the run over it.
  /usr/bin/osascript -e "display notification \"$1\" with title \"Gong sync\"" \
    >/dev/null 2>&1 || true
}

rotate_log() {
  [ -f "$LOG" ] || return 0
  local size
  size=$(wc -c <"$LOG" | tr -d ' ')
  if [ "$size" -gt "$MAX_LOG_BYTES" ]; then
    mv -f "$LOG" "$LOG.1"
    printf '%s  [rotate] previous log moved to %s\n' \
      "$(date '+%Y-%m-%d %H:%M:%S')" "$(basename "$LOG.1")" >"$LOG"
  fi
}

online() {
  # Cheap reachability check. Beats letting git hang for 15 minutes, which
  # it did once: "Failed to connect ... after 913613 ms".
  /sbin/ping -c1 -t3 github.com >/dev/null 2>&1
}

rotate_log

if [ ! -d "$REPO/.git" ]; then
  log "[error] not a git repo: $REPO"
  notify "Not a git repo: $REPO"
  exit 1
fi

log "[start] pull $REPO"

# --- wait for the network ---------------------------------------------------
attempt=1
until online; do
  if [ "$attempt" -ge "$NET_RETRIES" ]; then
    # Offline is the normal case for a laptop at 08:00. Log it, don't nag.
    log "[skip] github.com unreachable after $attempt attempts — will retry tomorrow"
    exit 0
  fi
  wait=$((attempt * 5))
  log "[wait] network not up (attempt $attempt/$NET_RETRIES), sleeping ${wait}s"
  sleep "$wait"
  attempt=$((attempt + 1))
done

BEFORE="$($GIT_BIN -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo unknown)"

# --- fetch ------------------------------------------------------------------
if ! fetch_out=$($GIT_BIN -C "$REPO" fetch --prune origin 2>&1); then
  log "[error] fetch failed: $fetch_out"
  notify "Gong sync fetch failed — see git-pull.log"
  exit 1
fi

BRANCH="$($GIT_BIN -C "$REPO" rev-parse --abbrev-ref HEAD)"
BEHIND="$($GIT_BIN -C "$REPO" rev-list --count "HEAD..origin/$BRANCH" 2>/dev/null || echo 0)"

if [ "$BEHIND" = "0" ]; then
  log "[ok] already up to date at $BEFORE"
  exit 0
fi

log "[info] $BEHIND commit(s) behind origin/$BRANCH"

# --- move untracked collisions aside ----------------------------------------
# An untracked local file where an incoming commit adds a tracked one aborts
# the rebase. Park it rather than lose it or block the pull.
collisions=$($GIT_BIN -C "$REPO" diff --name-only --diff-filter=A \
  "HEAD..origin/$BRANCH" 2>/dev/null | while IFS= read -r f; do
    if [ -e "$REPO/$f" ] && ! $GIT_BIN -C "$REPO" ls-files --error-unmatch "$f" >/dev/null 2>&1; then
      echo "$f"
    fi
  done)

if [ -n "$collisions" ]; then
  stamp=$(date '+%Y%m%d-%H%M%S')
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    mv -f "$REPO/$f" "$REPO/$f.local-$stamp"
    log "[moved] untracked collision: $f -> $f.local-$stamp"
  done <<<"$collisions"
  notify "Moved $(echo "$collisions" | grep -c .) colliding file(s) aside; see git-pull.log"
fi

# --- rebase with autostash --------------------------------------------------
# --autostash is the fix for the 9 "local changes would be overwritten"
# aborts: local edits are stashed, the rebase applies, the stash comes back.
if pull_out=$($GIT_BIN -C "$REPO" pull --rebase --autostash origin "$BRANCH" 2>&1); then
  AFTER="$($GIT_BIN -C "$REPO" rev-parse --short HEAD)"
  log "[ok] $BEFORE -> $AFTER ($BEHIND commit(s))"
  echo "$pull_out" | sed 's/^/    /' >>"$LOG"
  exit 0
fi

# --- failure ----------------------------------------------------------------
log "[error] rebase failed:"
echo "$pull_out" | sed 's/^/    /' >>"$LOG"

if $GIT_BIN -C "$REPO" rebase --abort >/dev/null 2>&1; then
  log "[recover] rebase aborted; tree restored to $BEFORE"
  notify "Gong sync pull conflicted — repo left clean at $BEFORE. See git-pull.log"
else
  notify "Gong sync pull FAILED and needs manual attention. See git-pull.log"
fi
exit 1
