# sigma-se-toolkit

SE toolkit for managing prospects end-to-end: a set of Claude skills for building Sigma data models, workbooks and POVs, plus a nightly Gong call sync that keeps per-prospect transcripts on disk for Claude to read.

This repo is a **template** — click **"Use this template"** at the top of the GitHub page to get your own independent copy. Your copy shares no history with this one, and your transcripts never touch anyone else's repo.

> **Keep your copy private.** It will accumulate verbatim customer call transcripts, and they persist in git history permanently. The 90-day prune is hygiene, not a retention control.

---

## The two halves

The skills are useful on their own and need no setup at all. The Gong sync needs credentials and access. Do them in either order.

| | What you get | Setup cost |
|---|---|---|
| **Part 1 — Skills** | Claude skills for the Sigma API, data models, workbook conventions, POV builds | ~5 min, no dependencies |
| **Part 2 — Gong sync** | `prospects/<account>/context_<account>.txt`, refreshed nightly | ~15 min, needs Sigma API creds + access to the shared workbook |

---

## Part 1 — Skills

```bash
git clone https://github.com/<your-org>/<your-repo>.git
cd <your-repo>
scripts/install-skills.sh
```

That symlinks every skill into `~/.claude/skills/`, so they load from **any** directory rather than only when Claude Code is started from inside this repo. Re-run it any time to refresh the upstream ones.

```bash
scripts/install-skills.sh --list       # show what points where
scripts/install-skills.sh --own-only   # skip the upstream clones
scripts/install-skills.sh --uninstall  # remove only the links it created
```

### Maintained here

| Skill | What it covers |
|---|---|
| `sigma-pov-build` | The POV workflow: read scoping → ground in the live warehouse → data model → workbook, with six approval gates before any write |
| `sigma-scoping` | Writes `scoping.md` from Gong transcripts and whatever data artifacts the prospect folder holds |
| `sigma-use-cases` | Ten tailored use cases for a named prospect, as a branded single-slide deck |
| `sigma-scenario-modeling` | Scenario / what-if apps built on input tables |
| `sigma-fin-recon` | Reconciliation workbooks (GL tie-out, bank recon, variance). Its exemplar spec is still a placeholder — see the skill's own note. |

### Installed from upstream

These are **not** vendored here. They belong to other repos, and the installer clones them so `git pull` is the update path.

