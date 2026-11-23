import hashlib
import math
import tempfile
import unittest
from pathlib import Path

from analysis.fan_operating_point import (
    FanCurve,
    SystemCurve,
    classify_solver_failure,
    solve_operating_point,
)


class FanCurveTests(unittest.TestCase):
    def setUp(self):
        self.curve = FanCurve(
            points=((0.0, 10.0), (50.0, 5.0), (100.0, 0.0)),
            source="synthetic test curve",
        )

    def test_piecewise_linear_interpolation(self):
        self.assertAlmostEqual(self.curve.pressure_at(25.0), 7.5)
        self.assertAlmostEqual(self.curve.pressure_at(75.0), 2.5)

    def test_refuses_extrapolation(self):
        with self.assertRaisesRegex(ValueError, "outside the supplied fan curve"):
            self.curve.pressure_at(101.0)

    def test_csv_loader(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "curve.csv"
            csv_path.write_text(
                "flow_cfm,static_pressure_mmh2o\n0,10\n50,5\n100,0\n",
                encoding="utf-8",
            )
            loaded = FanCurve.from_csv(csv_path)
            self.assertEqual(loaded.points, self.curve.points)

    def test_manufacturer_cfd_curve_is_canonical_and_loads(self):
        repo_root = Path(__file__).resolve().parents[1]
        csv_path = repo_root / "data/fan_curves/arctic_p9_max_4300rpm_manufacturer_cfd.csv"
        self.assertEqual(
            hashlib.sha256(csv_path.read_bytes()).hexdigest(),
            "d1c9123afa5bc3c95226cea0a57b58dc4bdc2a63d20e279fea4b5d09d15ae922",
        )

        curve = FanCurve.from_csv(csv_path)
        self.assertEqual(len(curve.points), 10)
        self.assertEqual(curve.points[0][0], 0.0)
        self.assertAlmostEqual(curve.points[0][1], 6.169283088516466, places=12)
        self.assertAlmostEqual(curve.points[-1][0], 58.25, places=12)
        self.assertEqual(curve.points[-1][1], 0.0)
        self.assertTrue(all(p >= 0.0 for _, p in curve.points))
        self.assertTrue(all(
            right[0] > left[0] and right[1] <= left[1]
            for left, right in zip(curve.points, curve.points[1:])
        ))

    def test_rejects_non_monotone_pressure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "bad.csv"
            csv_path.write_text(
                "flow_cfm,static_pressure_mmh2o\n0,10\n50,11\n100,0\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "non-increasing"):
                FanCurve.from_csv(csv_path)


class OperatingPointTests(unittest.TestCase):
    def setUp(self):
        self.curve = FanCurve(
            points=((0.0, 10.0), (50.0, 5.0), (100.0, 0.0)),
            source="synthetic test curve",
        )

    def test_operating_point_balances_fan_and_system_pressure(self):
        result = solve_operating_point(
            self.curve,
            fan_count=1,
            system_pressure_mmh2o=2.5,
            system_reference_flow_cfm=50.0,
        )
        self.assertAlmostEqual(
            result.fan_static_pressure_mmh2o,
            result.system_pressure_drop_mmh2o,
            places=7,
        )
        # Analytic root of 10 - 0.1*Q = 0.001*Q^2.
        expected = (-0.1 + math.sqrt(0.1**2 + 4 * 0.001 * 10)) / (2 * 0.001)
        self.assertAlmostEqual(result.total_flow_cfm, expected, places=5)

    def test_two_identical_parallel_fans_increase_total_flow(self):
        one = solve_operating_point(self.curve, 1, 2.5, 50.0)
        two = solve_operating_point(self.curve, 2, 2.5, 50.0)
        self.assertGreater(two.total_flow_cfm, one.total_flow_cfm)
        self.assertAlmostEqual(two.fan_static_pressure_mmh2o, two.system_pressure_drop_mmh2o, places=7)

    def test_bulk_air_temperature_rise_uses_ideal_energy_balance(self):
        result = solve_operating_point(self.curve, 1, 2.5, 50.0, heat_load_w=300.0)
        q_m3_s = result.total_flow_cfm * 0.00047194745
        expected = 300.0 / (1.204 * 1006.0 * q_m3_s)
        self.assertAlmostEqual(result.ideal_bulk_air_temperature_rise_c, expected, places=9)

    def test_invalid_system_reference_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "greater than 0"):
            solve_operating_point(self.curve, 1, 0.0, 50.0)

    def test_non_integer_fan_count_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "positive integer"):
            solve_operating_point(self.curve, 1.5, 2.5, 50.0)


