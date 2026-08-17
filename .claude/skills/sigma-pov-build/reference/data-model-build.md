# Data model build

Map the **warehouse overview + `scoping.md`** → a Sigma data model spec, then write to disk for review. Don't POST without approval.

> **Provisional (2026-06-30).** The spec-drafting sequence below (step 2 onward) is slated for deeper, per-step refinement — treat it as a work-in-progress, not settled doctrine. The one part that is now firm: the model is grounded in the **measured** warehouse (step 1 / `reference/warehouse-overview.md`), never in scoping's assertions alone.

## Inputs

The measured warehouse is the source of truth; `scoping.md` supplies intent and business language. On conflict, the warehouse wins.

From the **warehouse overview** (step 3, `reference/warehouse-overview.md`) — the primary input:
- **Real tables, columns, and types** — copied verbatim.
- **Measured grain and join fan-out** — dictates where metrics need `COUNT(DISTINCT <entity>)`.
- **Null rates and value domains** — dictate calculated columns, filters, and control options.

From `scoping.md`:
- **Use case** — determines what the model needs to answer.
- **Stakeholders** — drives metric naming (use business language they speak).
- **Priority artifacts** — explicit metric and dimension asks.

## Build sequence

1. **Ground the model in the warehouse (do not skip).** Complete the warehouse overview per `reference/warehouse-overview.md`: match the connection via `scripts/api/list-connections.sh` (cd into the prospect folder first so `.env` resolves), then discover and **sample** the relevant tables with the Sigma MCP `describe`/`query` tools. Produce the reconciliation (scoping asserts vs. measured) and clear Gate 2. If no matching connection exists, halt and surface as an AE setup blocker — Claude cannot create connections via API. **No spec is drafted until this is done.**

2. **Draft the spec.** Use `sigma-data-models` skill for field-level reference. Components:
   - **Sources** — table reference (database.schema.table), connection ID.
   - **Columns** — source columns with types. Map column names verbatim from scoping; don't rename.
   - **Calculated columns** — derived from scoping (e.g. `is_high_intent` flag).
   - **Metrics** — aggregations. Use `COUNT(DISTINCT Person_Id)` when the field is person-level, not row-level (this is a common quirk).
   - **Relationships** — only if multiple tables in scope.
   - **Filters / controls** — surface what the stakeholders said they want to filter by.
   - **Folder groupings** — group columns/metrics by stakeholder concern (Pipeline, Channel, Territory, etc.) so the workbook author can find them.
   - **Column-level security** — apply only if scoping calls it out.

3. **Write to disk.** `prospects/prospect_<Name>/data-models/<name>.json`. Use a slugified name (e.g. `gtm_interactions.json`).

4. **Show the user.** Surface a summary (sources, column count, metric count, calculated columns by name). Pause. Wait for explicit approval. This is gate 3 (see `approval-gates.md`).

5. **POST.** On approval, from the prospect folder. There's no `publish-data-model.sh` wrapper in upstream — data-model POSTs go through `sigma_curl` (the helper that `_env.sh` exports, with 401 auto-retry):
   ```bash
   cd prospects/prospect_<Name>
   source scripts/api/_env.sh
   sigma_curl -X POST \
     -H "Content-Type: application/json" \
     --data-binary @data-models/<name>.json \
     "$SIGMA_BASE_URL/v2/data-models"
   ```
   Capture the returned `id`. Write it back into the spec file under `"_metadata": {"id": "...", "posted_at": "..."}` so future updates know to PUT, not POST.

6. **Verify.** `GET /v2/data-models/{id}`. Confirm the model exists and has the expected column count. Gate 4.

## Update semantics

For an existing model (spec has `_metadata.id`):
- Use `PUT /v2/data-models/{id}` — not POST. Sigma treats them differently; POST with an ID is an error or duplicates.
- The `sigma-workbook-conventions` skill spells out the ID semantics in detail.

## Common pitfalls

| Pitfall | What goes wrong | Fix |
|---|---|---|
| Counting rows when the question is about people | `COUNT(*)` inflates because of many rows per person | Use `COUNT(DISTINCT Person_Id)` (or whichever entity key) |
| Inventing column names | Source CSV had `Customer_ID`, spec has `customer_id` | Always copy column names verbatim from scoping/source |
| Skipping the connection check | POST fails with `connection_id not found` | Step 1 above is mandatory |
| Including the source schema in the table name | Sigma expects table + connection-scoped schema, not `db.schema.table` in one field | Check `sigma-data-models` for field separation |

## When to defer to another skill

- **Scenario / what-if** (named scenarios, approval-and-lock workflow) → check the shape and pick the grain with [`scenario-modeling-patterns.md`](scenario-modeling-patterns.md), then build with `sigma-input-table-app` from the `millersigma` marketplace. The data model holds the base table plus Input Tables for overrides; that skill encodes the cross-join, page-control filter and modal-edit primitives.
- **Generic workbook layout rules** → `sigma-workbook-conventions` after the model is done. Read the chunked `reference/specification/*` and `reference/workflows/*` before drafting the workbook plan.
- **Recon-shaped use case** (GL tie-out, bank recon, sub-ledger ↔ GL) — no skill currently. One was dropped because it prescribed a structure with only a placeholder exemplar behind it. Re-add when 2-3 real recon specs exist to anchor the pattern.
