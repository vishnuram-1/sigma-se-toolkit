---
name: sigma-use-cases
description: >
  Generates exactly 10 tailored Sigma data application use cases for a named customer or
  prospect and delivers them as a single-slide branded PowerPoint, with a structured JSON
  written alongside as the supporting source-of-truth artifact. Use this skill whenever
  someone asks to generate use cases for a customer, build a use case slide or deck for a
  named company, identify what apps a prospect could build in Sigma, help a customer imagine
  what's possible with their data, close an "imagination gap", or prepare for a customer
  meeting. Also trigger when the request is phrased as "what could [company] build?", "use
  cases for [company/industry]", "make a use case slide for [company]", "help me prep for a
  meeting with [company]", or "what apps would make sense for [company]?".
---

# Sigma Use Cases

Generates exactly 10 tailored, defensible Sigma use case recommendations for a named customer
or prospect, then renders them into a single-slide branded PowerPoint. The goal is to close
the "imagination gap" — helping customers envision data application possibilities specific to
their industry, grounded in proven patterns from similar organizations, and anchored in
publicly verifiable facts about their business.

**The slide is the deliverable. The JSON is the substrate that populates it.** Every run
produces both: a structured JSON file (the single source of truth) and the PowerPoint slide
built from it. The slide is always the final step — this skill does not ask the user to
choose an output format.

**Output sequence (strict order):**
1. **Prerequisite check** — verify Sigma MCP connection before anything else
2. **Generate JSON** — research, query the data model, and write the full structured JSON file
3. **Render the slide** — populate the branded PPTX template from the JSON
4. **Visual QA + present** — verify the rendered slide, then deliver it

The JSON is written to disk silently and is **not** displayed to the user — it exists to
populate the slide and to support any later re-rendering. Only the PPTX is presented.

---

## Claude Code Environment Notes

This skill was originally authored for the claude.ai app. In Claude Code, use these mappings:

| App primitive | Claude Code equivalent |
|---|---|
| `/mnt/user-data/outputs/` | `$OUTPUT_DIR` — defaults to the current working directory. Write `use-cases-<slug>.json` and `.pptx` there. |
| `ask_user_input_v0` (single_select) | the **AskUserQuestion** tool |
| `present_files([...])` | report the absolute `.pptx` path back to the user as a clickable markdown link |
| `view slide-1.jpg` | the **Read** tool on the JPG (it renders images visually) |
| `/mnt/skills/public/pptx/scripts/office/soffice.py` | local `soffice` (LibreOffice) — see Visual QA section |
| Sigma MCP tools | the `mcp__claude_ai_Sigma_MCP__*` tools (`begin_session`, `query`, `describe`, etc.) |

**Python environment:** prefer the project venv if one is active (e.g. `.venv`).
Install `python-pptx` once with `python3 -m pip install python-pptx -q` (drop
`--break-system-packages`; that flag is Linux-only and errors on macOS).

**Visual QA dependencies (optional):** the QA screenshot step needs LibreOffice + poppler.
If `soffice` / `pdftoppm` are missing, install via Homebrew:
`brew install --cask libreoffice && brew install poppler`. If the user declines, skip the
screenshot and validate the JSON against the schema checklist before presenting.

**`<SKILL_DIR>`** is `~/.claude/skills/sigma-use-cases`.

---

## Prerequisites

### ⚠️ Required: Sigma MCP Connection Check

**Before doing anything else**, verify that the user has the Sigma MCP service configured
and that it is pointing at `https://staging.sigmacomputing.io/sigma-on-sigma`.

Check by attempting to call `mcp__claude_ai_Sigma_MCP__begin_session`. If the call fails,
or if no Sigma MCP connection is available:

> "Before I can generate use cases, I need to connect to Sigma's internal data model.
> It looks like the Sigma MCP service isn't configured yet — or it may not be pointing at
> `https://staging.sigmacomputing.io/sigma-on-sigma`. Could you check your MCP settings
> and make sure that connection is active? Once that's set, we're good to go."

**Do not proceed** until the connection is confirmed.

### Python dependency for slide rendering

`python-pptx` is required for the final slide step (macOS / Claude Code — no
`--break-system-packages`; use the active venv if present):
```bash
python3 -m pip install python-pptx -q
```

---

## Workflow

### Step 1: Identify the target

If the user hasn't named a specific company or industry, ask for one before proceeding.

