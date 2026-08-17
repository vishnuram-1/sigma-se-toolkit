# The six passes

Run these over the transcripts after gathering. Each pass fills specific sections of
the output contract. Every item lands with a citation or it doesn't land.

## Pass 1 — People and what each one owns

Collect distinct external speakers plus anyone named in the third person. For each:
role, and **what they own** — not just a title. "Philippe Papillon (AttriX) —
technical, owns tenant/security model" is useful; "Philippe, technical" is not.

Separate Sigma-side (AE, SE) from prospect-side. Mark the champion and the economic
buyer if either is identifiable; if not, that absence is an Open question, because a
POV with no named decision maker is a risk worth writing down.

→ *Deal logistics*

## Pass 2 — The analytic problem

What are they actually trying to do, in their own words? Prefer a verbatim quote over
your paraphrase — quotes survive re-reading and paraphrases drift.

Then enumerate the concrete assets: the named dashboards, reports, or apps in play.
Number them; later sections cite the numbers.

→ *Use case*

## Pass 3 — Scope and non-scope

The judgment pass, and the one that makes the document worth writing.

From the assets in Pass 2, decide what the POV delivers. Prioritize by *risk × value*:
lead with the asset that exercises the hardest requirement, because that's what the
POV is really testing. AttriX leads with EcoDriving over Speeding for exactly this
reason — "it's the higher-risk, higher-value asset and exercises every hard feature".

Then write down what it will **not** cover. An unwritten non-scope becomes scope by
default halfway through the build.

Both sections carry citations. If the calls don't support a scope decision, say so and
put the question in Open questions rather than inventing a plan.

→ *Scope for this build*, *Out of scope for first pass*

## Pass 4 — Data shape

Every database, schema, table, and column mentioned. Then, if the warehouse is
reachable, **measure them** — grain, row count, keys, null rates — and write the
numbers down. Title the section with the source: `Data shape (from LookML)`,
`(from CSV)`, `(from live BigQuery)`.

Mentioned-but-unverified and measured are different epistemic states. Keep them
visibly apart.

→ *Data shape*

## Pass 5 — Complexity

What is genuinely hard here? Period-over-period engines, row-level security and tenant
isolation, write-back, custom visuals, parameter-driven dashboards, volume.

Number each item (`§1`, `§2`, …) so Scope can cite them. Where a BI artifact exists,
this comes from the `*-assessment` skill's coverage framework, not from intuition.

For each: what it is, why it's work, and whether it's make-or-break. "Rebuild tenant
and group row-level security on Sigma user attributes — this is the make-or-break
requirement" tells a reader where to spend their attention.

→ *Complexity — what's real work*

## Pass 6 — Blockers, prior work, open questions

Three related sweeps:

- **Prerequisites & blockers** — what must be true before the clock starts, each with
  a named owner and, where stated, a date. Sigma-side setup counts.
- **Already built** — search for "I built", "the view I created", "the dashboard we
  showed". Cross-check against `/v2/files` if the org is reachable. This prevents
  rebuilding something that exists.
- **Open questions** — anything flagged, pushed back on, or left unresolved, plus
  every gap the passes above hit. This section being empty means you weren't reading
  carefully.

→ *Prerequisites & blockers*, *Already built*, *Open questions*

## When the calls are thin

Many prospects have one discovery call and no artifact. Write the skeleton honestly:
fill what the call supports, leave sections with a single line saying what's missing
and which question would fill it. A short accurate brief that names its gaps is more
useful than a long one that hides them behind confident prose.

Do **not** pad from `sigma-use-cases` output and present it as scope. If you use it for
ideas, mark them as ideas, in Open questions.
