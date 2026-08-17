#!/usr/bin/env python3
"""
sync_gong_calls.py

Exports the "VR Gong Calls" table from Sigma, then writes/updates
per-prospect context_{account}.txt files under prospects/.

Usage:
  # Nightly — take whatever the workbook returns, dedup against what's on disk:
  python scripts/sync_gong_calls.py

  # Backfill: only keep calls from the last N days:
  python scripts/sync_gong_calls.py --since 90

  # Explicitly no date filter (the default; kept for symmetry with --since):
  python scripts/sync_gong_calls.py --all

  # Print the distinct rep names the workbook exposes, then exit. Use this to
  # find the exact strings for config/me.py — a typo yields zero rows silently:
  python scripts/sync_gong_calls.py --list-reps

  # Dry-run (print actions, write no files):
  python scripts/sync_gong_calls.py --dry-run
  python scripts/sync_gong_calls.py --since 90 --dry-run

Required env vars:
  SIGMA_CLIENT_ID       Sigma API client ID
  SIGMA_CLIENT_SECRET   Sigma API client secret
  SIGMA_BASE_URL        e.g. https://aws-api.sigmacomputing.com

Rep filter (primary):
  config/me.py          Defines REPS = "Rep1,Rep2,...". Each SE commits
                        their own to their fork.

Rep filter (override, optional):
  REPS env var          Overrides config/me.py for one-off runs.

Note on the date window: the source workbook has three filter controls on the
table. This script overrides only the rep list; the other two — including a
date filter measured at ~28 days — keep their saved defaults. So the export
reaches back about a month no matter what, and --since is a client-side
filter that can narrow that but never widen it. Widening means changing the
workbook's own date control.
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

REPO_ROOT = Path(__file__).resolve().parent.parent
PROSPECTS_DIR = REPO_ROOT / "prospects"

# Source-workbook coordinates. Defaults match the shared SE workbook; override
# any of them in config/me.py so a different workbook doesn't require editing
# this file (which would conflict on every upstream pull).
sys.path.insert(0, str(REPO_ROOT))
try:
    import config.me as _me
except ImportError:  # no config/me.py — fall back to the shared defaults
    _me = None


def _cfg(name: str, default):
    """Read a setting from config/me.py, falling back to the shared default."""
    return getattr(_me, name, default) if _me else default


WORKBOOK_NAME = _cfg("WORKBOOK_NAME", "VR Gong Calls")
WORKSPACE_NAME = _cfg("WORKSPACE_NAME", "Client_B_Vish")

# Control ID for the rep-filter on the Gong Calls table element.
# Pass via the REPS env var, e.g. REPS="Jane Doe,John Smith".
# Empty / unset → no filter, all rows exported.
REPS_CONTROL_ID = _cfg("REPS_CONTROL_ID", "New-Control")

# How long a prospect can go without a call before its transcript file is
# pruned. Only the context_*.txt is removed — never the folder, which holds
# hand-built scoping/data-model/workbook artifacts and a gitignored .env.
STALE_AFTER_DAYS = _cfg("STALE_AFTER_DAYS", 90)

# Column names as they appear in the Sigma table
COL_DATE = "Day of Gong Call Date"
COL_TITLE = "Gong Call Title"
COL_DURATION = "Gong Call Recording Duration Min"
COL_ACCOUNT = "Account Name"
COL_OPPORTUNITY = "Opportunity Name"
COL_TRANSCRIPT = "Full Transcript"
COL_OPP_OWNER = "Opportunity Owner User Name"

SEPARATOR = "=" * 80

# Written every run, including no-op runs, so "did it run?" and "did it find
# anything?" are separate questions. Without this a quiet Monday is
# indistinguishable from a dead cron.
STATUS_PATH = PROSPECTS_DIR / ".sync-status"


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

    The rep filter is ALWAYS sent explicitly, even when empty:

      parameters omitted        -> the workbook's SAVED DEFAULT for the control
                                   applies. On the shared workbook that default
                                   is one particular SE's rep list, so omitting
                                   it silently scopes your export to somebody
                                   else's accounts. Measured: 91 rows, 4 owners.
      {control: ""}             -> genuinely no filter. Measured: 3742 rows,
                                   187 owners.
      {control: "A,B"}          -> just those owners. Measured: 51 rows for
                                   "Sean Gross,Joe Konen".

    Omitting the key is never what anyone wants, so it is never done. An empty
    `reps` means the caller explicitly asked for everything (--list-reps or
    --allow-unfiltered), and that is what it gets.
    """
    payload: dict = {
        "elementId": element_id,
        "format": {"type": "csv"},
        "parameters": {REPS_CONTROL_ID: reps},
    }

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
    """Poll /v2/query/{queryId}/download until the CSV is ready.

    Transient 5xx responses are retried rather than fatal. On 2026-07-06 a
    single 500 from this endpoint killed an otherwise-healthy nightly run —
    the only failure in 90 days — because raise_for_status() fired on the
    first non-2xx. Sigma's export backend returns 5xx intermittently under
    load; the query is still valid, so retrying is correct.
    """
    server_errors = 0
    for attempt in range(30):
        try:
            resp = requests.get(
                f"{base_url}/v2/query/{query_id}/download",
                headers={"Authorization": f"Bearer {token}"},
                timeout=60,
            )
        except requests.exceptions.RequestException as exc:
            server_errors += 1
            if server_errors > 5:
                raise
            wait = 2 ** min(attempt, 4)
            print(f"[warn] Network error polling export ({exc}); retry in {wait}s ...")
            time.sleep(wait)
            continue

        if resp.status_code == 200:
            resp.encoding = "utf-8"
            return resp.text

        if resp.status_code == 204:
            wait = 2 ** min(attempt, 4)  # exponential backoff capped at 16s
            print(f"[info] Not ready yet, waiting {wait}s ...")
            time.sleep(wait)
            continue

        if resp.status_code >= 500:
            server_errors += 1
            if server_errors > 5:
                print(f"[error] {server_errors} consecutive server errors; giving up.", file=sys.stderr)
                resp.raise_for_status()
            wait = 2 ** min(attempt, 4)
            print(f"[warn] Sigma returned {resp.status_code}; retry {server_errors}/5 in {wait}s ...")
            time.sleep(wait)
            continue

        # 4xx — a real client error. Retrying will not help.
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


