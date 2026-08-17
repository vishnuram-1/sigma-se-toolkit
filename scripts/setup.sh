#!/usr/bin/env bash
# One-command setup for a fresh copy of the SE toolkit.
#
# Replaces a five-step manual checklist spread across three surfaces (edit a
# file, add repo secrets in the GitHub UI, run a backfill, install a launchd
# agent). Every step is optional and re-runnable; nothing here is destructive.
#
# Usage: scripts/setup.sh

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || { echo "error: cannot cd to $REPO" >&2; exit 1; }

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
warn() { printf '  ! %s\n' "$*"; }
ok()   { printf '  + %s\n' "$*"; }
step() { printf '\n'; bold "$*"; }

ask() {  # ask <prompt> <default> -> echoes answer
  local prompt="$1" default="${2:-}" reply
  if [ -n "$default" ]; then
    read -r -p "  $prompt [$default]: " reply </dev/tty
    echo "${reply:-$default}"
  else
    read -r -p "  $prompt: " reply </dev/tty
    echo "$reply"
  fi
}

yes_no() {  # yes_no <prompt> -> 0 if yes
  local reply
  read -r -p "  $1 [y/N]: " reply </dev/tty
  [[ "$reply" =~ ^[Yy] ]]
}

bold "Sigma SE toolkit — setup"
echo "Every step is optional. Ctrl-C any time; re-run to pick up where you left off."

# --- 1. prerequisites -------------------------------------------------------
step "1. Prerequisites"
missing=0
for cmd in python3 git curl; do
  if command -v "$cmd" >/dev/null 2>&1; then ok "$cmd"; else warn "$cmd NOT FOUND"; missing=1; fi
done
python3 - <<'PY' || missing=1
import sys
v = sys.version_info
print(f"  {'+' if v >= (3, 10) else '!'} python {v.major}.{v.minor} "
      f"({'ok' if v >= (3,10) else 'NEEDS 3.10+ — the script uses X | None syntax'})")
sys.exit(0 if v >= (3, 10) else 1)
PY
if command -v gh >/dev/null 2>&1; then ok "gh (GitHub CLI) — can configure Actions for you"
else warn "gh not found — you'll set repo secrets by hand in the GitHub UI"; fi
[ "$missing" = "1" ] && { echo; warn "Install the missing prerequisites, then re-run."; exit 1; }

python3 -c "import requests, dateutil" 2>/dev/null \
  && ok "python deps installed" \
  || { warn "installing python deps"; python3 -m pip install -q -r requirements.txt && ok "done"; }

# --- 2. repo visibility -----------------------------------------------------
step "2. Repository visibility"
echo "  This repo will accumulate verbatim customer call transcripts."
if command -v gh >/dev/null 2>&1 && vis=$(gh repo view --json visibility -q .visibility 2>/dev/null); then
  if [ "$vis" = "PUBLIC" ]; then
    warn "This repo is PUBLIC. Transcripts must not go in a public repo."
    warn "Fix: gh repo edit --visibility private"
    yes_no "Continue anyway?" || exit 1
  else
    ok "visibility: $vis"
  fi
else
  warn "Could not determine visibility — confirm it is Private before the first sync."
fi
echo "  Note: transcripts persist in git history. The 90-day prune is hygiene, not retention."

# --- 3. Sigma credentials ---------------------------------------------------
step "3. Sigma API credentials"
echo "  Sigma -> Administration -> Developer Access -> Create new."
echo "  SIGMA_BASE_URL is the API host, not the app URL."
echo "    AWS US West  https://aws-api.sigmacomputing.com"
echo "    AWS US East  https://api.us-a.aws.sigmacomputing.com"
echo "    GCP US       https://api.sigmacomputing.com"
echo "    Azure US     https://api.us.azure.sigmacomputing.com"
echo "  Full list: https://help.sigmacomputing.com/docs/region-warehouse-and-feature-support"
echo

BASE_URL=$(ask "SIGMA_BASE_URL" "https://aws-api.sigmacomputing.com")
CLIENT_ID=$(ask "SIGMA_CLIENT_ID")
read -r -s -p "  SIGMA_CLIENT_SECRET (not echoed): " CLIENT_SECRET </dev/tty; echo

if [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ]; then
  warn "Skipping credential verification (nothing entered)."
else
  printf '  verifying ... '
  WHOAMI=$(SIGMA_BASE_URL="$BASE_URL" SIGMA_CLIENT_ID="$CLIENT_ID" SIGMA_CLIENT_SECRET="$CLIENT_SECRET" \
    python3 - <<'PY'
import os, sys, json, urllib.request, urllib.parse
base = os.environ["SIGMA_BASE_URL"].rstrip("/")
try:
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": os.environ["SIGMA_CLIENT_ID"],
        "client_secret": os.environ["SIGMA_CLIENT_SECRET"],
    }).encode()
    with urllib.request.urlopen(base + "/v2/auth/token", data, timeout=30) as r:
        token = json.load(r)["access_token"]
    req = urllib.request.Request(base + "/v2/whoami",
                                 headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=30) as r:
        me = json.load(r)
    print(f"OK  {me.get('email', me.get('userId','?'))}")
except Exception as exc:
    print(f"FAILED  {exc}", file=sys.stderr); sys.exit(1)
PY
  ) && ok "$WHOAMI" || { warn "Token exchange failed — check the base URL and credentials."; }
