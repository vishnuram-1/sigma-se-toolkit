#!/usr/bin/env bash
# Lists prospect folders that are ready for the POV workflow.
# A prospect is "ready" when it has a scoping.md AND a non-empty Gong
# context_*.txt. scoping.md is written by the sigma-scoping skill; there is no
# .docx step in the flow.
#
# ARTIFACTS counts hand-built work in the folder (data-models/, workbooks/,
# mockups/, reference/) — a prospect with artifacts but no scoping.md usually
# means scoping was skipped, which is worth seeing.
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

printf "%-44s %-10s %-10s %-10s\n" "PROSPECT" "SCOPING" "CONTEXT" "ARTIFACTS"
printf "%-44s %-10s %-10s %-10s\n" "--------" "-------" "-------" "---------"

for dir in "$PROSPECTS_DIR"/prospect_*/; do
  [[ -d "$dir" ]] || continue
  name=$(basename "$dir" | sed 's/^prospect_//')

  md_status="-"
  context_status="-"
  artifact_status="-"

  [[ -f "$dir/scoping.md" ]] && md_status="yes"

  # Count files in any subdirectory — data-models/, workbooks/, mockups/,
  # reference/, plugins/, LookML/, whatever the prospect actually supplied.
  # A fixed subfolder list would miss customer-shaped ones.
  artifacts=$(find "$dir" -mindepth 2 -type f -not -name ".*" 2>/dev/null | wc -l | tr -d ' ')
  [[ "$artifacts" -gt 0 ]] && artifact_status="${artifacts}f"

  context_file=$(ls "$dir"/context_*.txt 2>/dev/null | head -1 || true)
  if [[ -n "$context_file" && -s "$context_file" ]]; then
    size=$(wc -l <"$context_file" | tr -d ' ')
    context_status="${size}L"
  fi

  # Only print rows with at least one signal of being worked
  if [[ "$md_status" == "yes" || "$context_status" != "-" || "$artifact_status" != "-" ]]; then
    printf "%-44s %-10s %-10s %-10s\n" "$name" "$md_status" "$context_status" "$artifact_status"
  fi
done

echo ""
echo "Ready for build = SCOPING and CONTEXT present. No scoping.md? Run sigma-scoping."
