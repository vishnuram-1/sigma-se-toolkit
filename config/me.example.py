"""Per-SE configuration for the Gong sync.

    cp config/me.example.py config/me.py

config/me.py is gitignored — your edits will never conflict with an upstream
pull, and nobody inherits your rep list by forgetting to change theirs.

Only REPS normally needs setting. Everything else exists so that pointing at
a different workbook never means editing scripts/sync_gong_calls.py, which
WOULD conflict on every pull. Anything you omit falls back to the shared
default shown in the comment.

Note: the nightly GitHub Action does not see this file (it's untracked).
Set REPS there as a repository *variable* instead — Settings -> Secrets and
variables -> Actions -> Variables -> New repository variable, name REPS.
The env var takes precedence over this file, so the two never fight.
"""

# Comma-separated Opportunity Owner names, no space after the comma.
#
# REQUIRED. Left empty, the export returns every rep's calls — including
# prospects that aren't yours — so the script refuses to run and says so.
# Pass --allow-unfiltered if you genuinely want the whole company's calls.
#
# Get the exact strings — they are matched literally, and a typo returns zero
# rows while looking like a completely successful run:
#
#     python scripts/sync_gong_calls.py --list-reps
#
# Example: REPS = "Jane Doe,John Smith,Maria Garcia"
REPS = ""

# --- Optional overrides (defaults shown) ------------------------------------

# Source workbook and the workspace it lives in.
# WORKBOOK_NAME = "VR Gong Calls"
# WORKSPACE_NAME = "Client_B_Vish"

# Element ID of the rep-filter control on the Gong Calls table.
# REPS_CONTROL_ID = "New-Control"

# Days without a call before a prospect's context_*.txt is pruned.
# Only the transcript file is removed — never the folder, which holds your
# scoping.md, data-models/, workbooks/ and a gitignored .env.
# STALE_AFTER_DAYS = 90
