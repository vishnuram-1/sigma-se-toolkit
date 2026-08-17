# Sources, ranked

What a scoping doc can be built from, best first. Work down the list and stop when
you have enough; record in the provenance header what you used **and what you didn't
have** — a reader needs to know whether "no RLS requirement" means "asked and no" or
"never came up".

## 1. Gong transcripts — `context_<Name>.txt`

The only universal source (51 of 58 folders have this and nothing else).

Format is one call per block, newest first. The first line of each block is
tab-separated metadata:

```
{date}\t{title}\t{duration} min\t{opportunity}\t{owner}
```

followed by one speaker turn per line, `Name (Sigma|External|Unknown): text`.
A block with no body lines is a placeholder — Gong hadn't transcribed it yet.

Read the two or three most recent calls in full; grep older ones for specifics.
The newest call wins on any contradiction — deals change.

```bash
grep -n $'^[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}\t' context_*.txt   # call index
```

## 2. A data artifact in the folder

This is what separates a real scoping doc from a call summary. Look for:

| Artifact | Where | Gives you |
|---|---|---|
| LookML | `LookML/`, `reference/` | Data shape and a real complexity read |
| dbt artifacts | `reference/` | Models, tests, lineage |
| CSV extracts | `reference/`, `mockups/` | Column names, grain, actual values |
| HTML mockups | `mockups/` | What they expect to see — feeds Scope directly |
| Manual exports | `reference/context_manual_export.txt` | Calls Gong missed |

When the artifact is a BI export, **delegate the complexity read** to the matching
`*-assessment` skill rather than eyeballing it. AttriX's "Migration complexity"
section came from running ~8k lines of LookML through the looker-to-sigma coverage
framework, and it is the most useful section in that document.

## 3. The prospect's Sigma org — needs `.env`

Only 4 folders have credentials today, but where they exist this answers a question
transcripts answer badly: **what has the AE already built?**

```bash
cd <prospect folder>
bash scripts/api/whoami.sh          # confirm auth + org
sigma_curl "$SIGMA_BASE_URL/v2/files?limit=200"                # what exists already
bash scripts/api/list-connections.sh # warehouse actually wired up?
```

Everything found here goes under "Already built — check before duplicating" and into
Prerequisites (a missing connection is a blocker with a named owner, not a detail).

Credentials arrive as `SIGMA_BASE_URL` / `SIGMA_CLIENT_ID` / `SIGMA_CLIENT_SECRET` /
`SIGMA_API_TOKEN` already exported. Use them; never read `.env`, never print them.

## 4. The live warehouse — where a connection exists

The highest-value source and the most often skipped. It converts *tables mentioned on
a call* into *tables measured*: grain, row count, key columns, null rates, fan-out.

Use the Sigma MCP `describe` / `query` tools, or `scripts/api/probe-schema-tables.sh`
and `list-table-columns.sh`. `sigma-pov-build/reference/warehouse-overview.md` already
specifies how to do this — follow it, because doing it here means its Gate 2 arrives
with the work already done.

Anything measured belongs in **Data shape** with the number attached. Anything merely
said belongs in Open questions.

## 5. The generated opp summary

If Prospect Console has one cached, it is already structured — stage, people, useCase,
warehouse, commercials, risks, openQuestions — and derived from the same transcripts.
Use it as a first draft skeleton to check yourself against, not as evidence: it is a
model's reading, so anything it asserts still needs a citation from the source.

## 6. Slack, Gmail, Glean — session only

`sigma-pov-build` describes scoping as built partly from these. They are reachable in
a terminal Claude Code session and **not** from Prospect Console, which disables MCP.
If you are running in the app and the calls leave a gap those would fill, say so in
Open questions rather than guessing.
