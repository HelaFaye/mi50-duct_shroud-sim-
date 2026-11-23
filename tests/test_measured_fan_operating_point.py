import csv
import hashlib
import tempfile
import unittest
from pathlib import Path

from analysis.fan_operating_point import SystemCurve
from analysis.measured_fan_operating_point import (
    MeasuredFanCurve,
    MeasuredFanPoint,
    load_measured_fan_curves,
    run_measured_sweep,
    solve_measured_operating_points,
    _quadratic_roots,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = REPO_ROOT / "data/fan_curves/noctua_nf_a14x25_g2_cybenetics_25FN140A_raw.csv"
EXPECTED_RAW_SHA256 = "1a7266bafe0bb1acf3e2337f01b18735ab9d3585f193e5c58b5184008c132d8d"


def measured_curve(pwm, coordinates):
    points = tuple(
        MeasuredFanPoint(
            source_row_index=index + 1,
            pwm_percent=pwm,
            point_in_setting=index + 1,
            flow_cfm=flow,
            static_pressure_mmaq=pressure,
            fan_speed_rpm=1500.0 + index * 2.0,
            current_a=0.1 + index * 0.01,
            power_w=1.0 + index * 0.1,
        )
        for index, (flow, pressure) in enumerate(coordinates)
    )
    return MeasuredFanCurve(pwm, points, "synthetic test measurements")


class MeasuredDataImportTests(unittest.TestCase):
    def test_raw_file_hash_and_all_72_records_are_preserved(self):
        raw = RAW_PATH.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), EXPECTED_RAW_SHA256)
        curves = load_measured_fan_curves(RAW_PATH)
        self.assertEqual(len(curves), 9)
        self.assertEqual(sum(len(curve.points) for curve in curves.values()), 72)
        self.assertEqual(sorted(curves), [20, 30, 40, 50, 60, 70, 80, 90, 100])

    def test_negative_endpoints_positive_80_percent_endpoint_and_reversals_are_retained(self):
        curves = load_measured_fan_curves(RAW_PATH)
        for pwm in (20, 30, 40, 50, 60, 70, 90, 100):
            self.assertEqual(curves[pwm].points[-1].static_pressure_mmaq, -0.01)
        self.assertEqual(curves[80].points[-1].static_pressure_mmaq, 0.01)
        self.assertEqual(curves[60].points[3].static_pressure_mmaq, 0.46)
        self.assertEqual(curves[60].points[4].static_pressure_mmaq, 0.50)
        self.assertEqual(curves[100].points[3].static_pressure_mmaq, 1.31)
        self.assertEqual(curves[100].points[4].static_pressure_mmaq, 1.34)

    def test_selected_pwm_keeps_point_order_and_point_level_telemetry(self):
        curve = load_measured_fan_curves(RAW_PATH, [100])[100]
        self.assertEqual(len(curve.points), 8)
        self.assertEqual(curve.points[0].source_row_index, 65)
        self.assertEqual(curve.points[-1].source_row_index, 72)
        self.assertEqual(curve.points[0].fan_speed_rpm, 1503)
        self.assertEqual(curve.points[0].current_a, 0.279)
        self.assertEqual(curve.points[0].power_w, 3.35)

    def test_flow_must_be_strictly_increasing_but_pressure_may_reverse(self):
        curves = load_measured_fan_curves(RAW_PATH, [100])
        self.assertGreater(
            curves[100].points[4].static_pressure_mmaq,
            curves[100].points[3].static_pressure_mmaq,
        )
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "bad.csv"
            with RAW_PATH.open(newline="", encoding="utf-8") as source:
                rows = list(csv.DictReader(source))
            rows[1]["flow_cfm"] = rows[0]["flow_cfm"]
            with target.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "flow must be strictly increasing"):
                load_measured_fan_curves(target)

    def test_interpolation_includes_rpm_current_and_power(self):
        curve = load_measured_fan_curves(RAW_PATH, [100])[100]
        result = curve.interpolate(20.0)
        left, right = curve.points[1], curve.points[2]
        fraction = (20.0 - left.flow_cfm) / (right.flow_cfm - left.flow_cfm)
        self.assertAlmostEqual(
            result["static_pressure_mmaq"],
            left.static_pressure_mmaq + fraction * (right.static_pressure_mmaq - left.static_pressure_mmaq),
        )
        self.assertAlmostEqual(
            result["fan_speed_rpm"],
            left.fan_speed_rpm + fraction * (right.fan_speed_rpm - left.fan_speed_rpm),
        )

    def test_interpolation_refuses_flow_below_first_measurement(self):
        curve = measured_curve(100, [(5.0, 10.0), (15.0, 0.0)])
        self.assertEqual(curve.min_flow_cfm, 5.0)
        self.assertEqual(curve.interpolate(5.0)["static_pressure_mmaq"], 10.0)
        with self.assertRaisesRegex(ValueError, "extrapolation is disabled"):
            curve.interpolate(4.9)


