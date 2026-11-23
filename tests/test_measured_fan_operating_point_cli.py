"""Output-safety regression tests for the measured-fan CLI."""

import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from analysis import measured_fan_operating_point as measured


class MeasuredFanOutputSafetyTests(unittest.TestCase):
    def setUp(self):
        self.repo_temp = tempfile.TemporaryDirectory()
        self.external_temp = tempfile.TemporaryDirectory()

        self.root = Path(self.repo_temp.name).resolve()
        self.external = Path(self.external_temp.name).resolve()

        self.results = self.root / "results"
        self.results.mkdir()

        (self.root / "analysis").mkdir()
        (self.root / "docs").mkdir()
        (self.root / "data").mkdir()

        self.measurement = self.root / "data" / "measurement.csv"
        self.measurement.write_text("synthetic input\n", encoding="utf-8")

        self.solver_source = self.root / "analysis" / "solver.py"
        self.solver_source.write_text("source must survive\n", encoding="utf-8")

    def tearDown(self):
        self.repo_temp.cleanup()
        self.external_temp.cleanup()

    def resolve(self, output, inputs=()):
        return measured._resolve_safe_output_path(
            output,
            repo_root=self.root,
            input_paths=inputs,
        )

    def test_accepts_repository_results_destination(self):
        output = self.results / "report.json"
        self.assertEqual(self.resolve(output), output)

    def test_rejects_repository_destination_outside_results(self):
        with self.assertRaisesRegex(ValueError, "inside"):
            self.resolve(self.solver_source)

    def test_rejects_parent_traversal_into_source_tree(self):
        output = self.results / ".." / "analysis" / "solver.py"
        with self.assertRaisesRegex(ValueError, "inside"):
            self.resolve(output)

    def test_accepts_explicit_absolute_external_destination(self):
        output = self.external / "report.json"
        self.assertEqual(self.resolve(output), output)

    def test_rejects_relative_external_destination(self):
        output = Path(os.path.relpath(
            self.external / "report.json",
            Path.cwd(),
        ))
        with self.assertRaisesRegex(ValueError, "absolute"):
            self.resolve(output)

    def test_rejects_symlinked_output_file(self):
        target = self.external / "target.json"
        target.write_text("protected\n", encoding="utf-8")
        link = self.results / "report.json"

        try:
            link.symlink_to(target)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")

        with self.assertRaisesRegex(ValueError, "symlink"):
            self.resolve(link)

        self.assertEqual(target.read_text(encoding="utf-8"), "protected\n")

    def test_rejects_symlinked_output_parent(self):
        link = self.results / "external"
        try:
            link.symlink_to(self.external, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")

        with self.assertRaisesRegex(ValueError, "symlink"):
            self.resolve(link / "report.json")

    def test_rejects_symlinked_results_directory(self):
        self.results.rmdir()
        try:
            self.results.symlink_to(self.external, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")

        with self.assertRaisesRegex(ValueError, "symlink"):
            self.resolve(self.results / "report.json")

    def test_rejects_output_collision_with_analysis_input(self):
        source = self.results / "input.csv"
        source.write_text("important input\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "analysis input"):
            self.resolve(source, inputs=[source])

        self.assertEqual(source.read_text(encoding="utf-8"), "important input\n")

    def test_rejects_missing_parent_without_creating_it(self):
        parent = self.results / "missing"
        with self.assertRaisesRegex(ValueError, "already exist"):
            self.resolve(parent / "report.json")
        self.assertFalse(parent.exists())

    def test_atomic_write_creates_complete_report(self):
        output = self.results / "report.json"
        output.write_text('{"old": true}\n', encoding="utf-8")

        measured._atomic_write_text(output, '{"new": true}\n')

        self.assertEqual(
            json.loads(output.read_text(encoding="utf-8")),
            {"new": True},
        )
        self.assertEqual(list(self.results.glob(".report.json.*.tmp")), [])

    def test_atomic_write_failure_preserves_existing_report(self):
        output = self.results / "report.json"
        output.write_text("original\n", encoding="utf-8")

        with patch(
            "analysis.measured_fan_operating_point.os.replace",
            side_effect=OSError("simulated replacement failure"),
        ):
            with self.assertRaisesRegex(OSError, "simulated"):
                measured._atomic_write_text(output, "replacement\n")

        self.assertEqual(output.read_text(encoding="utf-8"), "original\n")
        self.assertEqual(list(self.results.glob(".report.json.*.tmp")), [])

    def cli_args(self, output):
        return [
            "--measurement-csv", str(self.measurement),
            "--pwms", "100",
            "--fan-counts", "1",
            "--system-pressure-mmh2o", "2.0",
            "--system-reference-flow-cfm", "50",
            "--output", str(output),
        ]

    def test_cli_writes_repository_report_atomically(self):
        output = self.results / "cli-report.json"

        with (
            patch.object(measured, "REPOSITORY_ROOT", self.root),
            patch.object(measured, "run_measured_sweep", return_value={"ok": True}),
        ):
            result = measured.main(self.cli_args(output))

        self.assertEqual(result, 0)
        self.assertEqual(
            json.loads(output.read_text(encoding="utf-8")),
            {"ok": True},
        )

    def test_cli_rejects_attempt_to_overwrite_solver_source(self):
        original = self.solver_source.read_text(encoding="utf-8")

        with (
            patch.object(measured, "REPOSITORY_ROOT", self.root),
            patch.object(measured, "run_measured_sweep", return_value={"ok": True}),
        ):
            with redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    measured.main(self.cli_args(self.solver_source))

        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(self.solver_source.read_text(encoding="utf-8"), original)

    def test_cli_supports_explicit_external_report(self):
        output = self.external / "external-report.json"

        with (
            patch.object(measured, "REPOSITORY_ROOT", self.root),
            patch.object(measured, "run_measured_sweep", return_value={"external": True}),
        ):
            result = measured.main(self.cli_args(output))

        self.assertEqual(result, 0)
        self.assertEqual(
            json.loads(output.read_text(encoding="utf-8")),
            {"external": True},
        )


if __name__ == "__main__":
    unittest.main()
