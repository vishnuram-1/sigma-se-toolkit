# The output contract

Derived from the two prospect docs that actually carried a POV —
`prospect_AttriX_Technologies/scoping.md` (181 lines) and
`prospect_Gnosis_Freight/scoping.md` (85) — not the older template, which lacked
Scope, Out of scope, and Complexity entirely.

**Length follows the evidence.** AttriX earned 181 lines because an 8k-line LookML
extraction sat behind it. A single discovery call earns ~40. Padding to look thorough
is a failure, not a courtesy.

| Section | Holds | Notes |
|---|---|---|
| Header + `> Source:` | Every source used **and** what wasn't available | "No formal scoping.docx" is a real and useful line |
| `## Prospect` | Identity, industry, current BI + stated pain in their words, warehouse, org status, deployment model | Call out embedded/multi-tenant on its own line — it changes the whole build |
| `## Deal logistics` | Shape, timeline and what gates the start, customer hours, Sigma-side prerequisites, people | Each person gets **what they own**, not a title |
| `## Use case` | The problem in plain English, then numbered assets | Mark net-new vs parity — different risk, different proof value |
| `## Scope for this build` | What the POV delivers, prioritized, with the reasoning for the order | Lead with the asset exercising the hardest requirement. Cite `see Complexity §N` |
| `## Out of scope for first pass` | What it deliberately won't cover | Short and blunt. Unwritten non-scope becomes scope by default |
| `## Data shape (from <source>)` | Tables, grain, keys, quirks that will bite | Title carries the source. Measured and merely-mentioned stay visibly apart |
| `## Complexity — what's real work` | Numbered §. Each: what, why it's work, make-or-break? | Where a BI artifact exists this comes from the `*-assessment` coverage framework |
| `## Prerequisites & blockers` | What must be true before the clock starts | Named owner each. Sigma-side setup counts |
| `## Already built` | What the AE or prospect already made | Transcripts cross-checked against `/v2/files`. Omit if genuinely nothing |
| `## Open questions` | What to ask next call, plus every gap the passes hit | Empty on a thin corpus means the passes weren't run carefully |
| `## Mentioned on calls — confirm` | The quarantine | Uncited items live here, with the quote, never in Scope |

## Worked example

`prospect_AttriX_Technologies/scoping.md` is the standard. Read it before writing a
new one. What makes it work:

- Provenance header states what was **missing**, not just what was used
- *"Embedded, multi-tenant … tenant isolation is a hard requirement, not a nicety"* — deployment model as a first-class constraint
- People carry ownership (*"owns tenant/security model"*)
- Three numbered assets, the net-new one marked
- Scope explains its **ordering** — *"the higher-risk, higher-value asset and exercises every hard feature"* — and cross-references Complexity
- `Data shape (from LookML)` — sourced in the heading, not asserted
- Complexity numbered, with the make-or-break item flagged explicitly