| Skill | Upstream |
|---|---|
| `sigma-api` | [sigmacomputing/sigma-agent-skills](https://github.com/sigmacomputing/sigma-agent-skills) |
| `sigma-data-models` | [sigmacomputing/sigma-agent-skills](https://github.com/sigmacomputing/sigma-agent-skills) |
| `sigma-workbook-conventions` | [RyanLauderback/ryan-workbook-skill](https://github.com/RyanLauderback/ryan-workbook-skill) |

This repo used to ship forked copies of all three. They drifted badly — the `ryan-workbook-skill` fork was 54 commits behind, and its `sigma-workbook-conventions` had 4 files where upstream has 37, including eight worked example specs. Forks also broke references that are correct in their home repo, because a copied skill leaves its sibling `docs/` and plugin manifest behind.

Both upstream repos also publish plugin manifests, so `/plugin marketplace add sigmacomputing/sigma-agent-skills` is a valid alternative to the symlink for those two. The installer uses symlinks for all three so there's one mechanism to reason about.

---

## Part 2 — Gong sync

### Quick path

```bash
scripts/setup.sh
```

Checks prerequisites, verifies your Sigma credentials against `/v2/whoami`, lists the rep names the workbook exposes so you can pick yours, writes `config/me.py`, optionally sets the GitHub Actions secrets via `gh`, runs a backfill, and installs the daily local pull. Every step is optional and the script is re-runnable.

### Manual path

**1. Get access to the source workbook.** The sync reads a Sigma workbook named `VR Gong Calls`. You need read access — ask the toolkit owner. Without it every other step will fail at export time.

**2. Sigma API credentials.** Sigma → Administration → Developer Access → Create new. Note that `SIGMA_BASE_URL` is the **API host**, not the app URL — `https://aws-api.sigmacomputing.com`, not `https://app.sigmacomputing.com`. [Region list](https://help.sigmacomputing.com/docs/region-warehouse-and-feature-support).

**3. Configure your reps.**

```bash
cp config/me.example.py config/me.py
python scripts/sync_gong_calls.py --list-reps   # exact strings — a typo returns zero rows silently
```

`config/me.py` is gitignored, so your rep list never conflicts with an upstream pull.

**4. GitHub Actions.** Settings → Secrets and variables → Actions:

| Kind | Name | Value |
|---|---|---|
| Secret | `SIGMA_BASE_URL` | e.g. `https://aws-api.sigmacomputing.com` |
| Secret | `SIGMA_CLIENT_ID` | your client ID |
| Secret | `SIGMA_CLIENT_SECRET` | your client secret |
| Variable | `REPS` | same value as in `config/me.py` |

`REPS` is a **variable**, not a secret — the runner can't read the gitignored `config/me.py`, and secrets are masked in logs, which makes a wrong rep list very hard to debug.

**5. Backfill.**

```bash
pip install -r requirements.txt
export SIGMA_BASE_URL=... SIGMA_CLIENT_ID=... SIGMA_CLIENT_SECRET=...
python scripts/sync_gong_calls.py --since 90 --dry-run   # inspect first
python scripts/sync_gong_calls.py --since 90
```

**6. Keep your laptop copy fresh.** The Action commits to GitHub; this pulls it down so Claude can read the transcripts locally.

```bash
scripts/install-local-sync.sh          # macOS (launchd), daily at 08:00
scripts/install-local-sync.sh --at 09:30
scripts/install-local-sync.sh --uninstall
```

Not on macOS? Use cron: `0 8 * * * /path/to/repo/scripts/pull-latest.sh /path/to/repo`

---

## CLI reference

```bash
python scripts/sync_gong_calls.py                 # nightly: dedup against what's on disk
python scripts/sync_gong_calls.py --since 90      # only keep calls from the last N days
python scripts/sync_gong_calls.py --all           # no date filter (the default)
python scripts/sync_gong_calls.py --list-reps     # print distinct rep names, then exit
python scripts/sync_gong_calls.py --dry-run       # print actions, write nothing
python scripts/sync_gong_calls.py --allow-unfiltered   # deliberately pull EVERY rep's calls
REPS="Other Rep" python scripts/sync_gong_calls.py     # one-off override
```

**A rep filter is required.** Without one the export returns every rep's calls, including prospects that aren't yours — which is almost always an unfinished setup rather than a deliberate choice. The script refuses to run and tells you how to fix it. `--allow-unfiltered` opts in on purpose; `--list-reps` bypasses the check because it has to query unfiltered to work.

There is no automatic nightly date window. The export has no server-side date filter, so a window would only discard rows that dedup already skips — and would silently drop late-arriving Gong transcripts, which is exactly what the placeholder-backfill logic exists to handle.

---

## How the sync works

1. **Auth** — OAuth client credentials → bearer token.
2. **Find workbook + table element** by name.
3. **Export CSV** — `POST /v2/workbooks/{id}/export`, passing the rep filter as a control parameter when `REPS` is set, so the filter applies server-side. Transient 5xx responses are retried.
4. **Group by account** → write/append `prospects/prospect_<Account>/context_<Account>.txt`, newest call first, deduped on date + title.
5. **Backfill placeholders** — a call whose transcript Gong hasn't finished processing is written as a metadata-only entry, then filled in place on a later run.
6. **Prune stale transcripts** — a prospect with no call in 90 days loses its `context_*.txt`. **The folder is never deleted**; your `scoping.md`, `data-models/`, `workbooks/` and `.env` are left alone. The folder goes only if pruning left it empty.
7. **Heartbeat** — `prospects/.sync-status` is written every run, including runs that find nothing.
8. **Commit + push** — one commit per day.

### Is it working?

```bash
cat prospects/.sync-status     # last_run, rows_exported, calls_written, prospects_pruned
tail -20 git-pull.log          # local mirror, timestamped
gh run list --workflow "Daily Gong Call Sync" --limit 10
```

A run that finds no new calls still commits a heartbeat, so "no commit today" now genuinely means something went wrong. On failure the Action opens an issue labelled `gong-sync`.

Quiet days are normal: a Monday run covers Sunday, and there are rarely weekend calls.

---

## context file format

```
2026-05-18	Sigma + Acme	34.88 min	Acme New Business	Jane Doe
Speaker (Role): utterance
Speaker (Role): utterance

2026-05-14	Acme | Sigma - Finalize Commercials	3.05 min	Acme New Business	Jane Doe
...
```

Tab-separated metadata header per call, transcript below, newest first.

---

## Configuration

Everything lives in `config/me.py` (gitignored; copy from `config/me.example.py`):

| Setting | Default | Notes |
|---|---|---|
| `REPS` | `""` | Comma-separated Opportunity Owner names, no space after the comma. **Required** — the script refuses to run unfiltered unless passed `--allow-unfiltered`. |
| `WORKBOOK_NAME` | `VR Gong Calls` | Source workbook |
| `WORKSPACE_NAME` | `Client_B_Vish` | Workspace the workbook lives in |
| `REPS_CONTROL_ID` | `New-Control` | Element ID of the rep-filter control |
| `STALE_AFTER_DAYS` | `90` | Days before a transcript file is pruned |

The env var `REPS` overrides the file, which is how the GitHub Action passes it in.

---

## Contributing improvements back

Skills and scripts evolve upstream; per-SE config does not. `config/me.py` is gitignored precisely so you can pull upstream changes without conflicts. If you fix a bug or add something other SEs should have, open a PR.
