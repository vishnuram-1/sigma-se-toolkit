---
name: sigma-pov-build
description: >-
  Use when the user wants to work on a Sigma POV/POC for a specific
  prospect — build a data model or a workbook for that prospect's Sigma
  org, grounded in the prospect's live warehouse. Composes the sigma-api,
  sigma-data-models, and sigma-workbook-conventions skills with the
  per-prospect folder convention under prospects/.
  Assumes scoping.md already exists (created separately). Triggers on
  phrases like "work on the <name> POV", "build the data model for
  <name>", "build a workbook for <name>", or any mention of a prospect
  that matches an existing prospect_<Name>/ folder.
---

# sigma-pov-build

Orchestrates the Sigma Solutions Engineer POV workflow: starting from an existing `scoping.md`, inspect and sample the prospect's live warehouse, then build and deploy data models and workbooks to the prospect's Sigma org — grounded in the real data, with explicit approval gates before any write.

## When to use

Activate when the user mentions a specific prospect by name AND wants to:
- Build a data model for that prospect
- Build a workbook for that prospect
- Push artifacts to that prospect's Sigma org

This skill assumes a `scoping.md` already exists in the prospect folder — it is a **prerequisite**, produced by the `sigma-scoping` skill from the Gong `context_<Name>.txt` plus whatever data artifacts the folder holds (LookML, dbt, CSVs, mockups). This skill does not create or enrich it. If `scoping.md` is missing, run `sigma-scoping` first.

If the user asks a generic Sigma question (auth, spec field reference) without a prospect, defer to the upstream skills directly (`sigma-api`, `sigma-data-models`, `sigma-workbook-conventions`).

## Prerequisites

- Prospect folder exists at `prospects/prospect_<Name>/`. If unsure, run `scripts/scan_prospects.sh`.
- **`scoping.md` exists** in that folder. This skill builds *from* it — it does not write it. If absent, halt and use the `sigma-scoping` skill to create one first.
- The upstream Sigma skills are loaded: `sigma-api`, `sigma-data-models`, `sigma-workbook-conventions`. This skill is the orchestrator — it does not duplicate their content.
- The globalized Sigma scripts are vendored at `scripts/` (mirrors the upstream `ryan-workbook-skill/scripts/` layout). Every script in `scripts/api/*.sh` self-bootstraps via `_env.sh`: it reads `.env` from the **current working directory**, fetches an OAuth token via the `sigma-api` skill's `get-token.sh`, and caches it at `/tmp/.sigma_token` (mode 0600, 55-min TTL). The implication: **always `cd` into the prospect folder before invoking these scripts**, so the per-prospect `.env` resolves correctly.

## Session-mode kickoff

`sigma-workbook-conventions` defines two session-mode triggers — `start build mode` and `start training mode`. The pov-build flow integrates with these:

- A prospect-named kickoff (`work on the X POV`, `build for Newity`, etc.) **implicitly enters build mode**, but adds the prospect-folder wrapper. Skip workbook-conventions' generic 3-question gate (env / data source / what+where) — those answers come from the prospect folder: `.env` is at `prospect_<Name>/.env`, the data source is in `scoping.md`, and the destination folder in Sigma is either captured in `scoping.md` or asked at gate 5.
- `start training mode` still applies: when the user is teaching a new pattern (industry-specific KPI shape, novel control layout), capture it with `local-` prefixed files in the appropriate skill — not in the prospect folder.

Before drafting any workbook plan, `sigma-workbook-conventions` requires a hard `Chunks Read:` line listing which `reference/specification/*.md` and `reference/workflows/*.md` chunks were consulted. That requirement applies to plans drafted inside this skill too. Don't skip it.

## Composition with other skills

