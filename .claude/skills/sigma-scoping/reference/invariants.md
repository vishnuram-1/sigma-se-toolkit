# Citation discipline and the don't-invent rules

The old recipe could rely on a `scoping.docx` as the anchor: anything not in the doc
was, by definition, unconfirmed. **That anchor does not exist** — no prospect folder
has a docx. Without it, the only thing standing between a scoping doc and confident
fiction is the discipline below. `scripts/check_scoping.py` enforces the mechanical
parts; the rest is judgment.

## Every claim carries its source

Two accepted forms:

- `(Sigma Connect: HPC, 2026-03-16)` — a call, by title and date
- `(LookML/fct_speeding_behavior.view.lkml)` — an artifact, by path

Where it goes: at the end of the bullet, or once per subsection if every bullet in it
shares a source. The provenance header covers the document as a whole and does **not**
excuse per-claim citations in Scope.

What doesn't need one: your own structural prose, and section headings.

## The quarantine rule

Anything you can't cite goes under **Mentioned on calls — confirm** — never into
Prospect, Use case, Scope, or Data shape.

This is the rule that does the work. A transcript hint ("we'd love to do forecasting
eventually") is not a commitment, and once it appears in Scope with no citation, the
next reader — possibly you, in three weeks — cannot tell it apart from something the
prospect actually agreed to.

## Never invent

- **Names.** If a role was mentioned without a name, write the role. Don't guess from
  a speaker label, and don't infer someone's employer from context.
- **Tables and columns.** Only what appears in a transcript, an artifact, or the
  warehouse. A plausible-sounding `dim_customer` that nobody said is a fabrication that
  will surface as a build failure later.
- **Numbers.** Row counts, volumes, and timelines get written down only if measured or
  stated. "Roughly 44M rows" needs to come from somewhere.
- **Scope.** Covered above, and the one that costs the most when it's wrong: it becomes
  a commitment to a customer.

## Don't compress the evidence

Keep the quote verbatim where it justifies a decision. `sigma-pov-build`'s own guidance
is that these are audit trail. A paraphrase loses the hedge — "we're probably going to
replace Tableau" and "we're replacing Tableau" are different deals.

## State what you did not have

The provenance header names the sources used **and** the ones that weren't available:

> Source: Gong call "Attrix x Sigma - Data Review" (2026-07-20) and the
> customer-provided LookML extraction in LookML/ … No formal scoping.docx.

A reader has to be able to distinguish "asked, and the answer was no" from "never came
up". Silence about a gap reads as coverage.

## Never overwrite the user's file

`scoping.md` is user-owned — `sigma-pov-build/reference/folder-layout.md` marks it
read-only even to the build flow. Write `scoping.generated.md` and show a diff. Let the
user promote it. Re-running is only safe if it can't destroy a hand edit, and this
document is explicitly a living artifact that will be re-run.
