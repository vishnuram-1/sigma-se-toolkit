# Per-prospect folder layout

Canonical shape under `prospects/prospect_<Name>/`:

```
prospect_<Name>/
├── context_<Name>.txt         # auto-synced from Sigma; transcripts only; do not edit
├── scoping.md                 # PREREQUISITE, user-owned; the basis this skill builds from
├── .env                       # per-prospect Sigma creds (gitignored, never echoed)
├── data-models/               # generated data model specs
│   └── <name>.json
├── workbooks/                 # generated workbook specs
│   └── <name>.json
├── mockups/                   # HTML mockups, sample CSVs (hand-added)
├── reference/                 # dbt artifacts, manual exports, misc source material
└── notes.md                   # short iteration log (optional)
```

`scoping.docx` may also be present as a seed the user converted from — but it is prep material, not consumed by this flow.

## File responsibilities

| File | Owner | Mutability |
|---|---|---|
| `context_<Name>.txt` | Sync script (`scripts/sync_gong_calls.py` in repo root) | Read-only for this skill. Never edit. |
| `scoping.md` | User | **Prerequisite.** Read-only for this skill — it builds *from* it, never writes it. Created/maintained in a separate scoping-prep activity. |
| `.env` | User | Read-only. Never echo, never log, never write to other files. |
| `data-models/*.json` | This skill | Generated (grounded in the warehouse overview). Overwritten on regeneration. Captured `id` field after POST is used for future PUTs. |
| `workbooks/*.json` | This skill | Same as data-models. |
| `mockups/`, `reference/` | User | Hand-added source material. This skill reads them; doesn't manage them. |
| `notes.md` | This skill + user | Append-only log. Short, dated entries. |

## Discovery

When a session needs to know which prospects are ready to work:

```bash
~/.claude/skills/sigma-pov-build/scripts/scan_prospects.sh
```

This lists prospect folders that have BOTH a scoping artifact AND a non-empty `context_<Name>.txt`. No stage filter (stage is intentionally out of scope for now). (Skill relocated to `~/.claude/skills/` on 2026-06-30; the scripts still target the repo at ``.)

## What we do NOT add

- `stage.txt` — explicitly dropped. Stage logic deferred until the source-of-truth question is answered.
- `scoping_history/` — git diff on `scoping.md` is the history; we don't duplicate it.
- Per-prospect `.claude/` subdirectories — one skill at the repo level, not per prospect.
