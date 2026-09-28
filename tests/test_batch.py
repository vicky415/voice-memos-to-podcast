import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


spec = importlib.util.spec_from_file_location(
    "batch", Path(__file__).resolve().parents[1] / "skills" / "voice-memos-to-podcast" / "scripts" / "batch.py"
)
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)


class BatchWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        root = Path(self.scratch.name)
        self.files = [root / "01.m4a", root / "02.m4a"]
        for path in self.files:
            path.write_bytes(b"synthetic audio fixture")

    def test_spotify_only_keeps_social_disabled_and_requires_order(self):
        ledger = batch.initialize(self.files, "spotify-only")
        with self.assertRaises(ValueError):
            batch.mark(ledger, 2, "spotify", "attempted")
        with self.assertRaises(ValueError):
            batch.mark(ledger, 1, "x", "attempted")
        for stage in ("spotify", "done"):
            batch.mark(ledger, 1, stage, "attempted")
            batch.mark(ledger, 1, stage, "confirmed")
        batch.mark(ledger, 2, "spotify", "attempted")
        self.assertEqual(ledger["episodes"][1]["spotify"], "attempted")

    def test_social_sequence_and_duplicate_protection(self):
        ledger = batch.initialize(self.files, "spotify-x-facebook")
        with self.assertRaises(ValueError):
            batch.mark(ledger, 1, "x", "attempted")
        batch.mark(ledger, 1, "spotify", "attempted")
        batch.mark(ledger, 1, "spotify", "confirmed")
        with self.assertRaises(ValueError):
            batch.mark(ledger, 1, "facebook", "attempted")
        batch.mark(ledger, 1, "x", "attempted")
        with self.assertRaises(ValueError):
            batch.mark(ledger, 1, "x", "attempted")
        batch.mark(ledger, 1, "x", "confirmed")
        with self.assertRaises(ValueError):
            batch.mark(ledger, 1, "x", "attempted")
        batch.mark(ledger, 1, "facebook", "attempted")
        batch.mark(ledger, 1, "facebook", "confirmed")
        batch.mark(ledger, 1, "done", "attempted")
        batch.mark(ledger, 1, "done", "confirmed")
        batch.mark(ledger, 2, "spotify", "attempted")

    def test_failure_can_continue_and_ledger_survives_restart(self):
        path = Path(self.scratch.name) / "private.json"
        batch.write_new(path, batch.initialize(self.files, "spotify-x-facebook"))
        ledger = batch.load(path)
        for stage, value in (
            ("spotify", "attempted"), ("spotify", "confirmed"),
            ("x", "attempted"), ("x", "failed"),
            ("facebook", "attempted"), ("facebook", "confirmed"),
            ("done", "attempted"), ("done", "confirmed"),
        ):
            batch.mark(ledger, 1, stage, value)
            batch.replace(path, ledger)
            ledger = batch.load(path)
        self.assertEqual(ledger["episodes"][0]["x"], "failed")
        batch.mark(ledger, 2, "spotify", "attempted")
        self.files[1].write_bytes(b"changed")
        with self.assertRaises(ValueError):
            batch.load(path)

    def test_ordered_unique_files_required(self):
        with self.assertRaises(ValueError):
            batch.initialize(list(reversed(self.files)), "spotify-only")
        with self.assertRaises(ValueError):
            batch.initialize([self.files[0], self.files[0]], "spotify-only")

    def test_folder_selects_only_direct_m4a_files_in_filename_order(self):
        root = Path(self.scratch.name)
        (root / "notes.txt").write_text("not audio")
        (root / "03.M4A").write_bytes(b"third")
        nested = root / "nested"
        nested.mkdir()
        (nested / "00.m4a").write_bytes(b"nested")
        selected = batch.folder_audio(root)
        self.assertEqual([path.name for path in selected], ["01.m4a", "02.m4a", "03.M4A"])
        self.assertEqual(len(batch.initialize(selected, "spotify-only")["episodes"]), 3)

    def test_empty_folder_and_progress_status(self):
        root = Path(self.scratch.name)
        empty = root / "empty"
        empty.mkdir()
        with self.assertRaises(ValueError):
            batch.folder_audio(empty)
        ledger = batch.initialize(self.files, "spotify-x-facebook")
        self.assertEqual(batch.progress(ledger)["next_episode"], 1)
        batch.mark(ledger, 1, "spotify", "attempted")
        batch.mark(ledger, 1, "spotify", "confirmed")
        batch.mark(ledger, 1, "x", "attempted")
        batch.mark(ledger, 1, "x", "failed")
        batch.mark(ledger, 1, "facebook", "attempted")
        batch.mark(ledger, 1, "facebook", "confirmed")
        batch.mark(ledger, 1, "done", "attempted")
        batch.mark(ledger, 1, "done", "confirmed")
        state = batch.progress(ledger)
        self.assertEqual((state["completed"], state["next_episode"]), (1, 2))
        self.assertEqual(state["episodes"][0]["x"], "failed")

    def test_cli_folder_to_social_completion_and_safe_resume(self):
        script = Path(__file__).resolve().parents[1] / "skills" / "voice-memos-to-podcast" / "scripts" / "batch.py"
        ledger_path = Path(self.scratch.name) / "batch.json"

        def command(*args, check=True):
            return subprocess.run(
                [sys.executable, str(script), *args],
                capture_output=True,
                text=True,
                check=check,
            )

        created = command(
            "init", "--mode", "spotify-x-facebook", "--folder", self.scratch.name,
            "--out", str(ledger_path),
        )
        self.assertEqual(json.loads(created.stdout)["progress"]["next_episode"], 1)
        for stage, value in (
            ("spotify", "attempted"), ("spotify", "confirmed"),
            ("x", "attempted"), ("x", "confirmed"),
            ("facebook", "attempted"), ("facebook", "failed"),
            ("done", "attempted"), ("done", "confirmed"),
        ):
            command(
                "mark", "--ledger", str(ledger_path), "--index", "1",
                "--stage", stage, "--value", value,
            )
        resumed = json.loads(command("status", "--ledger", str(ledger_path)).stdout)
        self.assertEqual((resumed["progress"]["completed"], resumed["progress"]["next_episode"]), (1, 2))
        self.assertEqual(resumed["progress"]["episodes"][0]["facebook"], "failed")
        duplicate = command(
            "mark", "--ledger", str(ledger_path), "--index", "1",
            "--stage", "x", "--value", "attempted", check=False,
        )
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertEqual(json.loads(command("status", "--ledger", str(ledger_path)).stdout)["progress"], resumed["progress"])


if __name__ == "__main__":
    unittest.main()
