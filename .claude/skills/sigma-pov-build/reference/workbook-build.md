# Workbook build

Map `scoping.md` + the deployed data model → a Sigma workbook spec. Same approval discipline as data-model-build.md.

## Inputs

From `scoping.md`:
- **Stakeholders** — one page per stakeholder concern is the default layout.
- **Priority artifacts** — explicit page asks (often: "Pipeline Signal", "Channel Effectiveness", etc.).
- **Open / blockers** — anything blocking visualization (e.g. missing ASP input) goes into Input Tables on a dedicated page.

From the data model:
- The model's `id` (captured during data-model build).
- Available metrics + dimensions — only these can be referenced.

From the prospect's Sigma org:
- `GET /v2/workbooks?search=<account>` — does the AE already have a workbook for this prospect? If yes, decision: extend or replace. Default to extend (less destructive).

## Default page layout

Page-per-stakeholder is the default. Within each page, top-to-bottom:

1. **KPI tiles row** — 3–5 headline numbers the stakeholder cares about.
2. **Trend chart** — primary metric over time.
3. **Breakdown** — bar / pivot by the most relevant dimension.
4. **Detail table** — row-level data with filters.

Adjust based on the stakeholder. Finance leaders skew toward forecast/scenario pages with Input Tables. Marketing leaders skew toward channel + campaign breakdowns. Sales/BDR leaders skew toward account- and territory-level views.

## Build sequence

1. **Pre-check for existing artifacts.** `GET /v2/workbooks?search=<account>` and read the result. If something exists, present it to the user — extend or build new?

2. **Draft the spec.** Defer to `sigma-workbook-conventions` for:
   - Element naming conventions
   - Page / folder layout rules
   - Create-vs-update ID semantics (the big footgun)
   - Secret handling in workbook params

3. **Apply page-per-stakeholder layout** unless scoping says otherwise.

4. **Write to disk.** `prospects/prospect_<Name>/workbooks/<name>.json`. Slugified name.

5. **Show the user.** Summary: page list, KPI tiles per page, where Input Tables sit, any Sigma Agent configuration. Pause. Gate 5.

6. **POST.** On approval:
   ```bash
   curl -X POST "$SIGMA_BASE_URL/v2/workbooks" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     --data @workbooks/<name>.json
   ```
   Capture `id` into the spec's `_metadata` block.

7. **Verify.** `GET /v2/workbooks/{id}` — check page count, element count. Gate 6.

## Updates

For an existing workbook (spec has `_metadata.id`):
- Use `PUT /v2/workbooks/{id}`.
- `sigma-workbook-conventions` covers ID handling for nested elements — pages, elements, controls. POST treats `id` fields differently than PUT does. Read that skill before any update pass.

## Demo-readiness checklist

Before declaring a workbook done, walk through:
- [ ] Every KPI tile resolves to a non-null number when the workbook loads
- [ ] Every page has a clear name (no `Page 2`, `Untitled Element`)
- [ ] Filters at the top of each page actually filter every element on the page
- [ ] Any Input Tables have sensible default values
- [ ] If Sigma Agent is configured, it's pointed at the right data model and has clear instructions
- [ ] Page-load time on the heaviest page is under ~5 seconds (slow loads kill demos)

## What we don't build by default

- **Embed portals** — out of scope for this skill. Use the `sigma-embed-portal` skill if the prospect needs a branded portal.
- **Multi-workbook applications** — if the use case spans 3+ workbooks, that's a "data app" pattern. Ask the user before splitting.
