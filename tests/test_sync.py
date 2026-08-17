#!/usr/bin/env python3
"""Tests for scripts/sync_gong_calls.py.

Run: python3 tests/test_sync.py     (no pytest needed — stdlib unittest)

These exist because the template's copy of the sync script silently regressed
to a revision predating the placeholder-backfill fix, and nothing caught it.
Every test below pins behaviour that was broken at some point.
"""

import importlib.util
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent


def load_sync():
    """Import the sync script as a module without running main()."""
    saved = sys.argv
    sys.argv = ["sync_gong_calls.py"]
    try:
        spec = importlib.util.spec_from_file_location(
            "sync_gong_calls", REPO / "scripts" / "sync_gong_calls.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.argv = saved


m = load_sync()

OLD = "2020-01-01"
RECENT = "2026-08-13"


def row(date, title, account, transcript="Someone (Sigma): hi", owner="Jane Doe"):
    return {
        m.COL_DATE: date, m.COL_TITLE: title, m.COL_DURATION: "10.0",
        m.COL_ACCOUNT: account, m.COL_OPPORTUNITY: f"{account} Opp",
        m.COL_OPP_OWNER: owner, m.COL_TRANSCRIPT: transcript,
    }


class TempProspects(unittest.TestCase):
    """Redirect the module's module-level paths at a throwaway directory."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self._saved = (m.PROSPECTS_DIR, m.STATUS_PATH)
        m.PROSPECTS_DIR = self.tmp
        m.STATUS_PATH = self.tmp / ".sync-status"

    def tearDown(self):
        m.PROSPECTS_DIR, m.STATUS_PATH = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def mk(self, folder, files):
        d = self.tmp / folder
        d.mkdir(parents=True, exist_ok=True)
        for name, content in files.items():
            p = d / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        return d


class TestTemplateDefaults(unittest.TestCase):
    def test_ships_no_rep_list(self):
        """The template must never carry one SE's reps to another."""
        self.assertEqual(
            m._cfg("REPS", ""), "",
            "config default REPS is non-empty — a new SE would silently sync "
            "someone else's prospects",
        )

    def test_retention_is_90_days(self):
        self.assertEqual(m.STALE_AFTER_DAYS, 90)


class TestCleanup(TempProspects):
    """cleanup_stale_prospects() used to shutil.rmtree() the whole folder."""

    def test_keeps_hand_built_artifacts(self):
        d = self.mk("prospect_HasWork", {
            "context_HasWork.txt": f"{OLD}\tOld\t5 min\tOpp\tOwner\nbody",
            "scoping.md": "# scope",
            ".env": "SIGMA_CLIENT_SECRET=shhh",
            "data-models/model.json": "{}",
            "workbooks/spec.json": "{}",
        })
        m.cleanup_stale_prospects(dry_run=False)

        self.assertFalse((d / "context_HasWork.txt").exists(), "transcript not pruned")
        self.assertTrue(d.is_dir(), "folder was deleted")
        self.assertTrue((d / "scoping.md").exists(), "scoping.md destroyed")
        self.assertTrue((d / ".env").exists(), ".env destroyed and unrecoverable")
        self.assertTrue((d / "data-models/model.json").exists())
        self.assertTrue((d / "workbooks/spec.json").exists())

    def test_removes_folder_only_when_emptied(self):
        self.mk("prospect_Empty", {"context_Empty.txt": f"{OLD}\tOld\t5 min\tOpp\tOwner\nbody"})
        m.cleanup_stale_prospects(dry_run=False)
        self.assertFalse((self.tmp / "prospect_Empty").exists())

    def test_leaves_fresh_prospects_alone(self):
        self.mk("prospect_Fresh", {"context_Fresh.txt": f"{RECENT}\tNew\t5 min\tOpp\tOwner\nbody"})
        m.cleanup_stale_prospects(dry_run=False)
        self.assertTrue((self.tmp / "prospect_Fresh/context_Fresh.txt").exists())

    def test_ignores_files_it_does_not_own(self):
        """A hand-placed .txt is not a context_*.txt and is not ours to delete."""
        d = self.mk("prospect_Manual", {
            "manual_export.txt": f"{OLD}\tOld\t5 min\tOpp\tOwner\nbody",
            "scoping.md": "# scope",
        })
        m.cleanup_stale_prospects(dry_run=False)
        self.assertTrue((d / "manual_export.txt").exists())
        self.assertTrue((d / "scoping.md").exists())

    def test_dry_run_deletes_nothing(self):
        d = self.mk("prospect_Old", {"context_Old.txt": f"{OLD}\tOld\t5 min\tOpp\tOwner\nbody"})
        self.assertEqual(m.cleanup_stale_prospects(dry_run=True), 1)
        self.assertTrue((d / "context_Old.txt").exists())


class TestWriteProspects(TempProspects):
    def test_dry_run_writes_nothing(self):
        m.write_prospects([row(RECENT, "Call", "Acme")], dry_run=True)
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_newest_call_first(self):
        m.write_prospects(
            [row("2026-08-10", "Older", "Acme"), row("2026-08-14", "Newer", "Acme")],
            dry_run=False,
        )
        text = (self.tmp / "prospect_Acme/context_Acme.txt").read_text()
        self.assertTrue(text.startswith("2026-08-14"), "not newest-first")

    def test_dedup_is_idempotent(self):
        rows = [row(RECENT, "Call", "Acme")]
        self.assertEqual(m.write_prospects(rows, dry_run=False), 1)
        self.assertEqual(m.write_prospects(rows, dry_run=False), 0, "re-added a known call")

    def test_placeholder_backfilled_in_place(self):
        """The regression this whole test file exists for.

        Gong often hasn't transcribed a call by the time the sync runs. The
        entry is written metadata-only, then filled in on a later run — it
        must be replaced in place, not appended as a duplicate.
        """
        rows = [row("2026-08-14", "Pricing", "Acme", transcript="")]
        m.write_prospects(rows, dry_run=False)
        path = self.tmp / "prospect_Acme/context_Acme.txt"
        self.assertNotIn("Jane Doe (Sigma)", path.read_text())

        rows[0][m.COL_TRANSCRIPT] = "Jane Doe (Sigma): on pricing"
        self.assertEqual(m.write_prospects(rows, dry_run=False), 1, "did not backfill")

        text = path.read_text()
        self.assertIn("on pricing", text)
        self.assertEqual(text.count("Pricing\t"), 1, "duplicated instead of backfilling")

    def test_rows_without_account_are_skipped(self):
        m.write_prospects([row(RECENT, "Orphan", "")], dry_run=False)
        self.assertEqual(list(self.tmp.iterdir()), [])


class TestDateWindow(unittest.TestCase):
    def test_no_window_by_default(self):
        self.assertIsNone(m.compute_cutoff(None))

    def test_filter_passthrough_without_cutoff(self):
        rows = [row(OLD, "a", "A"), row(RECENT, "b", "B")]
        self.assertEqual(len(m.filter_rows(rows, None)), 2)

    def test_since_drops_older_rows(self):
        rows = [row(OLD, "ancient", "A"), row(RECENT, "recent", "B")]
        kept = m.filter_rows(rows, m.compute_cutoff(90))
        self.assertEqual([r[m.COL_TITLE] for r in kept], ["recent"])


class TestStatusHeartbeat(TempProspects):
    def test_written_even_when_nothing_found(self):
        m.write_status(rows=0, written=0, pruned=0, dry_run=False)
        text = m.STATUS_PATH.read_text()
        self.assertIn("last_run=", text)
        self.assertIn("rows_exported=0", text)

    def test_dry_run_writes_nothing(self):
        m.write_status(rows=1, written=1, pruned=0, dry_run=True)
        self.assertFalse(m.STATUS_PATH.exists())


class TestCLI(unittest.TestCase):
    """Guard the flags the docstring used to advertise but never registered."""

    def run_cli(self, *args, env=None):
        import os
        e = dict(os.environ)
        e.pop("REPS", None)
        e.update(env or {})
        return subprocess.run(
            [sys.executable, str(REPO / "scripts" / "sync_gong_calls.py"), *args],
            capture_output=True, text=True, env=e, cwd=REPO, timeout=60,
        )

    def test_help_lists_every_documented_flag(self):
        out = self.run_cli("--help").stdout
        for flag in ("--dry-run", "--since", "--all", "--list-reps", "--allow-unfiltered"):
            self.assertIn(flag, out, f"{flag} is undocumented or unregistered")

    def test_since_and_all_are_exclusive(self):
        r = self.run_cli("--all", "--since", "30")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("mutually exclusive", r.stderr)

    def test_refuses_to_run_unfiltered(self):
        """An unset REPS pulls every rep's calls — it must be opt-in."""
        r = self.run_cli(env={
            "SIGMA_BASE_URL": "https://invalid.invalid",
            "SIGMA_CLIENT_ID": "x", "SIGMA_CLIENT_SECRET": "y",
        })
        self.assertEqual(r.returncode, 2, "ran unfiltered without opt-in")
        self.assertIn("No rep filter set", r.stderr)

    def test_missing_credentials_exits_cleanly(self):
        r = self.run_cli(env={
            "SIGMA_BASE_URL": "", "SIGMA_CLIENT_ID": "", "SIGMA_CLIENT_SECRET": "",
            "REPS": "Jane Doe",
        })
        self.assertEqual(r.returncode, 1)
        self.assertIn("Missing required env vars", r.stderr)


class TestShellScripts(unittest.TestCase):
    def test_all_shell_scripts_parse(self):
        scripts = sorted(REPO.glob("scripts/*.sh")) + sorted(
            REPO.glob(".claude/skills/*/scripts/*.sh")
        )
        self.assertTrue(scripts, "no shell scripts found")
        for s in scripts:
            with self.subTest(script=s.name):
                r = subprocess.run(["bash", "-n", str(s)], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, f"{s.name}: {r.stderr}")

    def test_no_personal_values_shipped(self):
        """The template must not carry one SE's paths or rep names."""
        needles = ["vish-gong-test", "Samuel Woods", "Josh Blank", "Brendan Dolan"]
        offenders = []
        for path in REPO.rglob("*"):
            if not path.is_file() or ".git/" in str(path):
                continue
            # This file necessarily contains the needles it searches for.
            if path.resolve() == pathlib.Path(__file__).resolve():
                continue
            if path.suffix not in {".py", ".sh", ".yml", ".yaml", ".json"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for needle in needles:
                if needle in text:
                    offenders.append(f"{path.relative_to(REPO)}: {needle}")
        self.assertEqual(offenders, [], "personal values in shipped files")


class TestWorkflow(unittest.TestCase):
    def test_workflow_is_valid_yaml_and_gated(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("pyyaml not installed")
        spec = yaml.safe_load((REPO / ".github/workflows/nightly_sync.yml").read_text())
        steps = spec["jobs"]["sync"]["steps"]
        names = [s.get("name", "") for s in steps]
        self.assertIn("Run sync", names)
        run_step = next(s for s in steps if s.get("name") == "Run sync")
        self.assertIn("preflight", run_step.get("if", ""),
                      "Run sync is not gated on the preflight check")


if __name__ == "__main__":
    unittest.main(verbosity=2)