| Concern | Where to look |
|---|---|
| OAuth → bearer token, base URL per cloud | `sigma-api` |
| Data model spec field reference (sources, columns, metrics, etc.) | `sigma-data-models` |
| Workbook spec authoring — element naming, page/folder layout, POST-vs-PUT pitfalls, the chunked `reference/specification/*` (charts, controls, formulas, layout, tables, etc.) and `reference/workflows/*` (crud, discover, plan, validate, from-image) | `sigma-workbook-conventions` |
| Scenario / what-if pages — is it that shape, and what's the grain? | [`reference/scenario-modeling-patterns.md`](reference/scenario-modeling-patterns.md) |
| Scenario / what-if **build mechanics** (input tables, modals, approve-and-lock) | `sigma-input-table-app` — **not bundled**; install the `millersigma` plugin marketplace |
| Branded embed portal deployment | `sigma-embed-portal` — **not bundled**; install the `millersigma` plugin marketplace if you need it |
| Everything below (folder shape, warehouse grounding, approval flow) | This skill |

There is no recon-specific skill. One shipped here briefly but prescribed a
structure with a placeholder exemplar behind it, which is worse than nothing —
it reads as verified guidance. Re-add only with 2-3 real recon specs to anchor
the pattern.

## Workflow at a glance

```
1. Read scoping.md from the prospect folder            ─── GATE 1 (confirm it's the basis to build from)
2. Resolve creds: read prospect_<Name>/.env; if it's
   missing, ask the user for API creds                 ─── (blocks until creds resolve)
3. Connection + warehouse overview:                    ─── GATE 2 (connection found + POV-relevant tables mapped)
     • list-connections.sh → match scoping's warehouse
     • explore the live warehouse (Sigma MCP describe/
       query) to discover and SAMPLE the tables relevant
       to the POV; reconcile against what scoping names
4. Generate data model spec — grounded in step 3,
   not in scoping's assertions                          ─── GATE 3 (approve spec)   [refine separately]
5. POST data model to prospect's Sigma org             ─── GATE 4 (verify via GET)
6. Generate workbook spec (defers to
   sigma-workbook-conventions)                          ─── GATE 5 (approve spec)   [refine separately]
7. POST workbook to prospect's Sigma org               ─── GATE 6 (verify + open in browser)
```

Six gates. Never POST without explicit user approval. See `reference/approval-gates.md`.

**Scoping is not part of this flow.** `scoping.md` is a prerequisite owned by the `sigma-scoping` skill, which builds it from Gong transcripts and whatever data artifacts the prospect folder holds. This skill starts by reading it (step 1), never by writing it.

**Steps 4 and 6 (spec generation) are provisional.** They are the current mainline but are slated for deeper, per-step refinement — treat `reference/data-model-build.md` (spec-drafting portion) and the workbook-gen handoff as works-in-progress. The one part that is now firm is step 3: **no spec is drafted until the real warehouse has been inspected and sampled.**

## Reference

- [`reference/folder-layout.md`](reference/folder-layout.md) — canonical prospect_<Name>/ shape and file responsibilities
- [`reference/warehouse-overview.md`](reference/warehouse-overview.md) — step 3: discover + sample the prospect's live warehouse to ground the model in measured reality
- [`reference/credentials.md`](reference/credentials.md) — .env handling, secret-safety invariants
- [`reference/data-model-build.md`](reference/data-model-build.md) — mapping scoping sections → data model spec
- [`reference/workbook-build.md`](reference/workbook-build.md) — mapping scoping sections → workbook spec, page-per-stakeholder default
- [`reference/approval-gates.md`](reference/approval-gates.md) — the six gates, what each one verifies, what to show the user

## Scripts

- [`scripts/scan_prospects.sh`](scripts/scan_prospects.sh) — list prospect folders that have scoping + Gong context (i.e. ready to work)

## Examples

- [`examples/reltio/`](examples/reltio/) — anchor example. Filled in after the first end-to-end run; use as a diff target for future POVs.

## Critical safety invariants

1. **Never POST without approval.** Generate specs to disk, show the user, wait for explicit go-ahead. POSTing to a prospect's org is a write to a shared system they evaluate Sigma in.
2. **Never echo or commit secrets.** `.env` is gitignored at the repo root. Tokens are passed via `Authorization` headers only. Do not write secrets to any file inside the workspace.
3. **Never invent the scoping doc.** `scoping.md` is a prerequisite. If it's missing, ask the user to create one — do not synthesize scope from transcripts alone. The user fills the doc with the prospect.
4. **Default to update, not duplicate.** Before building, check what the AE already has in the prospect's Sigma org via `GET /v2/workbooks` and `GET /v2/data-models`. Extend, don't duplicate.
