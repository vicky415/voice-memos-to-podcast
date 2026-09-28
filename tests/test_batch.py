import importlib.util
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
