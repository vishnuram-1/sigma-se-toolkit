---
name: sigma-scenario-modeling
description: >-
  Use when the user wants to build a "scenario modeling" or "what-if" application
  in Sigma — anywhere users need to create named scenarios, override base values
  by a key (date, account, SKU, region, etc.), submit those scenarios for
  approval, and lock approved scenarios from further edits. Generic across
  verticals: GTM pipeline forecasting, demand planning, headcount/FP&A planning,
  marketing-spend allocation, capex, supply-chain reorder modeling, pricing
  scenarios, loan-loss curve scenarios. Provides the canonical Sigma primitives
  (empty + linked input tables, 1=1 cross-join, page-control filter, modal
  workflow, conditional editing rules) and the standard pages, columns, and
  actions that make a scenario app work. Requires sigma-api and sigma-data-models;
  pair with sigma-workbook-conventions for naming/layout rules.
---

# Sigma Scenario-Modeling Workbook Skill

Generate / edit / audit Sigma "what-if" workbooks where users create named
scenarios, override a base series, route for approval, and lock approved
scenarios. This is a **workbook-pattern skill** — it prescribes the structure
and primitives, leaving field-level mechanics to `sigma-data-models`.

## When this skill is the right one

Use this skill when **all four** of these are true:

1. There is a **base series** with a primary grain (typically date, but could
   be account × period, SKU × week, cohort × month).
2. Users need to create **multiple named alternatives** (forecasts, plans,
   what-ifs) that override or extend that base series.
3. A user (or set of users) **enters values** directly into Sigma — not just
   filters a dashboard. This is write-back territory.
4. There is an **approval / lock state**: once a scenario is approved, it
   should not be silently edited; further changes need a new revision or
   explicit unlock.

If only #1 and #2 are true (read-only comparison of pre-computed scenarios),
this is the wrong skill — use `sigma-data-models` with a `scenario` dimension
column instead.

If write-back is needed but there is no approval/lock requirement, the full
skill is overkill — keep the linked-input-table pattern (sections 2–4 below)
and skip the forecast-log and approval pages.

## Prerequisites

1. `sigma-api` skill has produced `$SIGMA_API_TOKEN`.
2. **Warehouse write-back is enabled** on the Sigma connection. Confirm via
   `GET /v2/connections` — look for `writeAccess: true` and a `writebacks[]`
   entry with `database` + `schema`. Without this, the input-table pattern
   does not work.
3. A base series exists — either a warehouse table or a derived data-model
   element with a clear primary grain.
4. The grain is **stable**: the join key between base and scenarios will be
   the same field set (e.g. `(scenario_name, date)`). If the grain shifts
   over time, freeze a snapshot before scenarios are entered.

## The canonical pattern (Ian Reed's flow, generalized)

Every scenario-modeling workbook produced by this skill follows the same
five-layer build. The verbs (`insert row`, `update row`, `set control`, etc.)
are Sigma action names — use them verbatim.

### Layer 1 — Base series

A single table element on a hidden / read-only page. One row per primary
grain (e.g. one row per week, or per `account × week`). Keep this lean —
only the columns the scenario layer actually consumes.

### Layer 2 — Scenario registry (empty input table)

A new empty input table with **one column: `forecast_name`** (or `scenario_name`,
`plan_name` — match the domain). This is the registry of named scenarios.
Users add to it via the "Create new forecast" modal in Layer 4.

Add audit columns later in Layer 4 once you wire up actions:
`status`, `submitted_by`, `submitted_on`, `submission_comments`,
`approval_status`, `approval_by`, `approval_on`, `approval_comments`.

This table is sometimes called the **forecast log** because each row is the
record-of-truth for one scenario's lifecycle.

### Layer 3 — Fan-out join

Reference the base series in a new table. Cross-join it to the scenario
registry by **creating two formula columns both equal to `1`** (one on each
side) and joining on those. This explodes every base row across every
scenario.

Convert that joined output to a **linked input table** with composite primary
key `(forecast_name, <grain key>)` — e.g. `(forecast_name, date)`. Bring in
the base value as the override column (rename it from `revenue` to `forecast`
or similar). Set the column type to numeric.