### Step 1b: Confirm the GTM Sector Industry classification

**Before running any data queries**, query the `Industry Mapping` element (element ID
`x5cOWboOVW`) to retrieve the full list of distinct `GTM_SECTOR_INDUSTRY` values:

```sql
SELECT DISTINCT "GTM_SECTOR_INDUSTRY"
FROM "datamodel"."x5cOWboOVW"
WHERE "GTM_SECTOR_INDUSTRY" IS NOT NULL
  AND "GTM_SECTOR_INDUSTRY" != ' - '
ORDER BY "GTM_SECTOR_INDUSTRY"
```

`GTM_SECTOR_INDUSTRY` is the combined two-level taxonomy string in the form
`"<Sector L1> - <Industry L2>"` (e.g. `"Financial Services - Wealth & Investment Advisory"`).
The model exposes the taxonomy as `GTM_SECTOR_L_1` (level 1), `GTM_INDUSTRY_L_2` (level 2),
and this combined `GTM_SECTOR_INDUSTRY` field; use the combined field for the picker and for
all downstream filtering. The empty-string row surfaces as `" - "` and must be excluded (see
the `WHERE` clause).

Then present the filtered shortlist to the user. Show only the `GTM_SECTOR_INDUSTRY` values
that are **plausibly relevant** to the named company (typically 3–8 options, never the full
list). Use the **AskUserQuestion** tool (single-select) so the user can tap their choice.

Example prompt:
> "Before I pull the data, which industry bucket fits TD Wealth best? This controls which deployed app patterns and peer companies I use as proof points."

**Wait for the user's selection before proceeding to Step 2.** Store the selected
`GTM_SECTOR_INDUSTRY` string — it filters all downstream queries (Deployed Apps, Transcript
App Ideas, peer customer lookup).

**Do not guess or infer the industry from the company name alone.** This step is mandatory
every run, even when the answer seems obvious — the taxonomy is specific enough that
"Banking & Credit Unions" and "Wealth & Investment Advisory" produce very different use case
sets.

### Step 2: Pull data from the Use Case Agent data model

Use Sigma MCP tools to query the **Use Case Agent** data model
(`04a809f7-4b0c-4a22-a9c5-b785a956b68f`; begin a session if needed). All three queries below
filter on the selected `GTM_SECTOR_INDUSTRY` string from Step 1b. The combined-taxonomy column
carries a different opaque ID in each element — use the ID listed for that element:

| Element | Element ID | `Gtm Sector Industry` column ID |
|---|---|---|
| Customers | `BM7y2tpnvg` | `291dfeea9430e0ddf15cad1c16429ab5` |
| Deployed Apps | `oVz40LdBqC` | `wvT0PqSJ3t` |
| Transcript App Ideas | `k5sAh4nWAR` | `7IgHTsQ1gz` |

Run these queries in parallel:

**A. Customer profile lookup** — search the `Customers` element (`BM7y2tpnvg`):
- If found: retrieve AI company summary (`bE7cCBGbUB`), revenue model (`0VEbByN4zj`),
  competitors (`6zRcpCyx8M`), industry classification (`291dfeea9430e0ddf15cad1c16429ab5`),
  data apps use cases (`pKp0Pgnxp0`), IBI/embed use cases (`USfqysFXAr` / `pPp_2V5V7L`),
  org summary (`pKwU3PAq5g`), ARR (`qs_Vq7qoLI`), segment (`sgvPeK8ExH`), and
  org UUIDs (`Si5hh8n42L`).
- If not found: find 1–2 peer companies in the same `GTM_SECTOR_INDUSTRY` bucket.

**B. Deployed Apps by industry** — query the `Deployed Apps` element (`oVz40LdBqC`), filtering
on `wvT0PqSJ3t` = the selected `GTM_SECTOR_INDUSTRY`. Extract titles, departments, use case
types, and solution descriptions from the `Use Cases` column. These are proof points.

**C. Transcript App Ideas by industry** — query `Transcript App Ideas` (`k5sAh4nWAR`),
filtering on `7IgHTsQ1gz` = the same `GTM_SECTOR_INDUSTRY`.

### Step 3: Research the company publicly

Web search for: business model, revenue structure, strategic priorities, competitive
landscape, scale (employees, locations, geographies, revenue if public).

Only assert publicly verifiable facts. Use pattern-based framing otherwise.

### Step 4: Assess capabilities and complexity

