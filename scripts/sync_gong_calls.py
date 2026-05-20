#!/usr/bin/env python3
"""
sync_gong_calls.py

Exports the "VR Gong Calls" table from Sigma, then writes/updates
per-prospect context_{account}.md files under prospects/.

Usage:
  # Nightly (auto-detects Monday for 72h lookback, else 24h):
  python scripts/sync_gong_calls.py

  # One-time backfill of the past 30 days:
  python scripts/sync_gong_calls.py --initial

  # One-time full export of all data (no date filter):
  python scripts/sync_gong_calls.py --all

  # Dry-run (print actions, write no files):
  python scripts/sync_gong_calls.py --dry-run
  python scripts/sync_gong_calls.py --initial --dry-run

Required env vars:
  SIGMA_CLIENT_ID       Sigma API client ID
  SIGMA_CLIENT_SECRET   Sigma API client secret
  SIGMA_BASE_URL        e.g. https://aws-api.sigmacomputing.com

Rep filter (primary):
  config/me.py          Defines REPS = "Rep1,Rep2,...". Each SE commits
                        their own to their fork.

Rep filter (override, optional):
  REPS env var          Overrides config/me.py for one-off runs.
"""

import argparse
import csv
import io
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

WORKBOOK_NAME = "VR Gong Calls"
WORKSPACE_NAME = "Client_B_Vish"

# Control ID for the rep-filter on the Gong Calls table element.
# Pass via the REPS env var, e.g. REPS="Eric Ratner,Justin Levy".
# Empty / unset → no filter, all rows exported.
REPS_CONTROL_ID = "New-Control"

# Column names as they appear in the Sigma table
COL_DATE = "Day of Gong Call Date"
COL_TITLE = "Gong Call Title"
COL_DURATION = "Gong Call Recording Duration Min"
COL_ACCOUNT = "Account Name"
COL_OPPORTUNITY = "Opportunity Name"
COL_TRANSCRIPT = "Full Transcript"
COL_OPP_OWNER = "Opportunity Owner User Name"

SEPARATOR = "=" * 80

REPO_ROOT = Path(__file__).resolve().parent.parent
PROSPECTS_DIR = REPO_ROOT / "prospects"


# ---------------------------------------------------------------------------
# Sigma API helpers
# ---------------------------------------------------------------------------


