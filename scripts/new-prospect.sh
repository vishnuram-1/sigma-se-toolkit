#!/usr/bin/env bash
#
# new-prospect.sh — scaffold a prospect folder in the standard layout.
#
# Usage:
#   scripts/new-prospect.sh "Acme Corp"
#   scripts/new-prospect.sh "Acme Corp" --with-usecases   # also add use-cases/
#
# Creates prospects/prospect_<Name>/ with the conventional subfolders and a
# stub scoping.md. Safe to re-run: existing files are never overwritten.
#
# Note: context_<Name>.txt is populated by sync_gong_calls.py, not here — but
# only if the account/rep matches the "VR Gong Calls" workbook filter. Drop any
# hand-collected transcripts under reference/ (never edit context_<Name>.txt).

set -euo pipefail

if [[ $# -lt 1 || -z "${1:-}" ]]; then
  echo "Usage: $0 \"Prospect Name\" [--with-usecases]" >&2
  exit 1
fi

RAW_NAME="$1"
WITH_USECASES="${2:-}"

# Normalize: spaces/punct -> underscores, matching the sync script's convention.
SLUG=$(echo "$RAW_NAME" | sed -E 's/[^A-Za-z0-9]+/_/g; s/^_+//; s/_+$//')
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="$SCRIPT_DIR/../prospects/prospect_${SLUG}"

mkdir -p "$DEST"/{data-models,workbooks,mockups,reference}
[[ "$WITH_USECASES" == "--with-usecases" ]] && mkdir -p "$DEST/use-cases"

SCOPING="$DEST/scoping.md"
if [[ ! -f "$SCOPING" ]]; then
  cat > "$SCOPING" <<EOF
# ${RAW_NAME} — Scoping

## Account
- Company:
- Industry:
- Sigma org / cloud:

## Use case(s)

## Data sources / warehouse

## Success criteria

## Timeline & stakeholders
EOF
  echo "created scoping stub: $SCOPING"
fi

echo "Scaffolded: prospects/prospect_${SLUG}/"
ls -1 "$DEST"
