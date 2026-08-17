# Credentials handling

Each prospect has its own Sigma org and its own API client. Credentials live in a per-prospect `.env`.

## File location

```
prospects/prospect_<Name>/.env
```

## Required keys

```
SIGMA_BASE_URL=https://aws-api.sigmacomputing.com    # or another region
SIGMA_CLIENT_ID=...
SIGMA_CLIENT_SECRET=...
```

## Loading

Don't load credentials by hand. The globalized Sigma scripts at `scripts/api/*.sh` all source `_env.sh` on first call, which:

1. Reads `.env` from the **current working directory** (so `cd` into the prospect folder first).
2. Fetches an OAuth token via the `sigma-api` skill's `get-token.sh`.
3. Caches the token at `/tmp/.sigma_token` (mode 0600, 55-min TTL).
4. Exports `SIGMA_BASE_URL`, `SIGMA_API_TOKEN`, and the `sigma_curl` helper (auto-injects `Authorization` + `Accept: application/json`, retries once on 401 after re-fetching).

The implication: **never `cat .env` or `source .env` directly**. Always invoke through the scripts. If you need bare `sigma_curl` from a one-off bash command (e.g., a GET that doesn't have a wrapper script), source `_env.sh` once and use `sigma_curl`:

```bash
cd prospects/prospect_<Name>
source scripts/api/_env.sh
sigma_curl "$SIGMA_BASE_URL/v2/files?limit=5"
```

This pattern keeps `SIGMA_CLIENT_SECRET` out of the calling shell's env entirely — only `SIGMA_API_TOKEN` (a short-lived bearer) ends up exported.

## Safety invariants

These are **non-negotiable**. Violating any of them is a session-ending bug.

1. **Never echo a secret.** No `echo $SIGMA_CLIENT_SECRET`, no `cat .env`, no `env | grep SIGMA`. Even in error messages.
2. **Never write a secret to a file inside the workspace.** Tokens stay in env vars; they go into `Authorization: Bearer ...` headers and nowhere else.
3. **Never commit `.env`.** The repo `.gitignore` covers `**/.env`. Verify it's in place before creating any `.env`. If gitignore is missing or doesn't match, abort and ask the user to fix it first.
4. **Never log full curl commands** that include `-u $CLIENT_ID:$CLIENT_SECRET` — the shell expands them and they end up in transcripts.
5. **Per-prospect isolation.** A token minted from prospect A's `.env` must not be used against prospect B's base URL. The folder is the source of truth for which creds apply.

## Verifying gitignore before first .env is created

```bash
grep -E "^\*\*/\.env$|^\.env$" .gitignore
```

Must return at least one match. If empty → halt and tell the user to fix `.gitignore` first.

## What to do if a secret leaks

1. Tell the user immediately.
2. Recommend they rotate the client secret in Sigma (Admin → Developer Access).
3. If the leak was to a file, `git filter-repo` (or BFG) is required to scrub history — a `git rm` is not enough.
