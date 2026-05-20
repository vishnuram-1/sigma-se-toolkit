# Data model build

Map `scoping.md` → a Sigma data model spec, then write to disk for review. Don't POST without approval.

## Inputs

From `scoping.md`:
- **Use case** — determines what the model needs to answer.
- **Data references** — table(s), columns, quirks.
- **Stakeholders** — drives metric naming (use business language they speak).
- **Priority artifacts** — explicit metric and dimension asks.

From the prospect's Sigma org (via `sigma-api` token):
- `GET /v2/connections` — find the warehouse connection ID for the source. Pause if missing.

## Build sequence

1. **Verify connection.** `GET /v2/connections` against the prospect org. Find the connection that matches `scoping.md`'s warehouse (BigQuery, Snowflake, Redshift, etc.). If none, halt and surface this as a setup blocker for the AE — Claude cannot create connections via API.

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

5. **POST.** On approval:
   ```bash
   curl -X POST "$SIGMA_BASE_URL/v2/data-models" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     --data @data-models/<name>.json
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

- **Recon-shaped use case** (GL tie-out, bank recon, sub-ledger ↔ GL) → use `sigma-fin-recon` as an additional reference. It provides exemplar metric definitions and aging-bucket patterns.
- **Generic workbook layout rules** → `sigma-workbook-conventions` after the model is done.