This is where users actually enter their forecast values.

### Layer 4 — Editing UI

On the user-facing page:

1. A **page-level filter control** on `forecast_name`, single-select, with
   "no null" so a scenario is always picked. This is what makes "one
   scenario at a time" editing work.
2. **Hide** the `forecast_name` column on the linked input table — it's
   already implied by the filter.
3. **"Create new forecast" button**: action sequence —
   - `Open modal` (new modal: text control "Enter forecast name", Cancel +
     Submit buttons, header/footer hidden so you can lay out your own buttons).
   - On the modal's Submit: `Insert row` into the scenario registry, with
     `forecast_name` = the text control value.
   - Then `Set control value` on the page filter to that same text control
     value (so the user lands on their new scenario).
   - Then `Close modal`.
   - On the Create button click itself, ALSO `Clear control` on the modal's
     text input first — so it doesn't show stale text from last time.
     **Actions run in the order you set them**, so clear before open.

4. **"Submit for approval" button**: action sequence —
   - `Open modal` (approval modal: text control "Submission comments", Cancel
     + Submit).
   - Modal Submit: `Update row` on the scenario registry. To make update-row
     work you must give Sigma a row ID — add an `ID` column (Sigma offers
     this as "add row ID" when you try to update). Pass the right row via a
     lookup: in a scratch column, `Lookup([forecast_log/ID], [forecast_log/forecast_name], [PageControl/forecast_name])`,
     then reference that lookup in the update-row action's row ID field.
   - The update writes `status = "Pending"`, `submission_comments` = modal
     control, `submitted_by = CurrentUserEmail()`, `submitted_on = Now()`.
   - `Close modal` and `Clear control` on the approval modal's text input.

### Layer 5 — Approval workflow

A separate page, "Approval Flow":

1. **Pending queue table**: scenario registry filtered to `status = "Pending"`
   AND `approval_status` is null. Columns: forecast name, submitted by,
   submitted on, submission comments, an "Approve" column with an emoji or
   "Approve" text in a contrasting color (orange/blue, not red).