Map workflow patterns to Sigma capabilities:
- **Write-back / Input tables**: planning, budgeting, approvals, annotations
  → Grid or Form? Append or Overwrite?
- **File upload + AI parsing**: invoice, contract, receipt, form, image ingestion
- **API Actions**: external system triggers, real-time data fetch, ERP/CRM write-back
- **Embedded analytics**: customer-facing or partner-facing reporting
- **Row-level security**: hierarchical, role-restricted data access

Assess complexity per use case:
- **Simple** (≤2 actors, single state): BUILD notes only
- **Complex** (3+ personas, approval chain, audit requirements): add PRD-lite sketch

### Step 5: Generate exactly 10 use cases and write JSON

Apply workflow selection criteria (see below). For each use case produce the full schema.

**Write the JSON file silently to disk** at:
```
$OUTPUT_DIR/use-cases-<company-slug>.json
```
where `$OUTPUT_DIR` is the current working directory (or a prospect folder the user names).

This is mandatory — it is the source of truth that populates the slide. **Do not display the
raw JSON in the conversation, and do not `present_files` the JSON.** It is an internal artifact;
non-technical users do not need to see it. (It remains on disk so the slide can be re-rendered
later from an edited JSON without regenerating all 10 use cases.)

Schema: see **Use Case Schema** below.

### Step 6: Render the slide

This is the terminal step on every run. Populate the bundled brand template from the JSON.

```bash
python3 -m pip install python-pptx -q

python3 <SKILL_DIR>/assets/generate_from_template.py \
  $OUTPUT_DIR/use-cases-<company-slug>.json \
  $OUTPUT_DIR/use-cases-<company-slug>.pptx
```
(`<SKILL_DIR>` = `~/.claude/skills/sigma-use-cases`)

`<SKILL_DIR>` is this skill's own directory. The template path defaults to
`assets/Use_Case_Template.pptx` beside the script; override with `--template <path>` if needed.

The script automatically:
- Finds the placeholder slide by locating the `{industry}` token (no hard-coded index)
- Fills every `{n_field}` placeholder from the JSON
- Applies the impact-tier color rule (chip + accent bar) per card
- Writes seller talking points into the slide notes pane
- Removes the example slide and the Styles reference slide, leaving a single slide

### Step 7: Visual QA

Requires LibreOffice (`soffice`) + poppler (`pdftoppm`). On macOS `soffice` lives at
`/Applications/LibreOffice.app/Contents/MacOS/soffice`. If either is missing, install with
`brew install --cask libreoffice && brew install poppler`, or skip this step (validate against
the schema checklist instead) if the user prefers not to install them.

```bash
cd $OUTPUT_DIR
SOFFICE=$(command -v soffice || echo /Applications/LibreOffice.app/Contents/MacOS/soffice)
"$SOFFICE" --headless --convert-to pdf use-cases-<company-slug>.pptx
rm -f slide*.jpg
pdftoppm -jpeg -r 150 use-cases-<company-slug>.pdf slide
```

Then **Read** the resulting `slide-1.jpg` (the Read tool renders images). Check for:
- All 10 cards populated with correct data
- No placeholder tokens remaining (`{n_field}`)
- Impact-tier chips and left accent bars colored correctly (see table below)
- Value-tag eyebrows are uniform Sigma blue with **no** background fill
- Text scaled to fit (normAutofit enabled — no overflow)
- Slide title shows the correct industry (not `{industry}`)

### Step 8: Present

Report the absolute path to the finished `.pptx` back to the user as a clickable markdown
link, e.g. `[use-cases-<company-slug>.pptx]($OUTPUT_DIR/use-cases-<company-slug>.pptx)`.

Present **only** the PPTX. The JSON stays on disk as the supporting artifact and is not presented.

---

## Use Case Schema

Every use case must contain all of the following fields. The JSON is the single source of
truth — the slide generator reads directly from it.

### Top-level JSON envelope

```json
{
  "customer": "Company Name",
  "industry": "GTM Sector Industry string (e.g. 'Financial Services - Wealth & Investment Advisory')",
  "segment": "RSM or CAE",
  "arr": 0,
  "generated_at": "YYYY-MM-DD",
  "company_context": "2–3 sentence public summary of the company",
  "org_uuids": ["uuid-1", "uuid-2"],
  "use_cases": [ /* array of 10 use case objects */ ]
}
```

**`org_uuids`** — array of Sigma organization UUIDs for this account.

