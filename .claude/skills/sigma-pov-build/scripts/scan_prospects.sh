#!/usr/bin/env bash
# Lists prospect folders that are ready for the POV workflow.
# A prospect is "ready" if it has both a scoping artifact (.docx or .md)
# AND a non-empty Gong context_*.txt.
#
# Usage: scan_prospects.sh [path-to-prospects-dir]

set -euo pipefail

# Resolve the repo root from this script's own location, so the default works
# wherever the toolkit is cloned. Precedence: explicit argument, then
# CLAUDE_PROJECT_DIR, then the repo this script lives in.
# Path here is .claude/skills/sigma-pov-build/scripts/ -> up 4 = repo root.
_repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
PROSPECTS_DIR="${1:-${CLAUDE_PROJECT_DIR:-$_repo_root}/prospects}"

if [[ ! -d "$PROSPECTS_DIR" ]]; then
  echo "error: prospects dir not found: $PROSPECTS_DIR" >&2
  exit 1
fi

printf "%-50s %-10s %-10s %-10s\n" "PROSPECT" "DOCX" "MD" "CONTEXT"
printf "%-50s %-10s %-10s %-10s\n" "--------" "----" "--" "-------"

for dir in "$PROSPECTS_DIR"/prospect_*/; do
  [[ -d "$dir" ]] || continue
  name=$(basename "$dir" | sed 's/^prospect_//')

  docx_status="-"
  md_status="-"
  context_status="-"

  [[ -f "$dir/scoping.docx" ]] && docx_status="yes"
  [[ -f "$dir/scoping.md" ]] && md_status="yes"

  context_file=$(ls "$dir"/context_*.txt 2>/dev/null | head -1 || true)
  if [[ -n "$context_file" && -s "$context_file" ]]; then
    size=$(wc -l <"$context_file" | tr -d ' ')
    context_status="${size}L"
  fi

  # Only print rows that have at least one signal of being worked
  if [[ "$docx_status" == "yes" || "$md_status" == "yes" || "$context_status" != "-" ]]; then
    printf "%-50s %-10s %-10s %-10s\n" "$name" "$docx_status" "$md_status" "$context_status"
  fi
done

echo ""
echo "Ready for build = (DOCX or MD) AND CONTEXT present."
