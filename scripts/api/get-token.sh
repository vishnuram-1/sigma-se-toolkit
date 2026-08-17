#!/usr/bin/env bash
# Local fork of sigma-api's get-token.sh that extends the host allowlist to
# include Sigma staging environments. Identical to upstream otherwise — same
# pinned-host safety property, same token charset check before printing.
#
# Activated by setting SIGMA_TOKEN_FETCHER=<this script's path> in the .env
# of a workspace that needs to hit staging. Production .envs leave it unset
# and use the upstream skill copy.

set -euo pipefail

: "${SIGMA_BASE_URL:?SIGMA_BASE_URL is not set}"
: "${SIGMA_CLIENT_ID:?SIGMA_CLIENT_ID is not set}"
: "${SIGMA_CLIENT_SECRET:?SIGMA_CLIENT_SECRET is not set}"

for bin in curl jq base64; do
  command -v "$bin" >/dev/null 2>&1 || { echo "Error: $bin is required" >&2; exit 1; }
done

case "$SIGMA_BASE_URL" in
  https://aws-api.sigmacomputing.com|\
  https://api.us-a.aws.sigmacomputing.com|\
  https://api.ca.aws.sigmacomputing.com|\
  https://api.eu.aws.sigmacomputing.com|\
  https://api.au.aws.sigmacomputing.com|\
  https://api.uk.aws.sigmacomputing.com|\
  https://api.us.azure.sigmacomputing.com|\
  https://api.eu.azure.sigmacomputing.com|\
  https://api.ca.azure.sigmacomputing.com|\
  https://api.uk.azure.sigmacomputing.com|\
  https://api.sigmacomputing.com|\
  https://api.sa.gcp.sigmacomputing.com|\
  https://api.staging.sigmacomputing.io|\
  https://staging.sigmacomputing.io) ;;
  *) echo "Error: SIGMA_BASE_URL must be one of the published Sigma API hosts (incl. staging) for this fork." >&2; exit 1 ;;
esac

CREDENTIALS=$(printf '%s:%s' "$SIGMA_CLIENT_ID" "$SIGMA_CLIENT_SECRET" | base64 | tr -d '\n')

RESPONSE=$(curl -sf -X POST "${SIGMA_BASE_URL}/v2/auth/token" \
  -H "Authorization: Basic ${CREDENTIALS}" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials")

TOKEN=$(echo "$RESPONSE" | jq -r '.access_token')

if [[ -z "$TOKEN" || "$TOKEN" == "null" ]]; then
  echo "Error: failed to extract access_token from response:" >&2
  echo "$RESPONSE" >&2
  exit 1
fi

if ! [[ "$TOKEN" =~ ^[A-Za-z0-9._~+/=-]+$ ]]; then
  echo "Error: token contains unexpected characters; refusing to emit." >&2
  exit 1
fi

printf 'export SIGMA_API_TOKEN=%q\n' "$TOKEN"