- **Source**: `All Organization Uuids` column (`Si5hh8n42L`) from the `Customers` element of
  the Use Case Agent data model. Values are ordered by `org_created_at_utc` (oldest first).
- **Mandatory** when a matching row was found in the `Customers` element. If the customer was
  looked up and a row was returned, this field must be populated — omitting it is an error.
- **Omit the field entirely** (do not emit `"org_uuids": null` or `[]`) when no matching row
  existed in the `Customers` element and the output was generated from peer/industry patterns
  only.

### Per-use-case fields

| Field | Type | Description |
|---|---|---|
| `id` | integer | 1–10 |
| `title` | string | Specific, industry-vocabulary name. Max 6 words. No generic consulting language. |
| `value_tag` | string | Pick one: `Revenue growth`, `Cost avoidance`, `Risk avoidance`, `Operations`, `Labor`, `Customer` |
| `impact_tier` | string | Pick one: `High impact`, `Quick win`, `Insight` |
| `value_stat` | object | `{"num": "5–10%", "lbl": "≤6 words naming the source context"}` — industry benchmark only, never customer-specific |
| `card_summary` | string | 1–2 sentences, max 25 words, jargon-free |
| `department` | string | Primary business function(s) |
| `pain_point` | string | Pattern language only — "organizations in this sector often...", never asserts how this company operates |
| `steps` | array of strings | 4–6 workflow step labels for the app workflow flow display |
| `solution` | string | What the Sigma app enables — "could enable", "would allow" framing |
| `writeback_model` | array | `[{"name": "Plain English table name", "description": "one sentence"}]` — 2–5 items |
| `ux_pattern` | string | Named UX pattern(s) and composition |
| `value_case` | object | `{"leading_kpi": "...", "benefit_category": "...", "lagging_financial_kpi": "...", "directional_formula": "..."}` |
| `sigma_components` | array | Subset of: `Input tables`, `File upload`, `API actions`, `KPI cards`, `Data table`, `Embedded analytics`, `Row-level security`, `AI/Cortex` |
| `complexity` | integer | 1–5 |
| `maturity_start` | string | `L0`, `L1`, or `L2` |
| `maturity_target` | string | `L1`, `L2`, or `L3` |
| `file_upload` | boolean | |
| `api_action` | boolean | |

**Note on `value_stat`**: always an object `{num, lbl}`. Never a raw string. The slide reads
`.num` for the large display number and `.lbl` for the muted label beside it.

**Note on `steps` and `solution`**: populate both on every use case. `steps` is a 4–6 label
workflow flow; `solution` describes what the Sigma app enables (do not rely on `ux_pattern` as
a fallback).

---

## Impact Tier Guide

- **High impact**: Large financial exposure, direct P&L line, or operational risk that compounds.
- **Quick win**: High confidence, low implementation complexity, fast time-to-value.
- **Insight**: Analytically rich, less obvious ROI path, but meaningfully improves decision quality.

Aim for roughly 2–3 High impact, 3–4 Quick win, 2–3 Insight across the 10.

Stats must always be framed as industry benchmarks or sector patterns — never as derived from
the specific customer's data.

---

## Task Architecture Guide

For **simple** use cases (complexity 1–2), describe `pain_point` and `solution` in plain
sentences. `steps` array: 4–5 short labels.

For **complex** use cases (complexity 3–5), populate `value_case` with the full structured
object and ensure `steps` covers the full state machine in 5–6 labels.

Reference the Brookfield PRD pattern for financial/regulated workflows: explicit submission
instances, state history tables, multi-step approval cycles, and resubmission logic.

---

## Writeback Model Guide

The `writeback_model` array describes **input tables in plain English** — what gets recorded,
not how it's stored. Written for a VP Finance or Operations leader, not a data architect.

**Format**: 2–5 items. Each: `{"name": "Plain-English table name", "description": "one sentence"}`

Good examples:
- `{"name": "Variance annotations", "description": "where managers record the reason behind each flagged shrinkage event"}`
- `{"name": "Approval decisions", "description": "a permanent record of who approved or rejected each submission, and when"}`

Bad: technical schema syntax, database column names, or implementation details.

---

## UX Patterns

