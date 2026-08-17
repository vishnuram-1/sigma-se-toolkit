#!/usr/bin/env bash
# Idempotent .docx -> .md converter.
# Prefers pandoc if installed; falls back to textutil (macOS built-in).
#
# Usage: convert_docx.sh <path-to-docx> [output.md]
#   Default output: same basename, .md extension, same directory.
#
# Behavior: if the output .md already exists AND is newer than the .docx,
# the conversion is skipped. The wrapper exits 0 either way.

set -euo pipefail

INPUT="${1:-}"
if [[ -z "$INPUT" ]]; then
  echo "usage: convert_docx.sh <path-to-docx> [output.md]" >&2
  exit 1
fi

if [[ ! -f "$INPUT" ]]; then
  echo "error: input file not found: $INPUT" >&2
  exit 1
fi

case "$INPUT" in
  *.docx) ;;
  *)
    echo "error: input must be a .docx file: $INPUT" >&2
    exit 1
    ;;
esac

OUTPUT="${2:-${INPUT%.docx}.md}"

# Idempotency check
if [[ -f "$OUTPUT" && "$OUTPUT" -nt "$INPUT" ]]; then
  echo "[skip] $OUTPUT is newer than $INPUT"
  exit 0
fi

if command -v pandoc >/dev/null 2>&1; then
  echo "[pandoc] $INPUT -> $OUTPUT"
  pandoc "$INPUT" -o "$OUTPUT" --wrap=preserve
elif command -v textutil >/dev/null 2>&1; then
  # textutil produces text-only (or HTML if we ask). Plain txt is closer to MD
  # than HTML for our purposes; we accept lossy table conversion.
  echo "[textutil] $INPUT -> $OUTPUT (lossy on tables)"
  TMP_TXT=$(mktemp -t convert_docx.XXXXXX).txt
  textutil -convert txt -output "$TMP_TXT" "$INPUT"
  # Wrap in a minimal markdown frame so consumers know this was lossy
  {
    echo "<!-- Generated from $INPUT via textutil (lossy). Install pandoc for better fidelity. -->"
    echo ""
    cat "$TMP_TXT"
  } > "$OUTPUT"
  rm -f "$TMP_TXT"
else
  cat <<EOF >&2
error: no converter available. Install one:
  brew install pandoc        # preferred — preserves tables and formatting
  # textutil ships with macOS but appears unavailable here
EOF
  exit 1
fi

echo "[done] $OUTPUT"
