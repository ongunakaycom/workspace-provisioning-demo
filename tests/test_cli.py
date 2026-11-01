"""End-to-end: the exact commands from the README, run without credentials."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from provisioner.cli import main

ROOT = Path(__file__).resolve().parent.parent
INPUT = str(ROOT / "data" / "new_hires.example.csv")
SNAPSHOT = str(ROOT / "data" / "snapshot.example.json")


def run(*args: str) -> tuple[int, str]:
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(out):
        code = main(list(args))
    return code, out.getvalue()


class CliTests(unittest.TestCase):
    def test_dry_run_needs_a_snapshot_and_writes_nothing(self):
        code, output = run("--input", INPUT)
        self.assertEqual(code, 2)
        self.assertIn("refusing to invent a directory", output)

    def test_dry_run_plans_eleven_actions(self):
        # grace: 2, tim: 4 (create + 2 groups + licence), alan: 1,
        # katherine: 4 (suspend, move, 2 groups removed).
        code, output = run("--input", INPUT, "--snapshot", SNAPSHOT)
        self.assertEqual(code, 0)
        self.assertIn("11 action(s)", output)
        self.assertIn("dry run — nothing was written", output)
        # Ada is already correct, so she must not appear in the plan.
        self.assertNotIn("ada.lovelace", output)

    def test_apply_then_replan_is_a_no_op(self):
        code, output = run("--input", INPUT, "--snapshot", SNAPSHOT, "--fake", "--apply")
        self.assertEqual(code, 0)
        self.assertIn("second pass: 0 remaining", output)

    def test_typo_in_org_unit_stops_the_run(self):
        import csv
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "broken.csv"
            with (ROOT / "data" / "new_hires.example.csv").open(newline="", encoding="utf-8") as src:
                rows = list(csv.DictReader(src))
            rows[1]["org_unit"] = "/Enginering"
            with broken.open("w", newline="", encoding="utf-8") as dst:
                writer = csv.DictWriter(dst, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

            code, output = run("--input", str(broken), "--snapshot", SNAPSHOT)
            self.assertEqual(code, 2)
            self.assertIn("shadow OU", output)


if __name__ == "__main__":
    unittest.main()