- **Linear wizard**: Sequential steps — submissions, onboarding, filings
- **Hub-and-spoke**: Central list + detail panel — review queues, deal/case/location management
- **Ambient sidecar**: AI narrative alongside a dashboard
- **Focused modal**: High-risk single-record action (approve/reject)
- **Bulk action**: Multi-row select + action
- **Grid edit**: Direct table editing — operational parameters, mass updates

Complex apps are compositions: e.g., "Linear wizard (submitter) + Hub-and-spoke review queue
(Finance) + Focused modal (approve/reject action)"

---

## Value Case Framework

```json
{
  "leading_kpi": "process metric that changes",
  "benefit_category": "Revenue growth | Cost avoidance | Risk avoidance",
  "lagging_financial_kpi": "P&L or balance sheet line it moves",
  "directional_formula": "Volume × (New_rate − Old_rate) × Avg_value  OR  Legacy_process_cost × reduction_%  OR  Exposure_$ × Δ_loss_rate"
}
```

---

## Process Maturity Levels

| Level | Workflow | UX |
|---|---|---|
| L0 | Spreadsheets, email, shared drives | Swivel chair, many screens |
| L1 | Guided app, centralized data, governed | Single screen, minimized clicks |
| L2 | L1 + AI task compression | Proactive, personalized |
| L3 | Sigma Agent, semi-autonomous | Human intervention on exceptions only |

---

## Workflow Selection Criteria

### Prioritize:
- Excel/email workflows living between tech stacks
- High-friction processes lacking good tooling
- Workflows done without governance
- Misaligned-system processes (vendor not built for the sector)
- Hyper-specific sector workflows — not "dashboard" or "reporting"
- Document-driven workflows → `file_upload: true`
- External system orchestration → `api_action: true`
- "Institutionalized pain" — accepted as broken, never optimized
- Multi-player workflows with email/Slack handoffs
- Regulated or audit-sensitive workflows with no governed OLTP layer

### Avoid:
- Use cases competing with the customer's own product
- Streaming/high-frequency workflows
- Core system replacement (ERP, CRM, WMS)
- Generic use cases applicable to any company
- Anything ungroundable in data or public information

---

## Language and Tone Rules

**Card surface**: Direct, specific, data-grounded. No jargon. Written for a business user
scanning a product UI who needs to feel curious within 3 seconds.

**Detail fields**: Field CTO or Industry Principal voice — bridges business operations and
data systems. Executive-ready, not consultant-jargony.

**Never assert** the company operates a specific way. Use pattern language in `pain_point`.

**Solutions**: "could enable", "would allow", "might streamline" — not "will."

**`value_stat.num`**: always a benchmark or sector range. Never customer-specific.

---

## Slide Rendering Reference

The slide is built by `assets/generate_from_template.py`, which populates the placeholder
slide of `assets/Use_Case_Template.pptx` (Sigma 2026 brand, 10" × 5.62" / 16:9). All fonts,
spacing, logo, card layout, and color system come from the template — the script only fills
`{n_field}` placeholders and applies one per-card styling rule: impact-tier color coding.

### Placeholder tokens (per card, n = 1–10)

| Token | Source field |
|-------|-------------|
| `{industry}` | `industry` (slide title, card-independent) |
| `{n_impact_tier}` | `impact_tier` (normalized to `HIGH IMPACT` / `QUICK WIN` / `INSIGHT`) |
| `{n_id}` | `id` |
| `{n_title}` | `title` |
| `{n_card_summary}` | `card_summary` |
| `{n_value_stat_num}` | `value_stat.num` |
| `{n_value_stat_lbl}` | `value_stat.lbl` |
| `{n_department}` | `department` |
| `{n_ value_tag}` | `value_tag` (note: **leading space** inside the token — preserved from template) |

**Card order in template XML**: card groups appear in visual column order
(1, 2, 6, 7, 3, 4, 8, 9, 5, 10). The script resolves this by reading the `{n_id}` token from
each group — do not assume positional order.

### The one styling rule: impact-tier color coding

The tier value drives four things per card — chip fill, chip border, chip text, and the left
accent bar. `{n_impact_tier}` must be exactly one of: `HIGH IMPACT` · `QUICK WIN` · `INSIGHT`.

| Impact tier | Chip fill | Chip border | Chip text | Left accent bar |
|---|---|---|---|---|
| `HIGH IMPACT` | `#1A70F1` | `#1A70F1` | `#FFFFFF` | `#1A70F1` |
| `QUICK WIN` | `#EEF3FF` | `#DCE6FE` | `#1660D6` | `#7FA8F0` |
| `INSIGHT` | `#FFFFFF` | `#D6D6DB` | `#5F5F66` | `#C9C9D0` |