def compute_cutoff(since_days: int | None) -> datetime | None:
    """Oldest call date to keep, or None for no date filter.

    There is deliberately no automatic nightly lookback window. The export has
    no server-side date filter, so a window here would only discard rows that
    dedup already skips — and would silently drop late-arriving Gong
    transcripts for calls older than the window, which is precisely the case
    the placeholder-backfill logic exists to handle.
    """
    if since_days is None:
        return None
    return datetime.now(tz=timezone.utc) - timedelta(days=since_days)


def filter_rows(rows: list[dict], cutoff: datetime | None) -> list[dict]:
    """Keep only rows whose Date is >= cutoff. No cutoff → keep everything."""
    if cutoff is None:
        return rows
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


def parse_existing_entries(txt_path: Path) -> dict[str, tuple[str, bool]]:
    """Parse a context txt file into {dedup_key: (entry_text, has_transcript)}.

    Entries are separated by blank lines. The first line of each entry is the
    metadata line ('{date}\\t{title}\\t...'); any non-empty line(s) after that
    are the transcript body. `has_transcript=False` means the entry is a
    metadata-only placeholder — written when Gong hadn't finished transcribing
    yet — and should be re-written when the transcript becomes available on a
    later sync.
    """
    if not txt_path.exists():
        return {}
    text = txt_path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    result: dict[str, tuple[str, bool]] = {}
    for block in re.split(r"\n{2,}", text.strip()):
        block = block.rstrip("\n")
        if not block:
            continue
        lines = block.split("\n")
        m = re.match(r"^(\d{4}-\d{2}-\d{2})\t(.+?)\t", lines[0])
        if not m:
            continue
        key = f"{m.group(1)}||{m.group(2)}"
        has_transcript = any(line.strip() for line in lines[1:])
        result[key] = (block, has_transcript)
    return result


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

    def entry_date(block: str) -> str:
        m = re.match(r"^(\d{4}-\d{2}-\d{2})\t", block)
        return m.group(1) if m else "0000-00-00"

    total_added = 0
    total_updated = 0
    for account, account_rows in sorted(grouped.items()):
        folder_name = f"prospect_{sanitize_name(account)}"
        folder_path = PROSPECTS_DIR / folder_name
        txt_name = f"context_{sanitize_name(account)}.txt"
        txt_path = folder_path / txt_name

        existing = parse_existing_entries(txt_path)
        added = 0
        updated = 0
        new_placeholder = 0

        for row in account_rows:
            key = dedup_key(row)
            row_has_transcript = bool(row.get(COL_TRANSCRIPT, "").strip())
            new_block = format_txt_entry(row).rstrip("\n")

            if key in existing:
                _, was_complete = existing[key]
                if was_complete:
                    continue  # Already complete — leave alone
                # Existing entry is a metadata-only placeholder
                if row_has_transcript:
                    existing[key] = (new_block, True)
                    updated += 1
                # else: still no transcript — keep placeholder, wait for next sync
            else:
                # Brand-new key. Always record it so the call's metadata is
                # preserved; if the transcript isn't ready yet, we write a
                # placeholder and pick up the body on a future sync.
                existing[key] = (new_block, row_has_transcript)
                if row_has_transcript:
                    added += 1
                else:
                    new_placeholder += 1

        if not added and not updated and not new_placeholder:
            continue

        # Re-write the whole file in newest-first order so updates land in place
        sorted_blocks = sorted(existing.values(), key=lambda v: entry_date(v[0]), reverse=True)
        file_text = "\n\n".join(block for block, _ in sorted_blocks)

        total_added += added
        total_updated += updated
        parts = []
        if added:
            parts.append(f"+{added} new")
        if updated:
            parts.append(f"~{updated} backfilled")
        if new_placeholder:
            parts.append(f"·{new_placeholder} placeholder (no transcript yet)")
        print(f"[{'dry-run' if dry_run else 'write'}] {folder_name}/{txt_name}: {', '.join(parts)}")

        if dry_run:
            continue

        folder_path.mkdir(parents=True, exist_ok=True)
        txt_path.write_text(file_text, encoding="utf-8")

    return total_added + total_updated


