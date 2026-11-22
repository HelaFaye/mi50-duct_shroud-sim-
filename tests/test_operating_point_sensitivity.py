import tempfile
import unittest
from pathlib import Path

from analysis.fan_operating_point import FanCurve, SystemCurve
from analysis.operating_point_sensitivity import (
    _affinity_scaled_fan_curve,
    _resistance_scaled_system_curve,
    run_sensitivity,
)


class OperatingPointSensitivityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "data/fan_curves").mkdir(parents=True)
        (self.root / "data/system_curves").mkdir(parents=True)
        self.fan_path = self.root / "data/fan_curves/synthetic_fan.csv"
        self.fan_path.write_text(
            "flow_cfm,static_pressure_mmh2o\n0,10\n50,5\n100,0\n", encoding="utf-8"
        )
        self.system_path = self.root / "data/system_curves/synthetic_system.csv"
        self.system_path.write_text(
            "flow_cfm,static_pressure_mmh2o\n0,0\n50,2\n100,8\n", encoding="utf-8"
        )

    def tearDown(self):
        self.temp.cleanup()

    def run_model(self, **overrides):
        args = {
            "fan_curve_path": self.fan_path,
            "repo_root": self.root,
            "reference_rpm": 4000.0,
            "rpm_values": [4000.0],
            "fan_counts": [1, 2],
            "baseline_fan_count": 1,
            "system_resistance_multipliers": [0.5, 1.0, 2.0],
            "system_pressure_mmh2o": 2.0,
            "system_reference_flow_cfm": 50.0,
            "fan_curve_provenance": "synthetic_test_fixture",
        }
        args.update(overrides)
        return run_sensitivity(**args)

    def test_affinity_scaling_applies_flow_and_pressure_exponents(self):
        curve = FanCurve.from_csv(self.fan_path)
        scaled, ratio = _affinity_scaled_fan_curve(curve, 4000.0, 4400.0)
        self.assertAlmostEqual(ratio, 1.1)
        self.assertAlmostEqual(scaled.points[0][0], 0.0)
        self.assertAlmostEqual(scaled.points[0][1], 12.1)
        self.assertAlmostEqual(scaled.points[1][0], 55.0)
        self.assertAlmostEqual(scaled.points[1][1], 6.05)
        self.assertAlmostEqual(scaled.points[-1][0], 110.0)
        self.assertEqual(scaled.points[-1][1], 0.0)

    def test_reference_rpm_returns_original_curve(self):
        curve = FanCurve.from_csv(self.fan_path)
        scaled, ratio = _affinity_scaled_fan_curve(curve, 4000.0, 4000.0)
        self.assertIs(scaled, curve)
        self.assertEqual(ratio, 1.0)

    def test_affinity_scaling_rejects_nonfinite_derived_coordinates(self):
        curve = FanCurve.from_csv(self.fan_path)
        with self.assertRaisesRegex(ValueError, "non-finite"):
            _affinity_scaled_fan_curve(curve, 1e-308, 1e308)

    def test_system_scaling_rejects_nonfinite_derived_coordinates(self):
        curve = SystemCurve.from_csv(self.system_path)
        with self.assertRaisesRegex(ValueError, "non-finite"):
            _resistance_scaled_system_curve(curve, 1e308)

    def test_fan_count_sweep_increases_total_flow_for_identical_parallel_fans(self):
        report = self.run_model(rpm_values=[4000.0], fan_counts=[1, 2], system_resistance_multipliers=[1.0])
        rows = {row["fan_count_parallel"]: row for row in report["scenarios"]}
        self.assertGreater(rows[2]["outputs"]["total_flow_cfm"], rows[1]["outputs"]["total_flow_cfm"])
        self.assertAlmostEqual(rows[2]["outputs"]["per_fan_flow_cfm"] * 2,
                               rows[2]["outputs"]["total_flow_cfm"], places=10)

    def test_quadratic_reference_rejects_underflowed_flow_square(self):
        with self.assertRaisesRegex(ValueError, "quadratic system resistance coefficient"):
            self.run_model(
                system_reference_flow_cfm=1e-308,
                fan_counts=[1],
                system_resistance_multipliers=[1.0],
            )

    def test_quadratic_reference_rejects_overflowed_flow_square(self):
        with self.assertRaisesRegex(ValueError, "quadratic system resistance coefficient"):
            self.run_model(
                system_reference_flow_cfm=1e308,
                fan_counts=[1],
                system_resistance_multipliers=[1.0],
            )

    def test_higher_quadratic_resistance_reduces_flow(self):
        report = self.run_model(fan_counts=[1], system_resistance_multipliers=[0.5, 1.0, 2.0])
        rows = {row["system_resistance_multiplier"]: row for row in report["scenarios"]}
        low = rows[0.5]["outputs"]["total_flow_cfm"]
        nominal = rows[1.0]["outputs"]["total_flow_cfm"]
        high = rows[2.0]["outputs"]["total_flow_cfm"]
        self.assertGreater(low, nominal)
        self.assertGreater(nominal, high)

    def test_affinity_law_rpm_sweep_is_explicit_and_changes_flow(self):
        report = self.run_model(
            rpm_values=[4000.0, 4400.0],
            rpm_scaling_mode="affinity-law",
            fan_counts=[1],
            system_resistance_multipliers=[1.0],
        )
        rows = {row["rpm"]: row for row in report["scenarios"]}
        self.assertGreater(rows[4400.0]["outputs"]["total_flow_cfm"], rows[4000.0]["outputs"]["total_flow_cfm"])
        self.assertEqual(rows[4400.0]["rpm_curve_basis"], "affinity_law_derived")
        self.assertEqual(report["inputs"]["rpm_scaling"]["flow_exponent"], 1)
        self.assertEqual(report["inputs"]["rpm_scaling"]["pressure_exponent"], 2)

    def test_rpm_change_is_rejected_without_explicit_affinity_mode(self):
        with self.assertRaisesRegex(ValueError, "explicitly select rpm_scaling_mode='affinity-law'"):
            self.run_model(rpm_values=[4000.0, 4400.0])

    def test_baseline_axes_must_be_present(self):
        with self.assertRaisesRegex(ValueError, "must include 1.0"):
            self.run_model(system_resistance_multipliers=[0.5, 2.0])
        with self.assertRaisesRegex(ValueError, "must include baseline_fan_count"):
            self.run_model(fan_counts=[2])

    def test_tabulated_curve_sweep_preserves_shape_and_scales_pressure(self):
        report = self.run_model(
            system_pressure_mmh2o=None,
            system_reference_flow_cfm=None,
            system_curve_path=self.system_path,
            fan_counts=[1],
            system_resistance_multipliers=[0.5, 1.0, 2.0],
        )
        rows = {row["system_resistance_multiplier"]: row for row in report["scenarios"]}
        self.assertGreater(rows[0.5]["outputs"]["total_flow_cfm"], rows[1.0]["outputs"]["total_flow_cfm"])
        self.assertGreater(rows[1.0]["outputs"]["total_flow_cfm"], rows[2.0]["outputs"]["total_flow_cfm"])
        self.assertIn("uniformly scales", report["inputs"]["system"]["multiplier_interpretation"])

    def test_output_is_deterministic_and_contains_baseline_comparisons(self):
        first = self.run_model()
        second = self.run_model()
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "complete")
        self.assertEqual(first["run"]["scenario_count"], 6)
        baseline = next(row for row in first["scenarios"] if row["rpm"] == 4000.0
                        and row["fan_count_parallel"] == 1
                        and row["system_resistance_multiplier"] == 1.0)
        self.assertEqual(baseline["comparison_to_baseline"]["total_flow_cfm"]["absolute_change"], 0.0)
        self.assertEqual(first["inputs"]["rpm_scaling"]["electrical_input_power"], "not modeled; RPM is not used as a substitute for measured motor/fan electrical input")

    def test_short_tabulated_curve_failure_is_retained_without_extrapolation(self):
        short_system = self.root / "data/system_curves/short_system.csv"
        short_system.write_text(
            "flow_cfm,static_pressure_mmh2o\n0,0\n37.5,2\n75,6\n", encoding="utf-8"
        )
        report = self.run_model(
            system_pressure_mmh2o=None,
            system_reference_flow_cfm=None,
            system_curve_path=short_system,
            fan_counts=[1],
            system_resistance_multipliers=[0.2, 1.0],
        )
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["run"]["failed_scenarios"], 1)
        failed = next(row for row in report["scenarios"] if row["status"] == "failed")
        self.assertEqual(failed["failure_category"], "system_curve_range_too_short")
        self.assertIsNone(failed["outputs"])

    def test_zero_heat_load_has_undefined_relative_temperature_change(self):
        report = self.run_model(heat_load_w=0.0, fan_counts=[1], system_resistance_multipliers=[1.0])
        comparison = report["scenarios"][0]["comparison_to_baseline"]["ideal_bulk_air_temperature_rise_c"]
        self.assertEqual(comparison["absolute_change"], 0.0)
        self.assertIsNone(comparison["relative_change_percent"])


if __name__ == "__main__":
    unittest.main()
