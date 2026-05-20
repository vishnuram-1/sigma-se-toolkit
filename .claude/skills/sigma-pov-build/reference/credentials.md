# Credentials handling

Each prospect has its own Sigma org and its own API client. Credentials live in a per-prospect `.env`.

## File location

```
~/Prospects/vish-gong-test/prospects/prospect_<Name>/.env
```

## Required keys

```
SIGMA_BASE_URL=https://aws-api.sigmacomputing.com    # or another region
SIGMA_CLIENT_ID=...
SIGMA_CLIENT_SECRET=...
```

## Loading

When a Sigma API call is needed for a prospect:

```bash
set -a; source prospects/prospect_<Name>/.env; set +a
```

Then defer to the `sigma-api` skill — it handles the OAuth exchange and returns a bearer token.

## Safety invariants

These are **non-negotiable**. Violating any of them is a session-ending bug.

1. **Never echo a secret.** No `echo $SIGMA_CLIENT_SECRET`, no `cat .env`, no `env | grep SIGMA`. Even in error messages.
2. **Never write a secret to a file inside the workspace.** Tokens stay in env vars; they go into `Authorization: Bearer ...` headers and nowhere else.
3. **Never commit `.env`.** The repo `.gitignore` covers `**/.env`. Verify it's in place before creating any `.env`. If gitignore is missing or doesn't match, abort and ask the user to fix it first.
4. **Never log full curl commands** that include `-u $CLIENT_ID:$CLIENT_SECRET` — the shell expands them and they end up in transcripts.
5. **Per-prospect isolation.** A token minted from prospect A's `.env` must not be used against prospect B's base URL. The folder is the source of truth for which creds apply.

## Verifying gitignore before first .env is created

```bash
grep -E "^\*\*/\.env$|^\.env$" ~/Prospects/vish-gong-test/.gitignore
```

Must return at least one match. If empty → halt and tell the user to fix `.gitignore` first.

## What to do if a secret leaks

1. Tell the user immediately.
2. Recommend they rotate the client secret in Sigma (Admin → Developer Access).
3. If the leak was to a file, `git filter-repo` (or BFG) is required to scrub history — a `git rm` is not enough.