class MeasuredIntersectionTests(unittest.TestCase):
    def test_nonzero_minimum_measured_flow_sets_common_solver_domain(self):
        curve = measured_curve(100, [(5.0, 10.0), (15.0, 0.0)])
        system = SystemCurve(
            ((0.0, 0.0), (10.0, 1.0), (20.0, 2.0),
             (30.0, 3.0), (40.0, 4.0)),
            source="synthetic nonzero-minimum test",
        )
        result = solve_measured_operating_points(curve, 2, system_curve=system)

        self.assertEqual(result["common_flow_domain_cfm"], [10.0, 30.0])
        self.assertEqual(result["status"], "unique_intersection")
        self.assertAlmostEqual(result["roots"][0]["total_flow_cfm"], 25.0)
        self.assertGreaterEqual(result["roots"][0]["per_fan_flow_cfm"], 5.0)

    def test_quadratic_root_solver_avoids_catastrophic_cancellation(self):
        roots = _quadratic_roots(1.0, -1e16, 1.0)
        self.assertEqual(len(roots), 2)
        self.assertAlmostEqual(roots[0] / 1e-16, 1.0, places=14)
        self.assertAlmostEqual(roots[1] / 1e16, 1.0, places=14)

    def test_near_tangent_quadratic_preserves_two_close_real_roots(self):
        roots = _quadratic_roots(1.0, -2.0, 1.0 - 1e-12)

        self.assertEqual(len(roots), 2)
        self.assertLess(roots[0], 1.0)
        self.assertGreater(roots[1], 1.0)
        self.assertAlmostEqual(roots[0], 0.999999, places=8)
        self.assertAlmostEqual(roots[1], 1.000001, places=8)

        self.assertEqual(_quadratic_roots(1.0, -2.0, 1.0), [1.0])
        self.assertEqual(_quadratic_roots(1.0, -2.0, 1.0 + 1e-12), [])

    def test_quadratic_root_at_measured_breakpoint_is_reported_once(self):
        curve = measured_curve(100, [(0.0, 10.0), (20.0, 5.0), (40.0, 0.0)])
        result = solve_measured_operating_points(
            curve,
            1,
            system_pressure_mmh2o=5.0,
            system_reference_flow_cfm=20.0,
        )

        self.assertEqual(result["status"], "unique_intersection")
        self.assertEqual(result["mathematical_intersection_count"], 1)
        self.assertAlmostEqual(result["roots"][0]["total_flow_cfm"], 20.0)
        self.assertAlmostEqual(
            result["roots"][0]["pressure_residual_mmh2o"], 0.0, places=9
        )

    def test_unique_tabulated_intersection_and_electrical_telemetry(self):
        curve = measured_curve(100, [(0, 10), (100, 0)])
        system = SystemCurve(((0, 0), (100, 10)), source="synthetic system")
        result = solve_measured_operating_points(curve, 1, system_curve=system)
        self.assertEqual(result["status"], "unique_intersection")
        root = result["roots"][0]
        self.assertAlmostEqual(root["total_flow_cfm"], 50.0)
        self.assertAlmostEqual(root["fan_static_pressure_mmh2o"], 5.0)
        self.assertAlmostEqual(root["system_pressure_drop_mmh2o"], 5.0)
        self.assertAlmostEqual(root["per_fan_power_w"], 1.05)
        self.assertAlmostEqual(root["array_power_w_estimate"], 1.05)

    def test_multiple_intersections_are_all_reported(self):
        curve = measured_curve(100, [(0, 10), (20, 1), (40, 4), (60, 0.5), (100, -0.01)])
        system = SystemCurve(
            ((0, 0), (20, 2), (40, 2.5), (60, 3), (100, 4)),
            source="synthetic system with rising pressure",
        )
        result = solve_measured_operating_points(curve, 1, system_curve=system)
        self.assertEqual(result["status"], "multiple_intersections")
        self.assertEqual(result["mathematical_intersection_count"], 3)
        flows = [root["total_flow_cfm"] for root in result["roots"]]
        self.assertTrue(flows[0] < 20 < flows[1] < 40 < flows[2] < 60)

    def test_quadratic_screening_intersection_is_solved_per_measured_segment(self):
        curve = measured_curve(100, [(0, 10), (100, 0)])
        result = solve_measured_operating_points(
            curve,
            1,
            system_pressure_mmh2o=2.0,
            system_reference_flow_cfm=50.0,
        )
        self.assertEqual(result["status"], "unique_intersection")
        q = result["roots"][0]["total_flow_cfm"]
        self.assertAlmostEqual(10.0 - 0.1 * q, 0.0008 * q * q, places=8)

    def test_quadratic_roots_outside_generating_segment_are_rejected(self):
        # The first segment's extrapolated positive root is about 22.9 CFM,
        # outside [0, 20].  Only the second segment's root is admissible.
        curve = measured_curve(100, [(0, 10), (20, 2), (40, 0)])
        result = solve_measured_operating_points(
            curve,
            1,
            system_pressure_mmh2o=2.0,
            system_reference_flow_cfm=50.0,
        )
        self.assertEqual(result["status"], "unique_intersection")
        self.assertEqual(result["mathematical_intersection_count"], 1)
        q = result["roots"][0]["total_flow_cfm"]
        self.assertGreaterEqual(q, 20.0)
        self.assertLessEqual(q, 40.0)
        self.assertAlmostEqual(
            result["roots"][0]["fan_static_pressure_mmh2o"],
            result["roots"][0]["system_pressure_drop_mmh2o"],
            places=9,
        )

    def test_quadratic_mode_preserves_distinct_valid_roots_from_pressure_reversals(self):
        curve = measured_curve(100, [(0, 10), (20, 0.1), (40, 2), (60, 0)])
        result = solve_measured_operating_points(
            curve,
            1,
            system_pressure_mmh2o=2.0,
            system_reference_flow_cfm=50.0,
        )
        self.assertEqual(result["status"], "multiple_intersections")
        self.assertEqual(result["mathematical_intersection_count"], 3)
        flows = [root["total_flow_cfm"] for root in result["roots"]]
        self.assertEqual(flows, sorted(flows))
        self.assertTrue(all(0.0 < q < 60.0 for q in flows))

    def test_positive_terminal_pressure_can_produce_no_intersection(self):
        curve = measured_curve(80, [(0, 1.0), (100, 0.01)])
        result = solve_measured_operating_points(
            curve,
            1,
            system_pressure_mmh2o=0.0001,
            system_reference_flow_cfm=100.0,
        )
        self.assertEqual(result["status"], "no_positive_intersection")
        self.assertEqual(result["roots"], [])

    def test_coincident_segment_is_reported_as_ambiguous(self):
        curve = measured_curve(100, [(0, 10), (20, 1), (40, 2), (100, 5)])
        system = SystemCurve(((0, 0), (20, 1), (40, 2), (100, 5)), source="coincident")
        result = solve_measured_operating_points(curve, 1, system_curve=system)
        self.assertEqual(result["status"], "coincident_segment")
        self.assertEqual(result["coincident_segments_total_flow_cfm"], [[20, 100]])
        self.assertEqual(result["mathematical_intersection_count"], 0)
        self.assertEqual(result["roots"], [])

    def test_no_extrapolation_when_system_curve_range_is_short(self):
        curve = measured_curve(100, [(0, 10), (100, 0)])
        system = SystemCurve(((0, 0), (20, 2), (40, 4)), source="short system")
        result = solve_measured_operating_points(curve, 1, system_curve=system)
        self.assertEqual(result["common_flow_domain_cfm"], [0.0, 40])
        self.assertEqual(result["status"], "no_positive_intersection")

    def test_sweep_covers_nine_pwm_settings_without_rpm_affinity_scaling(self):
        report = run_measured_sweep(
            RAW_PATH,
            pwm_values=[20, 30, 40, 50, 60, 70, 80, 90, 100],
            fan_counts=[1, 2, 3],
            system_pressure_mmh2o=2.0,
            system_reference_flow_cfm=50.0,
            pressure_expanded_uncertainty_pa=0.6727,
        )
        self.assertEqual(report["source"]["measurement_record_count"], 72)
        self.assertEqual(report["run"]["scenario_count"], 27)
        self.assertEqual(report["run"]["unique_intersections"], 27)
        self.assertEqual(report["run"]["multiple_intersection_scenarios"], 0)
        self.assertEqual(report["run"]["no_intersection_scenarios"], 0)
        self.assertTrue(all(s["mathematical_intersection_count"] == 1 for s in report["scenarios"]))
        self.assertEqual(report["source"]["selected_pwm_settings"], [20, 30, 40, 50, 60, 70, 80, 90, 100])
        self.assertAlmostEqual(report["curve_diagnostics"][0]["maximum_adjacent_pressure_increase_mmaq"], 0.01)
        self.assertAlmostEqual(report["source"]["declared_pressure_expanded_uncertainty_mmh2o"], 0.06859630964702523, places=12)
        self.assertTrue(all(item["maximum_increase_within_declared_expanded_uncertainty"] for item in report["curve_diagnostics"]))
        self.assertTrue(all("rpm" not in scenario for scenario in report["scenarios"]))


if __name__ == "__main__":
    unittest.main()
