---
name: sigma-pov-build
description: >-
  Use when the user wants to work on a Sigma POV/POC for a specific
  prospect — enrich the scoping doc, build a data model, or build a
  workbook for that prospect's Sigma org. Composes the sigma-api,
  sigma-data-models, and sigma-workbook-conventions skills with the
  per-prospect folder convention under ~/Prospects/vish-gong-test/prospects/.
  Triggers on phrases like "work on the <name> POV", "enrich the scoping
  for <name>", "build the data model for <name>", or any mention of a
  prospect that matches an existing prospect_<Name>/ folder.
---

# sigma-pov-build

Orchestrates the Sigma Solutions Engineer POV workflow: ingest a prospect's scoping doc, enrich it from Gong transcripts, then build and deploy data models and workbooks to the prospect's Sigma org — with explicit approval gates before any write.

## When to use

Activate when the user mentions a specific prospect by name AND wants to:
- Convert / enrich a scoping doc
- Build a data model for that prospect
- Build a workbook for that prospect
- Push artifacts to that prospect's Sigma org

If the user asks a generic Sigma question (auth, spec field reference) without a prospect, defer to the upstream skills directly (`sigma-api`, `sigma-data-models`, `sigma-workbook-conventions`).

## Prerequisites

- Prospect folder exists at `~/Prospects/vish-gong-test/prospects/prospect_<Name>/`. If unsure, run `scripts/scan_prospects.sh`.
- The upstream Sigma skills are loaded: `sigma-api`, `sigma-data-models`, `sigma-workbook-conventions`. This skill is the orchestrator — it does not duplicate their content.

## Composition with other skills

| Concern | Where to look |
|---|---|
| OAuth → bearer token, base URL per cloud | `sigma-api` |
| Data model spec field reference (sources, columns, metrics, etc.) | `sigma-data-models` |
| Workbook naming / layout / POST-vs-PUT pitfalls | `sigma-workbook-conventions` |
| Recon-shaped POVs (GL tie-out, bank recon, etc.) | `sigma-fin-recon` |
| Everything below (folder shape, scoping enrichment, approval flow) | This skill |

## Workflow at a glance

```
1. Detect prospect folder + read scoping.docx (if present)
2. Convert .docx → .md, enrich with Gong context  ─── GATE 1 (approve scoping.md)
3. Read .env, mint Sigma token via sigma-api      ─── (silent if creds present)
4. Verify warehouse connection exists in org      ─── GATE 2 (block if missing)
5. Generate data model spec from scoping          ─── GATE 3 (approve spec)
6. POST data model to prospect's Sigma org        ─── GATE 4 (sanity check)
7. Generate workbook spec from scoping + model    ─── GATE 5 (approve spec)
8. POST workbook to prospect's Sigma org          ─── GATE 6 (sanity check)
```

Six gates. Never POST without explicit user approval. See `reference/approval-gates.md`.

## Reference

- [`reference/folder-layout.md`](reference/folder-layout.md) — canonical prospect_<Name>/ shape and file responsibilities
- [`reference/scoping-enrichment.md`](reference/scoping-enrichment.md) — docx → md conversion, what to layer in from Gong transcripts, re-run rules
- [`reference/credentials.md`](reference/credentials.md) — .env handling, secret-safety invariants
- [`reference/data-model-build.md`](reference/data-model-build.md) — mapping scoping sections → data model spec
- [`reference/workbook-build.md`](reference/workbook-build.md) — mapping scoping sections → workbook spec, page-per-stakeholder default
- [`reference/approval-gates.md`](reference/approval-gates.md) — the six gates, what each one verifies, what to show the user

## Scripts

- [`scripts/scan_prospects.sh`](scripts/scan_prospects.sh) — list prospect folders that have scoping + Gong context (i.e. ready to work)
- [`scripts/convert_docx.sh`](scripts/convert_docx.sh) — idempotent `.docx` → `.md` wrapper (pandoc preferred, textutil fallback)

## Examples

- [`examples/reltio/`](examples/reltio/) — anchor example. Filled in after the first end-to-end run; use as a diff target for future POVs.

## Critical safety invariants

1. **Never POST without approval.** Generate specs to disk, show the user, wait for explicit go-ahead. POSTing to a prospect's org is a write to a shared system they evaluate Sigma in.
2. **Never echo or commit secrets.** `.env` is gitignored at the repo root. Tokens are passed via `Authorization` headers only. Do not write secrets to any file inside the workspace.
3. **Never invent the scoping doc.** If `scoping.docx` is missing, ask the user for it. Do not synthesize scope from transcripts alone — the user fills the doc with the prospect.
4. **Default to update, not duplicate.** Before building, check what the AE already has in the prospect's Sigma org via `GET /v2/workbooks` and `GET /v2/data-models`. Extend, don't duplicate.