fi

# --- 4. rep filter ----------------------------------------------------------
step "4. Which reps' calls do you want?"
if [ -f config/me.py ]; then
  ok "config/me.py already exists — leaving it alone"
  grep -E '^REPS' config/me.py | head -1 | sed 's/^/  /'
elif [ -n "${CLIENT_ID:-}" ] && [ -n "${CLIENT_SECRET:-}" ]; then
  echo "  Fetching the rep names the workbook exposes ..."
  if SIGMA_BASE_URL="$BASE_URL" SIGMA_CLIENT_ID="$CLIENT_ID" SIGMA_CLIENT_SECRET="$CLIENT_SECRET" \
     python3 scripts/sync_gong_calls.py --list-reps; then
    REPS=$(ask "Your reps, comma-separated, no space after the comma (blank = all)")
    cp config/me.example.py config/me.py
    python3 - "$REPS" <<'PY'
import re, sys, pathlib
p = pathlib.Path("config/me.py")
p.write_text(re.sub(r'^REPS = ""', f'REPS = "{sys.argv[1]}"', p.read_text(), flags=re.M))
PY
    ok "wrote config/me.py (gitignored)"
  else
    warn "Could not list reps — the workbook may not be shared with you yet."
    warn "Ask the toolkit owner for read access, then re-run this script."
  fi
else
  cp config/me.example.py config/me.py
  ok "wrote config/me.py from the example — edit REPS when you have access"
fi

# --- 5. GitHub Actions ------------------------------------------------------
step "5. Nightly GitHub Action"
if command -v gh >/dev/null 2>&1 && [ -n "${CLIENT_ID:-}" ]; then
  if yes_no "Set the repo secrets + REPS variable via gh?"; then
    gh secret set SIGMA_BASE_URL     --body "$BASE_URL"      >/dev/null && ok "secret SIGMA_BASE_URL"
    gh secret set SIGMA_CLIENT_ID    --body "$CLIENT_ID"     >/dev/null && ok "secret SIGMA_CLIENT_ID"
    gh secret set SIGMA_CLIENT_SECRET --body "$CLIENT_SECRET" >/dev/null && ok "secret SIGMA_CLIENT_SECRET"
    CURRENT_REPS=$(grep -E '^REPS = ' config/me.py 2>/dev/null | sed 's/^REPS = "//; s/"$//')
    gh variable set REPS --body "${CURRENT_REPS:-}" >/dev/null && ok "variable REPS=${CURRENT_REPS:-<empty>}"
  fi
else
  echo "  Add these by hand: Settings -> Secrets and variables -> Actions"
  echo "    Secrets:   SIGMA_BASE_URL, SIGMA_CLIENT_ID, SIGMA_CLIENT_SECRET"
  echo "    Variables: REPS"
fi

# --- 6. backfill ------------------------------------------------------------
step "6. Backfill"
CONFIGURED_REPS=$(grep -E '^REPS = ' config/me.py 2>/dev/null | sed 's/^REPS = "//; s/"$//')
if [ -z "${CLIENT_ID:-}" ]; then
  warn "Skipping — no credentials entered."
elif [ -z "$CONFIGURED_REPS" ]; then
  # Don't let setup trip the unfiltered guard and surface a confusing exit 2.
  warn "Skipping — no reps set yet, and an unfiltered sync would pull every"
  warn "rep's calls. Set REPS in config/me.py, then:"
  warn "  python3 scripts/sync_gong_calls.py --since 90 --dry-run"
elif yes_no "Run a 90-day backfill now (dry-run first)?"; then
  SIGMA_BASE_URL="$BASE_URL" SIGMA_CLIENT_ID="$CLIENT_ID" SIGMA_CLIENT_SECRET="$CLIENT_SECRET" \
    python3 scripts/sync_gong_calls.py --since 90 --dry-run
  if yes_no "Looks right — run it for real?"; then
    SIGMA_BASE_URL="$BASE_URL" SIGMA_CLIENT_ID="$CLIENT_ID" SIGMA_CLIENT_SECRET="$CLIENT_SECRET" \
      python3 scripts/sync_gong_calls.py --since 90
  fi
fi

# --- 7. local mirror --------------------------------------------------------
step "7. Keep this clone fresh (macOS only)"
if [ "$(uname -s)" = "Darwin" ]; then
  echo "  The Action commits to GitHub; this pulls it down to your laptop so"
  echo "  Claude can read the transcripts locally."
  yes_no "Install the daily pull agent?" && ./scripts/install-local-sync.sh
else
  warn "Not macOS — the launchd agent doesn't apply."
  warn "Use cron instead:  0 8 * * *  $REPO/scripts/pull-latest.sh $REPO"
fi

step "Done"
echo "  Next: install the Claude skills."
echo "    scripts/install-skills.sh"
echo
echo "  That symlinks this repo's skills into ~/.claude/skills/ so they load from"
echo "  any directory, and clones the three upstream-maintained ones"
echo "  (sigma-api, sigma-data-models, sigma-workbook-conventions) which are"
echo "  deliberately not vendored here."
echo
echo "  Useful later:"
echo "    python scripts/sync_gong_calls.py --list-reps   re-check rep names"
echo "    cat prospects/.sync-status                      proof the last run happened"
echo "    tail -20 git-pull.log                           local mirror activity"
