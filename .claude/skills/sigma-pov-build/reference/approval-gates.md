# Approval gates

This skill writes to a shared system Vishnu's prospects use to evaluate Sigma. Every write to that system requires explicit user approval. The gates below structure that approval discipline.

## The six gates

### Gate 1 — Scoping ready
**Triggers after:** docx conversion + enrichment pass produces `scoping.md`.
**Show:** summary of what was added beyond the raw docx conversion (stakeholder names, decisions, blockers, existing AE work, data quirks).
**Action on approval:** proceed to creds + connection check.
**Action on reject:** edit `scoping.md` based on feedback or wait for an updated `scoping.docx`.

### Gate 2 — Connection verified
**Triggers after:** `GET /v2/connections` against prospect org.
**Show:** matched connection (name, type, ID) — or, if no match, a clear "the warehouse connection isn't set up in their org" message.
**Action on approval (match found):** proceed to data model spec.
**Action on no match:** halt. Surface as an AE setup blocker. Do not attempt to create the connection.

### Gate 3 — Data model spec ready
**Triggers after:** data model spec generated and written to `data-models/<name>.json`.
**Show:** spec summary — sources, column count, metric list, calculated columns by name, folder groupings.
**Action on approval:** POST.
**Action on reject:** revise spec based on feedback.

### Gate 4 — Data model deployed and verified
**Triggers after:** `POST /v2/data-models` returns success and `GET /v2/data-models/{id}` confirms.
**Show:** the URL to the model in the prospect's Sigma UI, column count from GET vs. expected.
**Action on approval:** proceed to workbook spec.
**Action on mismatch:** rollback (delete via `DELETE /v2/data-models/{id}`), regenerate, retry.

### Gate 5 — Workbook spec ready
**Triggers after:** workbook spec generated and written to `workbooks/<name>.json`.
**Show:** page list, KPI tiles per page, Input Tables, Sigma Agent configuration.
**Action on approval:** POST.
**Action on reject:** revise spec.

### Gate 6 — Workbook deployed and verified
**Triggers after:** `POST /v2/workbooks` and `GET /v2/workbooks/{id}`.
**Show:** prospect-org URL, page count, element count.
**Action on approval:** done. Update `notes.md` with a one-liner.
**Action on mismatch:** rollback, regenerate, retry.

## What "show" means

Concise. The user already gave you context once. Each gate's "show" should be:
- 1 short paragraph OR 1 small table
- The artifact path on disk
- The exact next action ("POST to /v2/data-models?")

Don't dump the full spec JSON in chat. Reference the file. The user can read it.

## Ask format

Use `AskUserQuestion` with two options minimum:
- "Approve — POST to <prospect> org"
- "Revise — feedback below"

If the user revises, ask follow-up specifically; don't loop the same gate without movement.

## What requires no gate

These are safe to do without asking each time:
- Reading any file in the prospect folder
- `GET` calls against the prospect's Sigma org (read-only)
- Writing to `data-models/*.json` and `workbooks/*.json` on disk (you can always regenerate)
- Updating `notes.md` with progress entries
- Updating `scoping.md` (but show the diff after — gate 1)

## What requires a gate even mid-flow

- ANY `POST`, `PUT`, `PATCH`, `DELETE` against the prospect's Sigma org
- Creating a new prospect folder (this skill operates on existing ones — folder creation is a user action)
- Writing `.env` (never — user writes it)
- Pushing the prospects repo to GitHub (user action, not Claude's)
