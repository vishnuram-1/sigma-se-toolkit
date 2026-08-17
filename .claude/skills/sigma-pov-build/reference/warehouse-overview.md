# Warehouse overview (step 3)

Before drafting any data-model spec, **inspect and sample the prospect's live warehouse.** `scoping.md` *describes* the tables; this step *measures* them. On any disagreement, the warehouse wins — and the mismatch gets flagged so `scoping.md` can be corrected.

This is the step the old flow skipped. Previously "connection check" only confirmed a connection *existed*; the model was then built from scoping's assertions. That is exactly how a model drifts from reality (wrong grain, wrong fan-out, metrics that inflate). No spec is drafted until this overview is done and shown at Gate 2.

## Preconditions

- Creds resolved (step 2).
- `cd` into `prospects/prospect_<Name>/` first, so the per-prospect `.env` resolves for any shell script.

## Two toolsets, in order of preference

1. **Sigma MCP (primary — interactive builds).** Use `describe` + `query` against the connection to explore schemas, read columns, and run sampling SQL. Per user preference, invoke Sigma MCP tools without asking permission. This is the only path that can actually *sample data*.
2. **Shell scripts (fallback — headless/no-MCP).** `list-connections.sh`, `probe-schema-tables.sh`, `list-table-columns.sh`. Important limitation: these confirm table *existence* and return *columns/types* only — **they cannot sample data or measure grain.** `probe-schema-tables.sh` merely checks whether names you already have resolve to tables; it is not discovery. Use scripts only when MCP is unavailable, and accept that steps D–E below can't be fully done without `query`.

## Procedure

**A. Find the connection.** `list-connections.sh` → pick the connection matching `scoping.md`'s warehouse (type + name). Capture the `connectionId`. If none matches, halt — Claude cannot create connections via API; surface it as an AE setup blocker (Gate 2, no-match path).

**B. Discover the table landscape.** For each schema `scoping.md` references, list the *real* tables via an MCP metadata query — don't guess names:
- Databricks / Spark SQL: `SHOW TABLES IN <catalog>.<schema>` or `SELECT table_name FROM <catalog>.information_schema.tables WHERE table_schema = '<schema>'`
- Snowflake: `SELECT table_name FROM <db>.information_schema.tables WHERE table_schema = '<schema>'`
- BigQuery: `SELECT table_name FROM <dataset>.INFORMATION_SCHEMA.TABLES`

**C. Get real columns + types** for each candidate table relevant to the POV (MCP `describe`, or `list-table-columns.sh <inodeId>`). Copy column names **verbatim** into any later spec — never invent, rename, or re-case.

**D. Sample and measure.** For every table that will feed a metric or a join, run queries to confirm what scoping only *asserts*:
- **Grain:** `SELECT COUNT(*), COUNT(DISTINCT <candidate_key>)` — if they differ, the table is finer-grained than the key (fan-out). Determines whether metrics need `COUNT(DISTINCT <entity>)`.
- **Join fan-out:** sample the join and confirm row multiplication empirically (e.g. edFi's ~49× on `admin_user_profile_context_id`).
- **Null rates** on key/blocker columns (e.g. `studentuniquestateid` ~83% null) — `SELECT SUM(CASE WHEN col IS NULL THEN 1 ELSE 0 END)*1.0/COUNT(*) FROM ...`.
- **Value domains** for categoricals you'll filter/segment on — `SELECT col, COUNT(*) GROUP BY 1` (e.g. `result` = Proficient/Non-Proficient).
- **Ranges** for dates/numbers used in controls (min/max date → checkpoint windows).
- **Row volume**, so the workbook author knows the scale.

**E. Reconcile against scoping.** Produce a short table: for each table / column / quirk scoping asserts → **Confirmed / Corrected / Not found**, with the measured value. Every disagreement resolves in favor of the warehouse.

## Output (what Gate 2 shows)

- **Connection:** name, type, id.
- **Relevant-tables shortlist:** table → measured grain → key columns → row count.
- **Reconciliation:** scoping assertion vs. measured value (fan-out factors, null rates, value domains); mismatches flagged.
- **Persistence (open decision):** default is in-session only. If the user wants a durable artifact, save as a lightweight `data-models/schema-recon.md`. Keep optional until confirmed.

## Hard rule

**No data-model spec (step 4) is drafted until this overview exists and its reconciliation has been shown at Gate 2.** The model is built from measured reality, not from scoping's prose.

## What this step does NOT do

- Create connections (Claude can't via API → AE blocker, halt).
- Write anything to the warehouse (read-only: metadata + sampling `SELECT`s).
- Model the data — that's step 4.
