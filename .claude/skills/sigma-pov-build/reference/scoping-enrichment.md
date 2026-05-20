# Scoping enrichment

`scoping.md` is a **living artifact** — not a one-shot conversion. It starts from a `.docx` the user filled out with the prospect and gets continuously enriched with context from Gong calls.

## When to regenerate

Regenerate `scoping.md` when ANY of:
- `scoping.docx` is newer than `scoping.md`
- `scoping.md` is missing entirely
- New entries in `context_<Name>.txt` since the last regeneration (mtime comparison)
- User explicitly asks

If none of these are true, the existing `scoping.md` is current — don't touch it.

## Conversion: .docx → .md

Use the wrapper script (handles fallback automatically):

```bash
~/Prospects/vish-gong-test/.claude/skills/sigma-pov-build/scripts/convert_docx.sh \
  prospects/prospect_<Name>/scoping.docx
```

Order of preference inside the script:
1. **`pandoc`** if installed — best fidelity, preserves tables and formatting.
2. **`textutil`** (macOS built-in) — falls back to HTML → strip to markdown. Tables get flattened to text; usually fine for scoping docs.

If neither works, the script writes a stub `scoping.md` pointing at the raw `.docx` and prompts the user to install pandoc (`brew install pandoc`).

## Enrichment passes

After raw conversion, layer in context from the Gong transcript. Pass-by-pass:

### Pass 1: Stakeholders
Scan transcripts for distinct external speakers. For each one mentioned in the scoping doc by role (e.g. "Head of Finance"), backfill the name. New names not in the scoping doc go under a "Mentioned on calls" subsection.

### Pass 2: Decisions and changes
Search transcripts for:
- Pricing / commercial discussions
- Data model changes ("we added a unique interaction ID")
- Tooling decisions ("we're going to replace Tableau")
- Timeline shifts

Add a dated bullet under a "Decisions since scoping doc" section.

### Pass 3: Blockers and open questions
Anything the prospect flagged as needing clarification, blocked on, or pushing back on. Surface explicitly under "Open / blockers" — these are what the user (Vishnu) needs to chase.

### Pass 4: Existing AE work
Look for mentions of "I built", "the view I created", "the dashboard we showed", etc. Note as "Already built — check before duplicating: <description>". This drives the `GET /v2/workbooks` check before any new build.

### Pass 5: Data references
Capture every database / schema / table / column name mentioned. These feed directly into the data model build (`reference/data-model-build.md`).

## Output structure

Generated `scoping.md` should follow this order:

```markdown
# <Account> — Scoping

> Last enriched: YYYY-MM-DD from scoping.docx (mtime YYYY-MM-DD) + <N> Gong calls.

## Account
- Account name, industry, current tooling, replacement target
- Decision criteria

## Use case(s)
- The core analytic problem in plain English
- Data sources, volumes, time range

## Stakeholders
| Role | Name | What they care about |

## Decisions since scoping doc
- YYYY-MM-DD: <decision>, surfaced on <call title>

## Open / blockers
- <blocker>, raised on <call title>

## Already built (check before duplicating)
- <description>, mentioned on <call title>

## Data references
- Table: <name>
- Columns: ...
- Quirks: ...

## Priority artifacts to build
1. Data model: <name> — purpose
2. Workbook: <name> — pages, KPIs
```

## What NOT to invent

- **Don't invent scope.** If the scoping doc doesn't mention a use case, the transcript alone is not enough to add it as "priority artifact." Surface it under "Mentioned on calls — confirm with Vishnu" instead.
- **Don't invent stakeholder names** if they're not in transcripts.
- **Don't compress.** Keep transcript quotes verbatim when they justify a decision — they're audit trail.
