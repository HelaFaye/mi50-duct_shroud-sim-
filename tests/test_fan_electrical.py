"""Tests for local P9 electrical telemetry loading and RPM interpolation."""
from __future__ import annotations

import csv
import hashlib
import tempfile
import unittest
from pathlib import Path

from analysis.fan_electrical import (
    ELECTRICAL_COLUMNS,
    estimate_fan_electrical,
    load_fan_electrical_dataset,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_CSV = ROOT / "data/fan_curves/arctic_p9_max_pwm_electrical.csv"
EXPECTED_SHA256 = "ed98b8526bc711b0b8ec15cf588784e794c0db62f986fd9e0c7bab5e2e4654f7"


def write_synthetic_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ELECTRICAL_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def row(table_row, pwm, voltage, rpm, current, power):
    return {
        "source_table_row": str(table_row),
        "pwm_percent": str(pwm),
        "supply_voltage_v": f"{voltage:.2f}",
        "fan_speed_rpm": str(rpm),
        "current_a": f"{current:.2f}",
        "power_w": f"{power:.2f}",
    }


class P9ElectricalSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE_CSV.is_file():
            raise unittest.SkipTest("P9 electrical source CSV is absent")
        raw = SOURCE_CSV.read_bytes()
        if hashlib.sha256(raw).hexdigest() != EXPECTED_SHA256:
            raise AssertionError("local P9 electrical CSV hash does not match audited transcription")
        cls.dataset = load_fan_electrical_dataset(SOURCE_CSV)

    def test_raw_csv_hash_and_record_count(self):
        self.assertEqual(self.dataset.source_sha256, EXPECTED_SHA256)
        self.assertEqual(self.dataset.record_count, 60)

    def test_exact_source_voltage_tables_are_available(self):
        self.assertEqual(set(self.dataset.curves), {5.0, 7.0, 12.0})
        self.assertTrue(all(len(curve.points) >= 2 for curve in self.dataset.curves.values()))

    def test_repeated_rpm_plateau_is_consolidated_without_losing_source_rows(self):
        curve = self.dataset.curves[12.0]
        plateau = next(point for point in curve.points if point.fan_speed_rpm == 426)
        self.assertEqual(plateau.pwm_percent, (6, 7, 8, 9, 10))
        self.assertEqual(plateau.source_table_rows, (7, 8, 9, 10, 11))
        self.assertEqual((plateau.current_a, plateau.power_w), (0.01, 0.07))

    def test_4300_rpm_12v_regression_estimate(self):
        result = estimate_fan_electrical(self.dataset, 12.0, 4300.0)
        self.assertEqual(result["interpolation"]["method"], "linear_interpolation_in_rpm")
        self.assertAlmostEqual(result["per_fan"]["current_a"], 0.2854901960784314, places=13)
        self.assertAlmostEqual(result["per_fan"]["power_w"], 3.4556022408963585, places=13)

    def test_exact_4119_rpm_observation_is_not_relabelled_as_interpolated(self):
        result = estimate_fan_electrical(self.dataset, 12.0, 4119.0)
        self.assertEqual(result["interpolation"]["method"], "source_observation")
        self.assertEqual(result["per_fan"], {"current_a": 0.25, "power_w": 3.05})

    def test_7v_low_pwm_rounded_zero_current_and_nonzero_power_are_preserved(self):
        result = estimate_fan_electrical(self.dataset, 7.0, 228.0)
        self.assertEqual(result["per_fan"], {"current_a": 0.0, "power_w": 0.02})

    def test_5v_low_pwm_zero_current_and_power_are_preserved(self):
        result = estimate_fan_electrical(self.dataset, 5.0, 138.0)
        self.assertEqual(result["per_fan"], {"current_a": 0.0, "power_w": 0.0})

    def test_array_estimate_scales_both_independent_telemetry_values(self):
        one = estimate_fan_electrical(self.dataset, 12.0, 4300.0, fan_count=1)
        three = estimate_fan_electrical(self.dataset, 12.0, 4300.0, fan_count=3)
        self.assertAlmostEqual(
            three["parallel_array_estimate"]["current_a"],
            one["per_fan"]["current_a"] * 3,
        )
        self.assertAlmostEqual(
            three["parallel_array_estimate"]["power_w"],
            one["per_fan"]["power_w"] * 3,
        )


class SyntheticElectricalValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "electrical.csv"
        write_synthetic_csv(self.path, [
            row(1, 0, 12, 0, 0.00, 0.00),
            row(2, 20, 12, 1000, 0.10, 1.20),
            row(1, 0, 7, 0, 0.00, 0.00),
            row(2, 20, 7, 800, 0.05, 0.35),
        ])

    def tearDown(self):
        self.temp.cleanup()

    def test_interpolates_current_and_power_independently(self):
        dataset = load_fan_electrical_dataset(self.path)
        result = estimate_fan_electrical(dataset, 12.0, 500.0)
        self.assertAlmostEqual(result["per_fan"]["current_a"], 0.05)
        self.assertAlmostEqual(result["per_fan"]["power_w"], 0.60)

    def test_refuses_rpm_extrapolation_below_and_above_table(self):
        write_synthetic_csv(self.path, [
            row(1, 10, 12, 100, 0.02, 0.24),
            row(2, 20, 12, 1000, 0.10, 1.20),
        ])
        dataset = load_fan_electrical_dataset(self.path)
        for rpm in (99, 1001):
            with self.subTest(rpm=rpm):
                with self.assertRaisesRegex(ValueError, "extrapolation is disabled"):
                    estimate_fan_electrical(dataset, 12.0, rpm)

    def test_refuses_voltage_interpolation(self):
        dataset = load_fan_electrical_dataset(self.path)
        with self.assertRaisesRegex(ValueError, "voltage interpolation is disabled"):
            estimate_fan_electrical(dataset, 10.0, 500.0)

    def test_refuses_invalid_fan_count(self):
        dataset = load_fan_electrical_dataset(self.path)
        for count in (0, -1, 1.5, True):
            with self.subTest(count=count):
                with self.assertRaisesRegex(ValueError, "fan_count"):
                    estimate_fan_electrical(dataset, 12.0, 500.0, count)

    def test_refuses_nonfinite_rpm(self):
        dataset = load_fan_electrical_dataset(self.path)
        for rpm in (float("nan"), float("inf")):
            with self.subTest(rpm=rpm):
                with self.assertRaisesRegex(ValueError, "target_rpm"):
                    estimate_fan_electrical(dataset, 12.0, rpm)

    def test_conflicting_telemetry_at_duplicate_rpm_is_rejected(self):
        write_synthetic_csv(self.path, [
            row(1, 0, 12, 0, 0.00, 0.00),
            row(2, 5, 12, 0, 0.01, 0.02),
            row(3, 20, 12, 1000, 0.10, 1.20),
        ])
        with self.assertRaisesRegex(ValueError, "conflicting current/power"):
            load_fan_electrical_dataset(self.path)

    def test_duplicate_voltage_pwm_key_is_rejected(self):
        write_synthetic_csv(self.path, [
            row(1, 0, 12, 0, 0.00, 0.00),
            row(2, 0, 12, 1000, 0.10, 1.20),
        ])
        with self.assertRaisesRegex(ValueError, "duplicate PWM"):
            load_fan_electrical_dataset(self.path)

    def test_source_row_sequence_must_be_consecutive_per_voltage(self):
        write_synthetic_csv(self.path, [
            row(1, 0, 12, 0, 0.00, 0.00),
            row(3, 20, 12, 1000, 0.10, 1.20),
        ])
        with self.assertRaisesRegex(ValueError, "source_table_row must run consecutively"):
            load_fan_electrical_dataset(self.path)

    def test_rows_with_missing_or_extra_fields_are_rejected(self):
        header = ",".join(ELECTRICAL_COLUMNS)
        malformed_rows = {
            "missing": "1,0,12.00,0,0.00",
            "extra": "1,0,12.00,0,0.00,0.00,unexpected",
        }

        for label, malformed_row in malformed_rows.items():
            with self.subTest(label=label):
                self.path.write_text(
                    header + "\n" + malformed_row + "\n",
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ValueError, "exactly 6 fields"):
                    load_fan_electrical_dataset(self.path)

    def test_invalid_source_table_row_values_are_rejected(self):
        for value in ("0", "1.5", "not-an-integer"):
            with self.subTest(value=value):
                rows = [
                    row(1, 0, 12, 0, 0.00, 0.00),
                    row(2, 20, 12, 1000, 0.10, 1.20),
                ]
                rows[0]["source_table_row"] = value
                write_synthetic_csv(self.path, rows)

                with self.assertRaisesRegex(ValueError, "source_table_row"):
                    load_fan_electrical_dataset(self.path)

    def test_missing_or_reordered_columns_are_rejected(self):
        self.path.write_text("pwm_percent,supply_voltage_v\n0,12\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "expected columns in this exact order"):
            load_fan_electrical_dataset(self.path)


if __name__ == "__main__":
    unittest.main()
