import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class OperatingPointSensitivityCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        (self.repo / "data/fan_curves").mkdir(parents=True)

        self.fan_path = self.repo / "data/fan_curves/synthetic.csv"
        self.fan_path.write_text(
            "flow_cfm,static_pressure_mmh2o\n"
            "0,10\n"
            "50,5\n"
            "100,0\n",
            encoding="utf-8",
        )

        (self.repo / "data/system_curves").mkdir(parents=True)
        self.system_path = self.repo / "data/system_curves/synthetic.csv"
        self.system_path.write_text(
            "flow_cfm,static_pressure_mmh2o\n"
            "0,0\n"
            "50,2\n"
            "100,8\n",
            encoding="utf-8",
        )

        self.base_args = [
            "--fan-curve", "data/fan_curves/synthetic.csv",
            "--repo-root", str(self.repo),
            "--reference-rpm", "4000",
            "--rpms", "4000",
            "--fan-counts", "1",
            "--baseline-fan-count", "1",
            "--system-resistance-multipliers", "1",
            "--system-pressure-mmh2o", "2",
            "--system-reference-flow-cfm", "50",
            "--fan-curve-provenance", "synthetic_cli_fixture",
        ]

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *extra):
        return self.run_cli_args([*self.base_args, *extra])

    def run_system_cli(self, *extra, system_curve="data/system_curves/synthetic.csv"):
        args = list(self.base_args)

        for option in (
            "--system-pressure-mmh2o",
            "--system-reference-flow-cfm",
        ):
            index = args.index(option)
            del args[index:index + 2]

        args.extend(["--system-curve", system_curve, *extra])
        return self.run_cli_args(args)

    def run_cli_args(self, args):
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "analysis.operating_point_sensitivity",
                *args,
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_stdout_contains_valid_json_and_provenance(self):
        result = self.run_cli()

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)

        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["run"]["scenario_count"], 1)
        self.assertEqual(
            report["inputs"]["fan_curve"]["sha256"],
            hashlib.sha256(self.fan_path.read_bytes()).hexdigest(),
        )
        self.assertTrue(report["inputs"]["solver_source_sha256"])

    def test_json_file_output_can_be_outside_repository_root(self):
        output_dir = self.root / "reports"
        output_dir.mkdir()
        output_path = output_dir / "sensitivity.json"

        result = self.run_cli("--output", str(output_path))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        report = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["analysis"], "deterministic_operating_point_sensitivity")

    def test_invalid_fan_count_exits_two(self):
        result = self.run_cli("--fan-counts", "0")

        self.assertEqual(result.returncode, 2)
        self.assertIn("fan_counts entries must be positive integers", result.stderr)

    def test_missing_quadratic_reference_flow_exits_two(self):
        args = list(self.base_args)
        index = args.index("--system-reference-flow-cfm")
        del args[index:index + 2]

        result = self.run_cli_args(args)

        self.assertEqual(result.returncode, 2)
        self.assertIn("--system-reference-flow-cfm is required", result.stderr)

    def test_parent_traversal_input_is_rejected(self):
        result = self.run_cli("--fan-curve", "../outside.csv")

        self.assertEqual(result.returncode, 2)
        self.assertIn("must resolve inside repository root", result.stderr)

    def test_symlink_input_escape_is_rejected(self):
        outside = self.root / "outside.csv"
        outside.write_text(
            "flow_cfm,static_pressure_mmh2o\n0,10\n50,5\n100,0\n",
            encoding="utf-8",
        )

        link = self.repo / "data/fan_curves/escape.csv"
        try:
            link.symlink_to(outside)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")

        result = self.run_cli("--fan-curve", "data/fan_curves/escape.csv")

        self.assertEqual(result.returncode, 2)
        self.assertIn("must resolve inside repository root", result.stderr)

    def test_output_cannot_overwrite_fan_curve(self):
        original = self.fan_path.read_bytes()

        result = self.run_cli("--output", str(self.fan_path))

        self.assertEqual(result.returncode, 2)
        self.assertIn("must not overwrite an analysis input", result.stderr)
        self.assertEqual(self.fan_path.read_bytes(), original)

    def test_output_symlink_cannot_overwrite_fan_curve(self):
        original = self.fan_path.read_bytes()
        output_link = self.root / "fan-alias.csv"

        try:
            output_link.symlink_to(self.fan_path)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")

        result = self.run_cli("--output", str(output_link))

        self.assertEqual(result.returncode, 2)
        self.assertIn("must not overwrite an analysis input", result.stderr)
        self.assertEqual(self.fan_path.read_bytes(), original)

    def test_missing_output_directory_is_reported_cleanly(self):
        output_path = self.root / "missing-directory/report.json"

        result = self.run_cli("--output", str(output_path))

        self.assertEqual(result.returncode, 2)
        self.assertIn("error:", result.stderr)
        self.assertFalse(output_path.exists())


    def test_tabulated_system_curve_cli_reports_hash_and_provenance(self):
        result = self.run_system_cli()

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)

        system = report["inputs"]["system"]
        self.assertEqual(
            system["sha256"],
            hashlib.sha256(self.system_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(system["path"], str(self.system_path))
        self.assertEqual(
            system["model"],
            "tabulated_curve_uniform_pressure_multiplier",
        )
        self.assertEqual(report["status"], "complete")

    def test_system_curve_parent_traversal_is_rejected(self):
        result = self.run_system_cli(system_curve="../outside.csv")

        self.assertEqual(result.returncode, 2)
        self.assertIn("must resolve inside repository root", result.stderr)

    def test_system_curve_symlink_escape_is_rejected(self):
        outside = self.root / "outside_system.csv"
        outside.write_text(
            "flow_cfm,static_pressure_mmh2o\n"
            "0,0\n"
            "50,2\n"
            "100,8\n",
            encoding="utf-8",
        )

        link = self.repo / "data/system_curves/escape.csv"
        try:
            link.symlink_to(outside)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")

        result = self.run_system_cli(
            system_curve="data/system_curves/escape.csv"
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("must resolve inside repository root", result.stderr)

    def test_output_cannot_overwrite_system_curve(self):
        original = self.system_path.read_bytes()

        result = self.run_system_cli("--output", str(self.system_path))

        self.assertEqual(result.returncode, 2)
        self.assertIn("must not overwrite an analysis input", result.stderr)
        self.assertEqual(self.system_path.read_bytes(), original)

    def test_output_cannot_overwrite_solver_source(self):
        solver_path = PROJECT_ROOT / "analysis/fan_operating_point.py"
        original_hash = hashlib.sha256(solver_path.read_bytes()).hexdigest()

        result = self.run_cli("--output", str(solver_path))

        self.assertEqual(result.returncode, 2)
        self.assertIn("must not overwrite an analysis input", result.stderr)
        self.assertEqual(
            hashlib.sha256(solver_path.read_bytes()).hexdigest(),
            original_hash,
        )

if __name__ == "__main__":
    unittest.main()