# ---------------------------------------------------------------------------
# Stale prospect cleanup
# ---------------------------------------------------------------------------


def cleanup_stale_prospects(dry_run: bool) -> int:
    """Prune transcript files for prospects with no call in STALE_AFTER_DAYS.

    Only ever deletes the sync-owned context_*.txt. The prospect folder itself
    is left alone, and is removed only if pruning left it completely empty.

    This function previously did shutil.rmtree(folder), which would have taken
    scoping.md, data-models/, workbooks/, mockups/ and the gitignored (and
    therefore unrecoverable) .env with it. A POV going quiet for a month is
    normal, so that fired on live work — it just happened not to have been
    noticed yet.
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=STALE_AFTER_DAYS)
    pruned = 0

    if not PROSPECTS_DIR.is_dir():
        return 0

    for folder in sorted(PROSPECTS_DIR.iterdir()):
        if not folder.is_dir():
            continue

        # Only sync-owned transcript files are candidates. A hand-placed .txt
        # (e.g. a manual export kept for reference) is not ours to delete.
        stale: list[tuple[Path, datetime]] = []
        for txt_path in sorted(folder.glob("context_*.txt")):
            newest = None
            for line in txt_path.read_text(encoding="utf-8").splitlines():
                m = re.match(r"^(\d{4}-\d{2}-\d{2})\t", line)
                if m:
                    dt = parse_date(m.group(1))
                    if dt and (newest is None or dt > newest):
                        newest = dt

            # No dated entries at all means we cannot judge staleness, and the
            # file is far more likely hand-authored than a stale export — the
            # sync always writes a dated metadata line, even for a call Gong
            # hasn't transcribed. Leave it alone.
            if newest is None:
                continue
            if newest < cutoff:
                stale.append((txt_path, newest))

        if not stale:
            continue

        other = [p for p in folder.iterdir() if p not in {t for t, _ in stale}]
        kept = f", keeping {len(other)} other file(s)" if other else ""
        oldest = min(dt for _, dt in stale)
        print(
            f"[{'dry-run' if dry_run else 'prune'}] {folder.name} "
            f"(last call {oldest.date()}) — "
            f"removing {len(stale)} transcript file(s){kept}"
        )

        if not dry_run:
            for txt_path, _ in stale:
                txt_path.unlink()
            # Remove the folder only if pruning left nothing behind.
            if not any(folder.iterdir()):
                folder.rmdir()
        pruned += 1

    return pruned


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------


def write_status(rows: int, written: int, pruned: int, dry_run: bool) -> None:
    """Record that a run happened, whether or not it found anything.

    Committed alongside the transcripts, so the git history answers "did the
    sync run today?" directly. Previously a run that found no new calls made
    no commit at all, so eleven consecutive quiet Mondays looked identical to
    a dead cron — which is what prompted this whole audit.
    """
    stamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    body = (
        f"last_run={stamp}\n"
        f"rows_exported={rows}\n"
        f"calls_written={written}\n"
        f"prospects_pruned={pruned}\n"
    )
    if dry_run:
        print(f"[dry-run] Would write {STATUS_PATH.name}: last_run={stamp}, rows={rows}")
        return
    PROSPECTS_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(body, encoding="utf-8")


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def git_commit_push(dry_run: bool, calls_changed: int = 0) -> None:
    """Stage prospect changes and commit + push if anything changed."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "prospects/"],
        capture_output=True, text=True, cwd=REPO_ROOT
    )
    if not result.stdout.strip():
        print("[info] No changes to commit.")
        return

    date_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    # Distinguish a real sync from a heartbeat-only run, so `git log` doesn't
    # claim calls were synced on a day when nothing came in.
    if calls_changed:
        msg = f"chore: sync Gong calls {date_str} ({calls_changed} call(s))"
    else:
        msg = f"chore: Gong sync heartbeat {date_str} (no new calls)"

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
    parser.add_argument(
        "--since",
        type=int,
        metavar="N",
        default=None,
        help="Only keep calls from the last N days (client-side). The ceiling is "
             "the source workbook's own date window, ~28 days, which this script "
             "does not override. Default: no date filter.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="No date filter (the default; accepted for symmetry with --since).",
    )
    parser.add_argument(
        "--list-reps",
        action="store_true",
        help="Print the distinct rep names the workbook exposes, then exit. "
             "Use this to get the exact strings for config/me.py.",
    )
    parser.add_argument(
        "--allow-unfiltered",
        action="store_true",
        help="Permit a run with no rep filter, pulling EVERY rep's calls. "
             "Off by default: an unset REPS is almost always an unfinished "
             "setup, not a deliberate request for the whole company's calls.",
    )
    args = parser.parse_args()

    if args.all and args.since is not None:
        parser.error("--all and --since are mutually exclusive.")

    base_url = os.environ.get("SIGMA_BASE_URL", "").rstrip("/")
    client_id = os.environ.get("SIGMA_CLIENT_ID", "")
    client_secret = os.environ.get("SIGMA_CLIENT_SECRET", "")

    # Reps come from config/me.py (committed in your fork). REPS env var
    # overrides for one-off runs. Empty string = unfiltered baseline.
    # --list-reps must query unfiltered, or it would only echo back the filter.
    reps = "" if args.list_reps else os.environ.get("REPS", _cfg("REPS", "")).strip()

    if not all([base_url, client_id, client_secret]):
        print(
            "[error] Missing required env vars: SIGMA_BASE_URL, SIGMA_CLIENT_ID, SIGMA_CLIENT_SECRET",
            file=sys.stderr,
        )
        sys.exit(1)

    # An empty rep filter exports every rep's calls. That is a legitimate but
    # rare choice, and an overwhelmingly common symptom of setup that stopped
    # halfway — so it has to be asked for, not defaulted into.
    if not reps and not args.list_reps and not args.allow_unfiltered:
        print(
            "[error] No rep filter set — this would pull EVERY rep's calls,\n"
            "        including prospects that aren't yours.\n"
            "\n"
            "        Set one of:\n"
            "          config/me.py        REPS = \"Your Name\"   (local runs)\n"
            "          repo variable REPS                        (GitHub Action)\n"
            "          REPS=\"Your Name\" python scripts/sync_gong_calls.py\n"
            "\n"
            "        Find the exact strings:\n"
            "          python scripts/sync_gong_calls.py --list-reps\n"
            "\n"
            "        If you really do want every rep, pass --allow-unfiltered.",
            file=sys.stderr,
        )
        sys.exit(2)

    mode = f"filtered to REPS={reps!r}" if reps else "UNFILTERED (every rep, explicitly allowed)"
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

    # Export. No server-side date filter is applied — the workbook's own
    # filters govern the window, and dedup decides what is actually new.
    print("[info] Exporting CSV ...")
    csv_text = export_csv(base_url, token, workbook_id, element_id, reps=reps)
    rows = parse_rows(csv_text)
    print(f"[info] Exported {len(rows)} row(s)")

    # A filter that matches nothing is the single most likely misconfiguration,
    # and without this it reads as a clean run: exit 0, no changes, no clue.
    # The usual cause is putting your own name in REPS — the column is the
    # opportunity's OWNER (the AE), and you're the SE on the call.
    if reps and not rows:
        print(
            f"\n[warn] REPS={reps!r} matched zero calls.\n"
            "       Names are matched literally, so this is almost certainly a\n"
            "       wrong or misspelled value rather than a genuinely quiet period.\n"
            "       REPS holds the AEs you support, not your own name.\n"
            "\n"
            "       See the exact strings the workbook exposes:\n"
            "         python scripts/sync_gong_calls.py --list-reps\n",
            file=sys.stderr,
        )

    # --list-reps: report and exit without touching any file.
    if args.list_reps:
        names = sorted({r.get(COL_OPP_OWNER, "").strip() for r in rows} - {""})
        print(f"\nDistinct {COL_OPP_OWNER!r} values ({len(names)}):\n")
        for name in names:
            print(f"  {name}")
        print(
            "\nCopy the ones you cover into config/me.py, comma-separated, "
            "no space after the comma:\n"
            '  REPS = "Name One,Name Two"\n'
        )
        return

    cutoff = compute_cutoff(args.since)
    if cutoff is not None:
        before = len(rows)
        rows = filter_rows(rows, cutoff)
        print(f"[info] --since {args.since}: kept {len(rows)} of {before} row(s)")

        # --since is a CLIENT-side filter. The ceiling is the source workbook's
        # own date control, which this script does not override — measured at
        # ~28 days. Asking for more than the workbook returns is silently a
        # no-op, so surface it rather than implying a deeper backfill happened.
        dates = [d for d in (parse_date(r.get(COL_DATE, "")) for r in rows) if d]
        if dates:
            oldest = min(dates)
            reach = (datetime.now(tz=timezone.utc) - oldest).days
            if args.since > reach + 2:
                print(
                    f"[warn] --since {args.since} asked for {args.since} days but the oldest call\n"
                    f"       available is {oldest.date()} ({reach} days back). The export is capped by\n"
                    f"       the source workbook's own date filter, which this script does not\n"
                    f"       override — so this is the full history you can reach today.",
                    file=sys.stderr,
                )

    written = pruned = 0
    if rows:
        # Write prospect files. Brand-new calls get a placeholder if Gong hasn't
        # finished transcribing yet; previously-empty placeholders are backfilled
        # in place once the transcript appears in a subsequent export.
        written = write_prospects(rows, dry_run=args.dry_run)
        print(f"[info] Calls newly written or backfilled: {written}")

        # Prune transcript files for prospects gone quiet. Never deletes a
        # folder that still holds hand-built artifacts.
        print("[info] Checking for stale transcripts ...")
        pruned = cleanup_stale_prospects(dry_run=args.dry_run)
        print(f"[info] Prospects pruned: {pruned}")
    else:
        print("[info] No rows to process.")

    # Heartbeat first, so the commit below always has something to record.
    write_status(len(rows), written, pruned, dry_run=args.dry_run)

    git_commit_push(dry_run=args.dry_run, calls_changed=written)
    print("[info] Done.")


if __name__ == "__main__":
    main()
