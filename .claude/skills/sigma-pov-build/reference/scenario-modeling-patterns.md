# Scenario / what-if patterns

Salvaged from a `sigma-scenario-modeling` skill that used to live here. The
**build mechanics** — input tables, linked input tables, modals, button actions,
the Submit → Approve lifecycle — are covered better and kept more current by
`sigma-input-table-app` in the [millersigma](https://github.com/cmiller-coder/millersigma)
plugin marketplace:

```
/plugin marketplace add cmiller-coder/millersigma
```

What that skill doesn't have is the scoping judgement below: whether a prospect's
ask is actually this shape, and what the grain should be for their vertical.

## Is it this shape?

Treat it as a scenario-modeling app only when **all four** hold:

1. There's a **base series** with a primary grain — usually date, but often
   `account × period`, `sku × week`, `cohort × month`.
2. Users create **multiple named alternatives** (forecasts, plans, what-ifs)
   that override or extend that base series.
3. Users **enter values** directly in Sigma rather than filtering a dashboard.
   This is write-back territory.
4. There's an **approval / lock state** — once approved, a scenario isn't
   silently editable; changes need a new revision or an explicit unlock.

If only 1 and 2 hold — read-only comparison of pre-computed scenarios — this is
the wrong shape. Add a `scenario` dimension to the data model instead.

If 1–3 hold but not 4, it's an adjustment/write-back app, not scenario
modeling. Simpler: no registry, no lock rules.

## Grain by vertical

The pattern is identical across these; only the grain and the override column
change. Getting the grain wrong is the expensive mistake — it's the thing to
confirm at scoping, not during the build.

| Use case | Base grain | Override column | Notes |
|---|---|---|---|
| GTM pipeline forecast | `week` or `month` | predicted pipeline $ | Additional inputs (ASP, signal weights) belong in separate single-row input tables |
| Demand planning | `sku × week` | forecast units | |
| Headcount / FP&A | `cost_center × month` | headcount, fully-loaded cost | Usually paired with an editable hire-date column |
| Marketing spend allocation | `channel × month` | budget $ | Add a total-budget guardrail input table and surface a violation flag |
| Capex planning | `project × quarter` | spend $ | Approval is multi-level — the registry needs `approval_status_l1`, `_l2` |
| Supply-chain reorder | `sku × location × week` | reorder qty | Join lead-time and on-hand from the base; prefer conditional flags over free input |
| Pricing scenarios | `product × tier × effective_date` | price, discount % | Lock on approve **and** on effective date once it passes |
| Loan loss curves | `vintage × months_since_origination` | loss % | The curve shape is the input — users tweak inflection points, not every cell |

## Scoping questions this implies

Ask these before promising a scenario app:

- What is the grain, exactly? One row per what?
- Who enters values, and who approves? Same person, or a separate approver?
- What happens to an approved scenario when the underlying actuals change?
- How many scenarios live at once — a handful, or one per user per quarter?
- Is there a guardrail (total budget, headcount cap) that scenarios must respect?