def get_token(base_url: str, client_id: str, client_secret: str) -> str:
    """Obtain a Bearer token via OAuth2 client credentials."""
    url = f"{base_url}/v2/auth/token"
    resp = requests.post(
        url,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def sigma_get(base_url: str, token: str, path: str, params: dict = None) -> dict:
    """GET a Sigma API endpoint and return parsed JSON."""
    resp = requests.get(
        f"{base_url}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def sigma_post(base_url: str, token: str, path: str, payload: dict) -> requests.Response:
    """POST to a Sigma API endpoint."""
    resp = requests.post(
        f"{base_url}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    return resp


def find_workbook(base_url: str, token: str) -> dict:
    """Locate the workbook by name within the target workspace."""
    page_token = None
    while True:
        params = {"limit": 50, "search": WORKBOOK_NAME}
        if page_token:
            params["page"] = page_token

        data = sigma_get(base_url, token, "/v2/workbooks", params)
        entries = data.get("entries", [])

        for wb in entries:
            if wb.get("name") == WORKBOOK_NAME:
                # Optionally verify workspace by checking path contains WORKSPACE_NAME
                path_parts = wb.get("path", "")
                if WORKSPACE_NAME.lower() in path_parts.lower():
                    return wb

        next_page = data.get("nextPage")
        if not next_page:
            break
        page_token = next_page

    raise RuntimeError(
        f"Could not find workbook '{WORKBOOK_NAME}' in workspace '{WORKSPACE_NAME}'. "
        "Check SIGMA_BASE_URL, credentials, and workbook name."
    )


def find_element(base_url: str, token: str, workbook_id: str) -> str:
    """Find the element ID for the Gong Calls table within the workbook."""
    pages = sigma_get(base_url, token, f"/v2/workbooks/{workbook_id}/pages")
    for page in pages.get("entries", []):
        page_id = page["pageId"]
        elements = sigma_get(
            base_url, token, f"/v2/workbooks/{workbook_id}/pages/{page_id}/elements"
        )
        for el in elements.get("entries", []):
            name = el.get("name", "")
            el_type = el.get("type", "")
            # Match the table element — prefer exact name match, fall back to first table
            if el_type in ("table", "pivot-table") and (
                WORKBOOK_NAME.lower() in name.lower() or "gong" in name.lower()
            ):
                return el["elementId"]

    # Fallback: return first table element found
    pages = sigma_get(base_url, token, f"/v2/workbooks/{workbook_id}/pages")
    for page in pages.get("entries", []):
        page_id = page["pageId"]
        elements = sigma_get(
            base_url, token, f"/v2/workbooks/{workbook_id}/pages/{page_id}/elements"
        )
        for el in elements.get("entries", []):
            if el.get("type") in ("table", "pivot-table"):
                print(f"[warn] Falling back to element '{el.get('name')}' ({el['elementId']})")
                return el["elementId"]

    raise RuntimeError(f"No table element found in workbook {workbook_id}")


def export_csv(base_url: str, token: str, workbook_id: str, element_id: str, reps: str = "") -> str:
    """Export the workbook element as CSV. Returns the raw CSV text.

    If `reps` is non-empty, applies it as the New-Control filter
    server-side (comma-separated list, no space after comma).
    """
    payload: dict = {
        "elementId": element_id,
        "format": {"type": "csv"},
    }
    if reps:
        payload["parameters"] = {REPS_CONTROL_ID: reps}

    resp = sigma_post(base_url, token, f"/v2/workbooks/{workbook_id}/export", payload)

    # The export may return the CSV directly, or an async query ID to poll.
    content_type = resp.headers.get("Content-Type", "")

    if "text/csv" in content_type or "application/octet-stream" in content_type:
        # Sigma omits the charset; requests defaults to ISO-8859-1 and mangles non-ASCII.
        resp.encoding = "utf-8"
        return resp.text

    # Async path: response contains a queryId to poll
    body = resp.json()
    query_id = body.get("queryId") or body.get("jobId")
    if not query_id:
        raise RuntimeError(f"Unexpected export response: {body}")

    print(f"[info] Export is async, polling queryId={query_id} ...")
    return _poll_download(base_url, token, query_id)


def _poll_download(base_url: str, token: str, query_id: str) -> str:
    """Poll /v2/query/{queryId}/download until the CSV is ready."""
    for attempt in range(30):
        resp = requests.get(
            f"{base_url}/v2/query/{query_id}/download",
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        if resp.status_code == 200:
            resp.encoding = "utf-8"
            return resp.text
        if resp.status_code == 204:
            wait = 2 ** min(attempt, 4)  # exponential backoff capped at 16s
            print(f"[info] Not ready yet, waiting {wait}s ...")
            time.sleep(wait)
            continue
        resp.raise_for_status()

    raise TimeoutError("Export did not complete within the allotted time.")


# ---------------------------------------------------------------------------
# Data processing
# ---------------------------------------------------------------------------


def parse_rows(csv_text: str) -> list[dict]:
    """Parse CSV text into a list of row dicts."""
    reader = csv.DictReader(io.StringIO(csv_text))
    return list(reader)


def parse_date(value: str) -> datetime | None:
    """Parse a date string into a UTC datetime. Returns None if unparseable."""
    if not value:
        return None
    from dateutil import parser as dateutil_parser
    try:
        dt = dateutil_parser.parse(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def compute_cutoff(initial: bool) -> datetime:
    """Return the oldest date we should include."""
    now = datetime.now(tz=timezone.utc)
    if initial:
        return now - timedelta(days=30)
    # Monday (weekday==0) → look back 72h to cover the weekend
    lookback_hours = 72 if now.weekday() == 0 else 24
    print(f"[info] Nightly mode: lookback={lookback_hours}h (today is {now.strftime('%A')})")
    return now - timedelta(hours=lookback_hours)


def filter_rows(rows: list[dict], cutoff: datetime) -> list[dict]:
    """Keep only rows whose Date is >= cutoff."""
    result = []
    for row in rows:
        dt = parse_date(row.get(COL_DATE, ""))
        if dt and dt >= cutoff:
            result.append(row)
    return result


def sanitize_name(name: str) -> str:
    """Convert an account name to a safe folder-name suffix."""
    name = name.strip()
    # Replace runs of non-alphanumeric characters with underscores
    name = re.sub(r"[^\w]+", "_", name)
    # Strip leading/trailing underscores
    name = name.strip("_")
    return name


def format_txt_entry(row: dict) -> str:
    """Format a single call as a plain-text block.

    Format:
        {date}\\t{title}\\t{duration} min\\t{opportunity}\\t{owner}
        Speaker (Role): utterance
        Speaker (Role): utterance
        ...
    """
    date_raw = row.get(COL_DATE, "").strip()
    dt = parse_date(date_raw)
    date_display = dt.strftime("%Y-%m-%d") if dt else date_raw
    title = row.get(COL_TITLE, "").strip()
    duration = row.get(COL_DURATION, "").strip()
    opportunity = row.get(COL_OPPORTUNITY, "").strip()
    owner = row.get(COL_OPP_OWNER, "").strip()
    transcript = row.get(COL_TRANSCRIPT, "").strip()

    # Split transcript into one line per speaker turn
    transcript_lines = re.sub(
        r"(?<!\n)([A-Z][a-z]+(?: [A-Z][a-z]+)* \((?:External|Sigma|Unknown)\):)",
        r"\n\1",
        transcript,
    ).lstrip("\n")

    metadata = f"{date_display}\t{title}\t{duration} min\t{opportunity}\t{owner}"
    return f"{metadata}\n{transcript_lines}"


def dedup_key(row: dict) -> str:
    """Unique key used to skip already-written calls."""
    dt = parse_date(row.get(COL_DATE, ""))
    date_str = dt.strftime("%Y-%m-%d") if dt else row.get(COL_DATE, "")
    title = row.get(COL_TITLE, "").strip()
    return f"{date_str}||{title}"


def existing_txt_keys(txt_path: Path) -> set[str]:
    """Extract dedup keys already present in a context txt file.

    Keys are on metadata lines: '{date}\\t{title}\\t...'
    """
    if not txt_path.exists():
        return set()
    keys = set()
    for line in txt_path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(\d{4}-\d{2}-\d{2})\t(.+?)\t", line)
        if m:
            keys.add(f"{m.group(1)}||{m.group(2)}")
    return keys


# ---------------------------------------------------------------------------
# File writing
# ---------------------------------------------------------------------------


def write_prospects(rows: list[dict], dry_run: bool) -> int:
    """Create / update prospect Markdown files. Returns count of new entries written."""
    from collections import defaultdict

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        account = row.get(COL_ACCOUNT, "").strip()
        if not account:
            print(f"[warn] Skipping row with no account name: {row.get(COL_TITLE)}")
            continue
        grouped[account].append(row)

    # Sort each group newest-first
    for account in grouped:
        grouped[account].sort(
            key=lambda r: parse_date(r.get(COL_DATE, "")) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

    new_entries = 0
    for account, account_rows in sorted(grouped.items()):
        folder_name = f"prospect_{sanitize_name(account)}"
        folder_path = PROSPECTS_DIR / folder_name
        txt_name = f"context_{sanitize_name(account)}.txt"
        txt_path = folder_path / txt_name

        known = existing_txt_keys(txt_path)
        new_blocks = []
        for row in account_rows:
            key = dedup_key(row)
            if key in known:
                continue
            new_blocks.append(format_txt_entry(row))
            known.add(key)

        if not new_blocks:
            continue

        new_entries += len(new_blocks)
        print(f"[{'dry-run' if dry_run else 'write'}] {folder_name}/{txt_name}: +{len(new_blocks)} call(s)")

        if dry_run:
            continue

        folder_path.mkdir(parents=True, exist_ok=True)

        # Prepend new entries (newest first) above existing content
        existing = txt_path.read_text(encoding="utf-8") if txt_path.exists() else ""
        new_content = "\n\n".join(new_blocks)
        if existing:
            new_content = new_content + "\n\n" + existing
        txt_path.write_text(new_content, encoding="utf-8")

    return new_entries


# ---------------------------------------------------------------------------
# Stale prospect cleanup
# ---------------------------------------------------------------------------


def cleanup_stale_prospects(dry_run: bool) -> int:
    """Delete prospect folders with no call in the last 30 days. Returns count deleted."""
    import shutil

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=30)
    deleted = 0

    for folder in sorted(PROSPECTS_DIR.iterdir()):
        if not folder.is_dir():
            continue

        txt_files = list(folder.glob("*.txt"))
        if not txt_files:
            continue

        most_recent = None
        for txt_path in txt_files:
            for line in txt_path.read_text(encoding="utf-8").splitlines():
                m = re.match(r"^(\d{4}-\d{2}-\d{2})\t", line)
                if m:
                    dt = parse_date(m.group(1))
                    if dt and (most_recent is None or dt > most_recent):
                        most_recent = dt

        if most_recent is None or most_recent < cutoff:
            age = f"last call {most_recent.date()}" if most_recent else "no dated calls"
            print(f"[{'dry-run' if dry_run else 'delete'}] {folder.name} ({age}) — removing")
            if not dry_run:
                shutil.rmtree(folder)
            deleted += 1

    return deleted


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def git_commit_push(dry_run: bool) -> None:
    """Stage prospect changes and commit + push if anything changed."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "prospects/"],
        capture_output=True, text=True, cwd=REPO_ROOT
    )
    if not result.stdout.strip():
        print("[info] No changes to commit.")
        return

    date_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    msg = f"chore: sync Gong calls {date_str}"

    if dry_run:
        print(f"[dry-run] Would commit: {msg}")
        return

    subprocess.run(["git", "add", "prospects/"], cwd=REPO_ROOT, check=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=REPO_ROOT, check=True)
    subprocess.run(["git", "push", "-u", "origin", "HEAD"], cwd=REPO_ROOT, check=True)
    print(f"[info] Committed and pushed: {msg}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Gong call transcripts from Sigma.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without writing files or committing.",
    )
    args = parser.parse_args()

    base_url = os.environ.get("SIGMA_BASE_URL", "").rstrip("/")
    client_id = os.environ.get("SIGMA_CLIENT_ID", "")
    client_secret = os.environ.get("SIGMA_CLIENT_SECRET", "")

    # Reps come from config/me.py (committed in your fork). REPS env var
    # overrides for one-off runs. Empty string = unfiltered baseline.
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from config.me import REPS as _config_reps
    except ImportError:
        _config_reps = ""
    reps = os.environ.get("REPS", _config_reps).strip()

    if not all([base_url, client_id, client_secret]):
        print(
            "[error] Missing required env vars: SIGMA_BASE_URL, SIGMA_CLIENT_ID, SIGMA_CLIENT_SECRET",
            file=sys.stderr,
        )
        sys.exit(1)

    mode = f"filtered to REPS={reps!r}" if reps else "unfiltered (full workbook)"
    print(f"[info] Starting sync — dry_run={args.dry_run}, mode: {mode}")

    # Auth
    print("[info] Authenticating with Sigma ...")
    token = get_token(base_url, client_id, client_secret)

    # Discover workbook + element
    print(f"[info] Locating workbook '{WORKBOOK_NAME}' in workspace '{WORKSPACE_NAME}' ...")
    workbook = find_workbook(base_url, token)
    workbook_id = workbook["workbookId"]
    print(f"[info] Found workbook: id={workbook_id}")

    print("[info] Locating table element ...")
    element_id = find_element(base_url, token, workbook_id)
    print(f"[info] Found element: id={element_id}")

    # Export — the API always returns the last 30 days; dedup handles skipping known entries
    print("[info] Exporting CSV ...")
    csv_text = export_csv(base_url, token, workbook_id, element_id, reps=reps)
    rows = parse_rows(csv_text)
    print(f"[info] Exported {len(rows)} row(s)")

    if not rows:
        print("[info] Nothing to do.")
        return

    # Write prospect files (dedup prevents re-writing existing calls)
    new_entries = write_prospects(rows, dry_run=args.dry_run)
    print(f"[info] New entries written: {new_entries}")

    # Remove prospect folders with no call in the last 30 days
    print("[info] Checking for stale prospect folders ...")
    deleted = cleanup_stale_prospects(dry_run=args.dry_run)
    print(f"[info] Stale folders removed: {deleted}")

    # Commit & push
    git_commit_push(dry_run=args.dry_run)
    print("[info] Done.")


if __name__ == "__main__":
    main()