class SystemCurveTests(unittest.TestCase):
    def setUp(self):
        self.system = SystemCurve(
            points=((0.0, 0.0), (20.0, 0.5), (40.0, 2.0), (60.0, 4.5), (80.0, 8.0), (100.0, 12.5)),
            source="synthetic measured-system-curve test",
        )
        self.fan = FanCurve(
            points=((0.0, 10.0), (50.0, 5.0), (100.0, 0.0)),
            source="synthetic fan test",
        )

    def test_system_curve_interpolation(self):
        self.assertAlmostEqual(self.system.pressure_at(30.0), 1.25)

    def test_system_curve_refuses_extrapolation(self):
        with self.assertRaisesRegex(ValueError, "extrapolation is disabled"):
            self.system.pressure_at(101.0)

    def test_system_curve_csv_loader(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "system.csv"
            csv_path.write_text(
                "flow_cfm,static_pressure_mmh2o\n0,0\n20,0.5\n40,2\n",
                encoding="utf-8",
            )
            loaded = SystemCurve.from_csv(csv_path)
            self.assertEqual(loaded.points, ((0.0, 0.0), (20.0, 0.5), (40.0, 2.0)))

    def test_rejects_decreasing_system_pressure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "bad_system.csv"
            csv_path.write_text(
                "flow_cfm,static_pressure_mmh2o\n0,0\n20,1\n40,0.5\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "non-decreasing"):
                SystemCurve.from_csv(csv_path)

    def test_measured_system_curve_operating_point_balances_pressure(self):
        result = solve_operating_point(self.fan, 1, system_curve=self.system)
        self.assertAlmostEqual(
            result.fan_static_pressure_mmh2o,
            result.system_pressure_drop_mmh2o,
            places=7,
        )
        self.assertIsNone(result.system_resistance_k_mmh2o_per_cfm2)
        self.assertEqual(result.system_curve_source, self.system.source)

    def test_parallel_fans_share_total_system_curve(self):
        one = solve_operating_point(self.fan, 1, system_curve=self.system)
        two = solve_operating_point(self.fan, 2, system_curve=self.system)
        self.assertGreater(two.total_flow_cfm, one.total_flow_cfm)
        self.assertAlmostEqual(
            two.fan_static_pressure_mmh2o,
            two.system_pressure_drop_mmh2o,
            places=7,
        )

    def test_does_not_extrapolate_short_system_curve(self):
        short = SystemCurve(
            points=((0.0, 0.0), (10.0, 0.5), (20.0, 2.0)),
            source="short synthetic curve",
        )
        with self.assertRaisesRegex(RuntimeError, "add higher-flow system measurements"):
            solve_operating_point(self.fan, 1, system_curve=short)

    def test_rejects_mixed_system_curve_and_quadratic_inputs(self):
        with self.assertRaisesRegex(ValueError, "not both"):
            solve_operating_point(
                self.fan, 1, system_pressure_mmh2o=2.0,
                system_reference_flow_cfm=50.0, system_curve=self.system,
            )


class SolverFailureClassificationTests(unittest.TestCase):
    """Categories must track the solver's real error messages."""

    FAN = FanCurve(((0.0, 10.0), (50.0, 5.0), (100.0, 0.0)))

    def classify(self, **kwargs):
        with self.assertRaises((ValueError, RuntimeError)) as raised:
            solve_operating_point(curve=self.FAN, fan_count=1, **kwargs)
        return classify_solver_failure(raised.exception)

    def test_no_positive_flow_root_message(self):
        # Not reachable with validated curves (system curves start at 0 mmH2O),
        # so pin the category to the solver's literal message instead.
        self.assertEqual(
            classify_solver_failure(RuntimeError(
                "No positive-flow operating point: system pressure meets/exceeds fan shutoff pressure")),
            "no_positive_flow_root",
        )

    def test_short_system_curve(self):
        short = SystemCurve(((0.0, 0.0), (10.0, 0.5)))
        self.assertEqual(self.classify(system_curve=short), "system_curve_range_too_short")

    def test_out_of_range_interpolation(self):
        with self.assertRaises(ValueError) as raised:
            self.FAN.pressure_at(150.0)
        self.assertEqual(classify_solver_failure(raised.exception), "fan_curve_range_failure")
        system = SystemCurve(((0.0, 0.0), (10.0, 1.0)))
        with self.assertRaises(ValueError) as raised:
            system.pressure_at(20.0)
        self.assertEqual(classify_solver_failure(raised.exception), "system_curve_range_failure")

    def test_unknown_error_is_generic(self):
        self.assertEqual(classify_solver_failure(ValueError("something else")), "solver_failure")


if __name__ == "__main__":
    unittest.main()