2. **Approve column action**: on click —
   - `Set control value` on a hidden `approval_id` control = the row's ID.
   - `Clear control` on the approval-comments modal control (so stale text
     doesn't carry over).
   - `Open modal` (final approval modal).
3. **Final approval modal**: a segmented control with options
   `Approve / Deny / Change Requested`, a text control for approval comments,
   Cancel + Approve buttons.
4. **Approve button action**: `Update row` on the scenario registry where
   `ID = <approval_id control>`, setting `approval_status` = segmented
   control, `approval_comments` = text control,
   `approval_by = CurrentUserEmail()`, `approval_on = Now()`. Then close modal.
5. **Approved log table**: same registry filtered to `approval_status = "Approve"`.

### Layer 6 — Lock-down

Once a scenario is approved, edits to its forecast values must be blocked.
Two complementary mechanisms — use both:

1. **Conditional editing rule** on the linked input table's forecast column.
   In the data model's Data Entry tab → Conditional Editing Rules:

   > Allow editing when `approval_status != "Approve"` OR `approval_status is null`.

   ⚠️ **Sigma's wording trips everyone up**: the rule states the condition
   under which editing **is allowed**, not the condition under which it's
   blocked. Phrase it positively and remember the `OR is null` clause for
   brand-new scenarios that have no status yet.

2. **Conditional action on click**: on the forecast cell `select`, conditional
   "if `approval_status = "Approve"` then open a 'Locked — no edits allowed'
   modal." This is the user-friendly explanation layer; the editing rule is
   the real enforcement.

## Standard column set for the scenario registry

Name to match the domain (`forecast_log`, `plan_log`, `scenario_log`), but
keep the columns:

| Column | Type | Set by |
|---|---|---|
| `id` | text/uuid | Sigma row ID (added when you first run `update row`) |
| `forecast_name` | text | Create-new modal |
| `status` | text — "Pending" / null | Submit-for-approval action |
| `submission_comments` | text | Submit-for-approval modal |
| `submitted_by` | text | `CurrentUserEmail()` |
| `submitted_on` | datetime | `Now()` |
| `approval_status` | text — "Approve" / "Deny" / "Change Requested" / null | Final approval modal |
| `approval_comments` | text | Final approval modal |
| `approval_by` | text | `CurrentUserEmail()` |
| `approval_on` | datetime | `Now()` |

## Cross-vertical adaptations

The pattern stays identical; only the grain and what users override changes.

| Use case | Base grain | Override column | Notes |
|---|---|---|---|
| GTM pipeline forecast | `week` (or `month`) | predicted pipeline $ | Reltio's case — additional inputs: ASP, signal weights (separate single-row input tables). |
| Demand planning | `sku × week` | forecast units | Reed's transcript. |
| Headcount / FP&A | `cost_center × month` | headcount, fully-loaded cost | Often paired with a hire-date column users can edit. |
| Marketing spend allocation | `channel × month` | budget $ | Add a "total budget" guardrail input table; surface a violation flag. |
| Capex planning | `project × quarter` | spend $ | Approval is multi-level — extend the registry with `approval_status_l1`, `approval_status_l2`. |
| Supply chain reorder | `sku × location × week` | reorder qty | Often joined to lead-time and on-hand from base; conditional flags rather than free input. |
| Pricing scenarios (Integra) | `product × tier × effective_date` | price, discount % | Lock at "Approve" but also lock at "Effective" once the date passes. |
| Loan loss curves (Newity) | `vintage × months_since_origination` | loss % | Curve shape is the input — users typically tweak inflection points, not every cell. |

## Non-obvious gotchas

These all come from the Reed transcript; document them so the next builder
doesn't hit them.

- **Action order matters and is implicit.** Sigma runs actions in the order
  listed on the button. Clear controls **before** opening modals; set the
  page filter **before** closing the create-scenario modal so the user lands
  on their new scenario.
- **Update-row needs a row ID, and you have to wire it.** Sigma adds the
  hidden ID column the first time you set up an update-row action and click
  "no row ID found." Pass it through to action modals via a hidden control
  that the triggering button populates.
- **Page-filter "include nulls" defaults to true.** On the scenario filter,
  turn this off so a brand-new scenario doesn't show every base row pre-filled.
- **Conditional editing reads as "when allowed" not "when blocked."** State
  the rule in the positive (allow when `!= "Approve"` OR `is null`).
- **`is null` must be in the rule for fresh scenarios.** Otherwise users can't
  edit a scenario they just created (because its approval_status is null,
  which isn't `!= "Approve"` until you wrap it with `OR is null`).
- **The cross-join uses two `1` columns, not `1=1`.** Sigma joins on column
  equality. Add a literal-`1` formula column on each side, then join on those.
- **Linked input tables are immutable in schema after publish.** If you need
  to add columns later, you can — but renaming the primary key is painful.
  Settle on the PK before going live.
- **Audit fields should be set in the same action that changes status.** Not
  in a separate "log writer" action — Sigma actions are not transactional, so
  splitting risks half-writes if a user closes the modal mid-flow.
- **Writeback target schema must be separate from production.** The connection
  config's `writebacks[]` should point at a `sigma_` or `_writeback` schema,
  not the prod marts. This is also what security teams want to see.

## Output expectations

When generating a scenario-modeling workbook spec, you should produce JSON
covering:

1. A `data-models` element with the base series and the scenario registry
   (with all standard audit columns from the table above).
2. A linked input table element with composite PK `(forecast_name, <grain>)`.
3. Three workbook pages: **Sources** (hidden, base + registry), **Scenario
   Editor**, **Approval Flow**.
4. All modals defined: create-scenario, submit-for-approval, final-approval,
   locked-notice.
5. All actions defined on each button/cell trigger, **in correct order**.
6. Conditional editing rules on the linked input table forecast column.

Pair with `sigma-workbook-conventions` for naming and layout, and
`sigma-data-models` for the precise field-level JSON syntax. The exemplar
in `examples/exemplar-spec.json` is a minimal reference — start from it.
