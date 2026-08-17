---
name: sigma-scoping
description: >-
  Use when the user wants a scoping.md written or refreshed for a specific
  prospect — the POV brief that sigma-pov-build treats as its prerequisite.
  Builds it from the Gong transcripts in context_<Name>.txt, any data artifact
  in the folder (LookML, dbt, CSV, mockups), and — where credentials exist —
  the prospect's live Sigma org and warehouse. Triggers on "build the scoping
  doc for <name>", "write scoping for <name>", "refresh <name>'s scoping",
  "draft a POV brief for <name>", or a request to run sigma-pov-build against a
  prospect that has no scoping.md yet.
---

# sigma-scoping

Produces `scoping.md` — the POV brief `sigma-pov-build` halts without. Everything
in it is derived from evidence already on disk or in the prospect's org, and every
claim carries the call it came from.

## When to use

- A prospect has calls but no `scoping.md` (51 of 58 folders today).
- An existing `scoping.md` is stale — new calls have landed since it was written.
- `sigma-pov-build` halted at its scoping prerequisite.

Not for: generating use-case ideas (`sigma-use-cases`), or assessing a source BI
instance (the `*-assessment` skills — though this skill delegates to them).

## Start here: there is no scoping.docx

An earlier version of this workflow assumed a `.docx` the user filled in with
the prospect, converted and then enriched. **No prospect folder has one**,
`pandoc` often isn't installed, and the best existing docs say so themselves
("No formal scoping.docx"). Assume you are writing from transcripts and
artifacts. `scripts/convert_docx.sh` remains available for the rare case where
a prospect actually supplies one as a seed.

The consequence matters: with no doc to diff against, "don't invent scope" has
nothing to push against except discipline. See `reference/invariants.md`.

## Workflow

```
1. Gather   — transcripts, folder artifacts, org, warehouse   (reference/sources.md)
2. Draft    — six passes into the output contract             (reference/passes.md)
3. Verify   — scripts/check_scoping.py, fix every finding
4. Hand off — scoping.generated.md + a diff, never an in-place overwrite
```

**Never overwrite `scoping.md` directly.** It is the user's file — `sigma-pov-build`'s
folder-layout reference marks it user-owned. Write `scoping.generated.md` alongside
it and show a diff. On a first run for a folder with no scoping at all, say so and
offer to promote it with `mv`. This is what makes "living artifact" safe to re-run.

## Output contract

Follow the structure of the prospect docs that actually worked
(`prospect_AttriX_Technologies/scoping.md`, `prospect_Gnosis_Freight/scoping.md`),
not the older template. Full spec with a worked example in `reference/structure.md`:

```
# <Account> — POV Scoping
> Source: <exact calls, artifacts, org reads> — state what you did NOT have.

## Prospect                      identity, industry, current BI, warehouse, deployment model
## Deal logistics                shape, timeline, commitment, named people and what each owns
## Use case                      the analytic problem in plain English, numbered assets
## Scope for this build          what the POV will actually deliver, prioritized
## Out of scope for first pass   what it deliberately will not
## Data shape (from <source>)    tables, grain, keys — cite where this came from
## Complexity — what's real work numbered §, so later sections can cite "see Complexity §2"
## Prerequisites & blockers      what must be true before the clock starts, and who owns it
## Open questions                what to ask on the next call
```

The two sections the old template lacked — **Scope for this build** and **Out of
scope** — are the ones that make a POV finishable. Don't drop them.

## Invariants

1. **Every claim cites its source.** `(call title, YYYY-MM-DD)` or the artifact path.
   Anything uncited goes under "Mentioned on calls — confirm", never into Scope.
2. **Never invent scope, names, or tables.** A transcript hint is not a commitment.
3. **Never overwrite `scoping.md`.** Generate alongside; the user promotes.
4. **Never read or echo `.env`.** Credentials reach you through the environment.
5. **Measured beats asserted.** If the warehouse is reachable, a row count belongs
   in Data shape instead of a table name someone said out loud.

## Reference

- [`reference/sources.md`](reference/sources.md) — what to draw on, ranked, and how to reach each
- [`reference/structure.md`](reference/structure.md) — the output contract, section by section, with a worked example
- [`reference/passes.md`](reference/passes.md) — the six extraction passes over the transcripts
- [`reference/invariants.md`](reference/invariants.md) — citation discipline and the don't-invent rules

## Scripts

- [`scripts/check_scoping.py`](scripts/check_scoping.py) — verifies a generated doc against its
  evidence: every person named must appear in a transcript, every table must appear in a
  transcript or artifact, every Scope bullet must carry a citation. Run it before handing off;
  treat findings as blocking.

## Composition

| Concern | Skill |
|---|---|
| Consuming the result — data model + workbook build | `sigma-pov-build` |
| Complexity read when the artifact is a BI export | the matching `*-assessment` skill (looker, powerbi, qlik, cognos, gooddata, microstrategy, quicksight) |
| Auth for org/warehouse reads | `sigma-api`, plus `scripts/api/*.sh` |
| Ideas for "priority artifacts" when the calls are thin | `sigma-use-cases` |
| The rare `.docx` seed | `scripts/convert_docx.sh` |

The AttriX doc is the standard to hit: its complexity read came from running an 8k-line
LookML extraction through the looker-to-sigma coverage framework. A transcript gives you
the narrative; an artifact gives you the data shape. Go find the artifact.
