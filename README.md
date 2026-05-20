# sigma-se-toolkit

SE toolkit for managing prospects end-to-end: nightly Gong call sync from Sigma + a set of Claude skills for building data models, workbooks, and POVs.

This repo is a **template** — click **"Use this template"** at the top of the GitHub page to create your own copy.

---

## What you get

| | |
|---|---|
| `scripts/sync_gong_calls.py` | Pulls Gong call transcripts from a shared Sigma workbook, organises them per-prospect under `prospects/<account>/context_<account>.txt` |
| `.github/workflows/nightly_sync.yml` | GitHub Action that runs the sync every morning at 10 AM UTC |
| `.claude/skills/` | 6 Sigma-related Claude skills: `sigma-api`, `sigma-data-models`, `sigma-workbook-conventions`, `sigma-pov-build`, `sigma-fin-recon`, `sigma-scenario-modeling` |
| `config/me.py` | Per-SE config — set your rep list here |

---

## Setup (after creating your repo from the template)

### 1. Configure your reps

Edit `config/me.py`:

```python
REPS = "Your Rep,Another Rep,Third Rep"
```

Empty string means "no filter" — you'll get every row the workbook returns.

Commit and push:

```bash
git add config/me.py && git commit -m "Configure my reps" && git push
```

### 2. Add GitHub Actions secrets

Go to **Settings → Secrets and variables → Actions → Secrets** and add:

| Secret | Value |
|--------|-------|
| `SIGMA_BASE_URL` | e.g. `https://api.sigmacomputing.com` |
| `SIGMA_CLIENT_ID` | Your Sigma API client ID |
| `SIGMA_CLIENT_SECRET` | Your Sigma API client secret |

Generate Sigma API credentials in your Sigma instance: **Administration → Developer access → Create new**.

### 3. Run it once manually to backfill

```bash
git clone https://github.com/<your-org>/<your-repo>.git
cd <your-repo>
pip install -r requirements.txt

export SIGMA_BASE_URL=...
export SIGMA_CLIENT_ID=...
export SIGMA_CLIENT_SECRET=...
python scripts/sync_gong_calls.py
```

This commits + pushes the initial set of `prospects/<account>/context.txt` files. After that, the nightly cron keeps them fresh.

### 4. (Optional) One-off run with a different rep

`config/me.py` is the default. Override for a one-time run:

```bash
REPS="Other Rep" python scripts/sync_gong_calls.py
```

---

## Known assumptions (will change)

- **Sigma workbook**: hardcoded to a workbook named `VR Gong Calls` in a workspace called `Client_B_Vish`. To use the toolkit today, you need read access to that workbook (ask Vish). Future work: parameterize workspace via `config/me.py`.
- **Rep-filter control ID**: hardcoded to `New-Control` (the text-list control on the table element). Make sure the workbook you point at has this control.
- **Workbook columns**: `Day of Gong Call Date`, `Gong Call Title`, `Gong Call Recording Duration Min`, `Account Name`, `Opportunity Name`, `Full Transcript`, `Opportunity Owner User Name`.

---

## How the sync works

1. **Auth** — OAuth client credentials → bearer token.
2. **Find workbook + table element** — by name.
3. **Export CSV** — POST to `/v2/workbooks/{id}/export`, passing `parameters.New-Control` if `REPS` is set. Server-side filter is applied.
4. **Group by account** → write/append to `prospects/<account>/context_<account>.txt`, newest call first. Dedup by date + title.
5. **Stale folder cleanup** — any prospect with no call in the last 30 days gets its folder deleted.
6. **Commit + push** — one daily `chore: sync Gong calls YYYY-MM-DD` commit.

---

## context.txt format

```
2026-05-18	Sigma + Reltio	34.88 min	Reltio New Business	Justin Levy
Speaker (Role): utterance
Speaker (Role): utterance

2026-05-14	Reltio | Sigma - Finalize Commercials	3.05 min	Reltio New Business	Justin Levy
...
```

Tab-separated metadata header per call, transcript below.

---

## Contributing improvements back

This template is a starting point. If you fix a bug or add a feature you think other SEs should benefit from, open a PR against `sigmacomputing/sigma-se-toolkit`. Skills and scripts evolve here; per-SE config (`config/me.py`) does not.
