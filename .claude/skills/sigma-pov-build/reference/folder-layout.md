# Per-prospect folder layout

Canonical shape under `~/Prospects/vish-gong-test/prospects/prospect_<Name>/`:

```
prospect_<Name>/
├── context_<Name>.txt         # auto-synced from Sigma; transcripts only; do not edit
├── scoping.docx               # user-provided seed; source of truth for scope
├── scoping.md                 # generated/maintained; enriched from .docx + Gong
├── .env                       # per-prospect Sigma creds (gitignored, never echoed)
├── data-models/               # generated data model specs
│   └── <name>.json
├── workbooks/                 # generated workbook specs
│   └── <name>.json
└── notes.md                   # short iteration log (optional)
```

## File responsibilities

| File | Owner | Mutability |
|---|---|---|
| `context_<Name>.txt` | Sync script (`scripts/sync_gong_calls.py` in repo root) | Read-only for this skill. Never edit. |
| `scoping.docx` | User (Vishnu, filled with the prospect) | Read-only for this skill. User updates it externally. |
| `scoping.md` | This skill | Regenerated when `scoping.docx` is newer OR new transcripts since last write. Overwrites in place. |
| `.env` | User | Read-only. Never echo, never log, never write to other files. |
| `data-models/*.json` | This skill | Generated. Overwritten on regeneration. Captured `id` field after POST is used for future PUTs. |
| `workbooks/*.json` | This skill | Same as data-models. |
| `notes.md` | This skill + user | Append-only log. Short, dated entries. |

## Discovery

When a session needs to know which prospects are ready to work:

```bash
~/Prospects/vish-gong-test/.claude/skills/sigma-pov-build/scripts/scan_prospects.sh
```

This lists prospect folders that have BOTH `scoping.docx` (or `scoping.md`) AND a non-empty `context_<Name>.txt`. No stage filter (stage is intentionally out of scope for now).

## What we do NOT add

- `stage.txt` — explicitly dropped. Stage logic deferred until the source-of-truth question is answered.
- `scoping_history/` — git diff on `scoping.md` is the history; we don't duplicate it.
- Per-prospect `.claude/` subdirectories — one skill at the repo level, not per prospect.
