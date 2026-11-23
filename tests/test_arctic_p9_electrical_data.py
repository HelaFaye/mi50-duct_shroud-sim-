"""Integrity checks for the ARCTIC P9 Max electrical PWM transcription.

The tests pin the source-file identity, table structure, displayed precision,
and selected source-reported observations. They skip when the CSV is absent.
"""
from __future__ import annotations

import csv
import hashlib
import math
import unittest
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data/fan_curves/arctic_p9_max_pwm_electrical.csv"
EXPECTED_SHA256 = "ed98b8526bc711b0b8ec15cf588784e794c0db62f986fd9e0c7bab5e2e4654f7"
EXPECTED_COLUMNS = [
    "source_table_row", "pwm_percent", "supply_voltage_v",
    "fan_speed_rpm", "current_a", "power_w",
]
EXPECTED_PWM = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
                20, 30, 40, 50, 60, 70, 80, 90, 100]
VOLTAGES = ["12.00", "7.00", "5.00"]
EXPECTED_ENDPOINTS = {
    "12.00": ("4476", "0.32", "3.85"),
    "7.00": ("3033", "0.18", "1.29"),
    "5.00": ("2250", "0.13", "0.67"),
}


class ArcticP9ElectricalDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CSV_PATH.is_file():
            raise unittest.SkipTest("ARCTIC P9 electrical source CSV is absent")
        cls.raw = CSV_PATH.read_bytes()
        with CSV_PATH.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            cls.columns = reader.fieldnames
            cls.rows = list(reader)

    def test_csv_sha256_is_pinned(self):
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), EXPECTED_SHA256)

    def test_schema_and_60_record_completeness(self):
        self.assertEqual(self.columns, EXPECTED_COLUMNS)
        self.assertEqual(len(self.rows), 60)

    def test_voltage_blocks_and_pwm_coverage(self):
        self.assertEqual(
            [row["supply_voltage_v"] for row in self.rows],
            [voltage for voltage in VOLTAGES for _ in EXPECTED_PWM],
        )
        grouped = defaultdict(list)
        for row in self.rows:
            grouped[row["supply_voltage_v"]].append(row)
        self.assertEqual(list(grouped), VOLTAGES)
        for voltage in VOLTAGES:
            records = grouped[voltage]
            self.assertEqual(len(records), 20)
            self.assertEqual([int(row["source_table_row"]) for row in records], list(range(1, 21)))
            self.assertEqual([int(row["pwm_percent"]) for row in records], EXPECTED_PWM)

    def test_voltage_and_pwm_keys_are_unique(self):
        keys = [(row["supply_voltage_v"], row["pwm_percent"]) for row in self.rows]
        self.assertEqual(len(keys), len(set(keys)))

    def test_numeric_values_are_finite_nonnegative_and_source_formatted(self):
        for row in self.rows:
            for field in ("supply_voltage_v", "current_a", "power_w"):
                self.assertRegex(row[field], r"^\d+\.\d{2}$")
                value = float(row[field])
                self.assertTrue(math.isfinite(value))
                self.assertGreaterEqual(value, 0.0)
            for field in ("source_table_row", "pwm_percent", "fan_speed_rpm"):
                value = int(row[field])
                self.assertGreaterEqual(value, 0)

    def test_100_percent_pwm_endpoints(self):
        for voltage, expected in EXPECTED_ENDPOINTS.items():
            row = next(
                item for item in self.rows
                if item["supply_voltage_v"] == voltage and item["pwm_percent"] == "100"
            )
            actual = (row["fan_speed_rpm"], row["current_a"], row["power_w"])
            self.assertEqual(actual, expected)

    def test_zero_to_five_percent_pwm_records_are_preserved(self):
        for voltage in VOLTAGES:
            for row in self.rows:
                if row["supply_voltage_v"] == voltage and int(row["pwm_percent"]) <= 5:
                    self.assertEqual(row["fan_speed_rpm"], "0")
                    self.assertEqual(row["current_a"], "0.00")
                    self.assertEqual(row["power_w"], "0.00")

    def test_rounded_low_pwm_electrical_values_are_preserved_verbatim(self):
        expected = {
            "12.00": ("0.01", "0.07"),
            "7.00": ("0.00", "0.02"),
            "5.00": ("0.00", "0.00"),
        }
        for voltage, electrical in expected.items():
            for pwm in range(6, 11):
                row = next(
                    item for item in self.rows
                    if item["supply_voltage_v"] == voltage
                    and int(item["pwm_percent"]) == pwm
                )
                self.assertEqual((row["current_a"], row["power_w"]), electrical)


if __name__ == "__main__":
    unittest.main()