The script normalizes any non-canonical `impact_tier` string to one of the three values. If a
runtime can't set shape fills, the script still fills the text and the card shows the shipped
default (pale-blue chip + blue accent) — on-brand, only the at-a-glance tier coding is lost.

### Leave everything else as shipped

Card surface (white `#FFFFFF`, `1px #E5E5E9` border on `#F4F5F7` background), stat panel
(`#EEF3FF` fill; number `#1A70F1`, label `#5F5F66`), value-tag eyebrow (`#1A70F1`, **no**
background fill), card title `#111114`, summary `#5F5F66`, id & department `#8B8B92`, slide
title in Instrument Serif, body in DM Sans — all pre-styled and identical on every card. Do
not recolor per tier.

### Updating the template

To change layout, fonts, spacing, logo, or card design: open
`assets/Use_Case_Template.pptx`, edit the placeholder slide (keep all `{n_field}` tokens
intact, including the leading space inside `{n_ value_tag}`), save, and replace the file. No
code changes needed if the per-card shape order (indices 0–12) is preserved. If shapes within
a card group are reordered, update the `IDX_*` constants at the top of
`generate_from_template.py`.

### Fallback: scratch generator

`assets/generate_slide.py` is a fully programmatic scratch builder (no template dependency).
Use only if the template file is unavailable. Its output predates the 2026 brand template — it
matches Sigma brand tokens but **not** the current template typography or tier-only color
model. Prefer `generate_from_template.py` in all normal cases.

---

## Data Source Reference

The **Use Case Agent** data model (`04a809f7-4b0c-4a22-a9c5-b785a956b68f`, via Sigma MCP):
- **Customers** (`BM7y2tpnvg`): Profiles with AI summaries, use case arrays, ARR, industry classification, org UUIDs
- **Deployed Apps** (`oVz40LdBqC`): Production apps by real customers — most credible proof points
- **Transcript App Ideas** (`k5sAh4nWAR`): What prospects actually ask for in sales calls
- **Industry Mapping** (`x5cOWboOVW`): GTM taxonomy for peer-group matching. Two-level
  hierarchy — `GTM_SECTOR_L_1` (level 1), `GTM_INDUSTRY_L_2` (level 2), and the combined
  `GTM_SECTOR_INDUSTRY` ("<Sector L1> - <Industry L2>"). Use `GTM_SECTOR_INDUSTRY` as the
  filter key. The legacy `GTM_INDUSTRY_L_1_L_2` column no longer exists.

---

## Quality Checks Before Finalizing

- [ ] Sigma MCP prerequisite confirmed before any data queries
- [ ] GTM Sector Industry confirmed via user selection (Step 1b) — never inferred
- [ ] Exactly 10 use cases in the JSON
- [ ] JSON written to disk **silently** — not displayed or surfaced to the user
- [ ] `org_uuids` populated when a `Customers` row was found — field omitted entirely (not null/empty) for prospect-only runs
- [ ] Every `value_stat` is `{num, lbl}` object — industry benchmark, never customer-specific
- [ ] `impact_tier` mix: roughly 2–3 High impact, 3–4 Quick win, 2–3 Insight
- [ ] `value_tag` covers at least 3 different categories across the 10
- [ ] `card_summary` is ≤25 words and jargon-free
- [ ] `steps` array populated for every use case (4–6 labels)
- [ ] `solution` field populated for every use case
- [ ] `writeback_model` uses `{name, description}` objects — plain English, no schema syntax
- [ ] `pain_point` uses pattern language — never asserts how this company operates
- [ ] `sigma_components` array populated for all 10
- [ ] No two use cases are the same workflow with different names
- [ ] 2–3 reference specific deployed app patterns from the data model
- [ ] No use case competes with the customer's own product
- [ ] All company-specific facts are publicly verifiable (or framed as patterns)
- [ ] Slide generator runs without error; visual QA image reviewed — all 10 cards populated
- [ ] No `{n_field}` placeholder tokens remaining in the slide
- [ ] Impact-tier chips and left accent bars colored correctly per tier
- [ ] Value-tag eyebrows are uniform `#1A70F1` with no background fill
- [ ] Output is a single slide (example + Styles slides removed)
- [ ] Only the PPTX presented (as a path/link); JSON not presented
