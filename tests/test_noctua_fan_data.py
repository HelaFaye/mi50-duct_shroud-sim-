import csv
import hashlib
import unittest
from collections import defaultdict
from pathlib import Path

from analysis.fan_operating_point import FanCurve


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "fan_curves"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class NoctuaFanDataTests(unittest.TestCase):
    def test_nf_a14_source_table_hash_and_native_points(self):
        path = DATA / "noctua_nf_a14_pwm_1500rpm_source.csv"
        self.assertEqual(sha256(path), "4a74752dbbc0a82952d532b827c462304eab86185b514685f6db4b930eb25254")
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 5)
        self.assertEqual(
            [(row["airflow_m3_h"], row["static_pressure_mmh2o"]) for row in rows],
            [
                ("140.20", "0.00"),
                ("104.10", "0.67"),
                ("69.70", "0.98"),
                ("31.20", "1.66"),
                ("0.00", "2.08"),
            ],
        )

    def test_nf_a14_normalized_curve_hash_and_solver_compatibility(self):
        path = DATA / "noctua_nf_a14_pwm_1500rpm_manufacturer.csv"
        self.assertEqual(sha256(path), "b2ca9397f7e327fd0fbb4e63ff8a595012a1809316eedb0524e603215bf214af")
        curve = FanCurve.from_csv(path)
        self.assertEqual(len(curve.points), 5)
        self.assertAlmostEqual(curve.shutoff_pressure_mmh2o, 2.08)
        self.assertAlmostEqual(curve.free_air_flow_cfm, 82.518603, places=6)
        self.assertAlmostEqual(curve.pressure_at(0.0), 2.08)
        self.assertAlmostEqual(curve.pressure_at(curve.free_air_flow_cfm), 0.0)

    def test_cybenetics_g2_raw_file_hash_and_record_count(self):
        path = DATA / "noctua_nf_a14x25_g2_cybenetics_25FN140A_raw.csv"
        self.assertEqual(sha256(path), "1a7266bafe0bb1acf3e2337f01b18735ab9d3585f193e5c58b5184008c132d8d")
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 72)
        self.assertEqual([int(row["source_row_index"]) for row in rows], list(range(1, 73)))
        self.assertEqual(sorted({int(row["pwm_percent"]) for row in rows}), list(range(20, 101, 10)))

        by_pwm = defaultdict(list)
        for row in rows:
            by_pwm[int(row["pwm_percent"])].append(row)
        self.assertEqual(set(by_pwm), set(range(20, 101, 10)))
        self.assertTrue(all(len(points) == 8 for points in by_pwm.values()))

    def test_cybenetics_g2_negative_endpoints_and_pressure_reversals_are_preserved(self):
        path = DATA / "noctua_nf_a14x25_g2_cybenetics_25FN140A_raw.csv"
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

        by_pwm = defaultdict(list)
        for row in rows:
            by_pwm[int(row["pwm_percent"])].append(row)

        # Eight source curves end at -0.01 mmAq; the 80% curve ends at +0.01 mmAq.
        self.assertEqual(
            sum(float(points[-1]["static_pressure_mmaq"]) == -0.01 for points in by_pwm.values()),
            8,
        )
        self.assertEqual(by_pwm[80][-1]["static_pressure_mmaq"], "0.01")

        # Keep all source pressure reversals; do not silently monotonize raw data.
        reversal_pwms = {
            pwm
            for pwm, points in by_pwm.items()
            if any(
                float(right["static_pressure_mmaq"]) > float(left["static_pressure_mmaq"])
                for left, right in zip(points, points[1:])
            )
        }
        self.assertEqual(reversal_pwms, {20, 60, 90, 100})
        self.assertEqual(by_pwm[100][3]["static_pressure_mmaq"], "1.31")
        self.assertEqual(by_pwm[100][4]["static_pressure_mmaq"], "1.34")

    def test_raw_g2_dataset_is_not_accidentally_a_solver_curve(self):
        path = DATA / "noctua_nf_a14x25_g2_cybenetics_25FN140A_raw.csv"
        with self.assertRaisesRegex(ValueError, "missing required CSV column"):
            FanCurve.from_csv(path)


if __name__ == "__main__":
    unittest.main()
