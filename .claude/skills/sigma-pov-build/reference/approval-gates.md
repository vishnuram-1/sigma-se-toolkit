# Approval gates

This skill writes to a shared system the prospects use to evaluate Sigma. Every write to that system requires explicit user approval. The gates below structure that approval discipline.

## The six gates

### Gate 1 — Scoping confirmed
**Triggers after:** `scoping.md` is read from the prospect folder. (This skill does **not** create or enrich it — that's a separate prerequisite. If the file is missing, halt and ask the user to create one.)
**Show:** a short summary of the scoping as read — use case(s), stakeholders, named data sources/tables, known data quirks, blockers — so the user can confirm it's current and correct before any warehouse work begins.
**Action on approval:** proceed to creds (step 2) + warehouse overview (step 3).
**Action on reject:** user edits `scoping.md` (or points at an updated one); re-read and re-summarize.

### Gate 2 — Connection verified + POV-relevant tables mapped
**Triggers after:** the warehouse overview (step 3, see `reference/warehouse-overview.md`) completes: connection matched via `list-connections.sh`, then the live warehouse discovered and **sampled** to identify and measure the tables relevant to the POV.
**Show:**
- matched connection (name, type, ID) — or, if no match, a clear "the warehouse connection isn't set up in their org" message;
- the **relevant-tables shortlist**: table → measured grain → key columns → row count;
- the **reconciliation**: what scoping asserted vs. what the data actually shows (fan-out factors, null rates, value domains), with mismatches flagged.
**Action on approval (match found):** proceed to data model spec — built from the measured reality, not scoping's prose.
**Action on no match:** halt. Surface as an AE setup blocker. Do not attempt to create the connection.

### Gate 3 — Data model spec ready
**Triggers after:** data model spec generated and written to `data-models/<name>.json`.
**Show:** spec summary — sources, column count, metric list, calculated columns by name, folder groupings.
**Action on approval:** POST via `sigma_curl` (sourced from `scripts/api/_env.sh` — gives you `Authorization` + `Accept: application/json` + 401 auto-retry for free).
**Action on reject:** revise spec based on feedback.

### Gate 4 — Data model deployed and verified
**Triggers after:** the `sigma_curl -X POST /v2/data-models` returns success and a follow-up `sigma_curl GET /v2/data-models/{id}` confirms.
**Show:** the URL to the model in the prospect's Sigma UI, column count from GET vs. expected.
**Action on approval:** proceed to workbook spec.
**Action on mismatch:** rollback (`sigma_curl -X DELETE /v2/data-models/{id}`), regenerate, retry.

### Gate 5 — Workbook spec ready
**Triggers after:** workbook spec generated and written to `workbooks/<name>.json`. The plan that produced it must include a `Chunks Read:` line listing which `sigma-workbook-conventions/reference/specification/*.md` and `reference/workflows/*.md` chunks were consulted (this is a hard gate in `sigma-workbook-conventions/SKILL.md`).
**Show:** page list, KPI tiles per page, Input Tables, Sigma Agent configuration, the `Chunks Read:` line from the plan.
**Action on approval:** POST via `publish-workbook.sh post` (which auto-runs `validate-spec.py` with its 7 pre-POST checks). If validate-spec fails, the POST is aborted by the wrapper before any state changes — surface the failure to the user and fix in-place.
**Action on reject:** revise spec.

### Gate 6 — Workbook deployed and verified
**Triggers after:** `publish-workbook.sh post` returns `{workbookId, url, path}`, followed by `publish-workbook.sh get-spec <workbookId> | jq . > workbooks/<name>.json` (the GET-back spec is the new source of truth — Sigma normalizes IDs and layout XML on POST) and `verify-workbook.sh <workbookId>`.
**Show:** prospect-org URL, page count, element count, validation result from `verify-workbook.sh`.
**Action on approval:** done. Update `notes.md` with a one-liner. The API doesn't validate cross-element column resolution or visualization quality — open the URL in a browser for the final visual pass.
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
