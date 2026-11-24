"""Integrity checks for the ARCTIC P8/P12/P14 Max CFD-workbook imports.

The workbooks are not redistributed, so these tests work from the committed
verbatim source tables: every solver CSV must equal its source table plus only
the transformations declared in scripts/extract_arctic_cfd_workbooks.py.
"""

from __future__ import annotations

import csv
import hashlib
import unittest
from pathlib import Path

from analysis.fan_operating_point import FanCurve
from scripts.extract_arctic_cfd_workbooks import TRANSFORMS, WORKBOOKS, apply_transforms, render

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "fan_curves"

PINNED = {
    "arctic_p8_max_3000rpm_manufacturer_cfd": (
        "44c5fb34165267cdb73a767269bca46515b9f52c31c5b7b7cbdc4a6732d3bf50",
        "c109e7fd9bb1ae52b64bad825d11c2a1aad90caa2f3d48d3048018be10daafa6",
    ),
    "arctic_p12_max_3300rpm_manufacturer_cfd": (
        "190415ee09404e03c0174fd509b5ece286e866487ecd028d36f6e1141ce09b71",
        "851a11d151994d1b75510916fadee215a356b9db3715acddabcd56c1a7e86326",
    ),
    "arctic_p14_max_2800rpm_manufacturer_cfd": (
        "70d8c1a921a09c69471ab8e73d609050a03d4a0ee8c2d54fb3b19640b7a94a1d",
        "cd1356d3bb0b8b5126745de45acb3eeb55356fb290e0ad363f30daec7a48bde4",
    ),
}


def _source_rows(fan_id):
    with (DATA / f"{fan_id}_source.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [(int(r["worksheet_row"]), r["flow_cfm"], r["static_pressure_mmh2o"]) for r in reader]


class ArcticCfdWorkbookDataTests(unittest.TestCase):
    def test_files_match_pinned_hashes(self):
        for fan_id, (source_hash, solver_hash) in PINNED.items():
            with self.subTest(fan=fan_id):
                self.assertEqual(hashlib.sha256((DATA / f"{fan_id}_source.csv").read_bytes()).hexdigest(), source_hash)
                self.assertEqual(hashlib.sha256((DATA / f"{fan_id}.csv").read_bytes()).hexdigest(), solver_hash)

    def test_solver_csv_is_source_plus_declared_transforms_only(self):
        for fan_id in WORKBOOKS:
            with self.subTest(fan=fan_id):
                derived = render(["flow_cfm", "static_pressure_mmh2o"],
                                 apply_transforms(_source_rows(fan_id), TRANSFORMS[fan_id]))
                self.assertEqual(derived, (DATA / f"{fan_id}.csv").read_bytes())

    def test_solver_curves_load_and_keep_published_endpoints(self):
        expected = {  # (shutoff mmH2O, free-air CFM) from the workbook tables
            "arctic_p8_max_3000rpm_manufacturer_cfd": (5.71, 50.31),
            "arctic_p12_max_3300rpm_manufacturer_cfd": (5.31, 83.84),
            "arctic_p14_max_2800rpm_manufacturer_cfd": (4.4867513371028842, 109.8478463517346),
        }
        for fan_id, (shutoff, free_air) in expected.items():
            with self.subTest(fan=fan_id):
                curve = FanCurve.from_csv(DATA / f"{fan_id}.csv")
                self.assertEqual(curve.shutoff_pressure_mmh2o, shutoff)
                self.assertEqual(curve.free_air_flow_cfm, free_air)

    def test_source_tables_retain_the_rows_the_solver_cannot_use(self):
        p8 = _source_rows("arctic_p8_max_3000rpm_manufacturer_cfd")
        self.assertEqual(p8[3][1:], p8[4][1:])  # duplicate 6.51 CFM row kept verbatim
        p12 = _source_rows("arctic_p12_max_3300rpm_manufacturer_cfd")
        self.assertEqual(p12[-1][1:], ("83.84", "0.02"))  # non-zero terminal pressure kept verbatim

    def test_every_transform_has_a_reason(self):
        for fan_id, transforms in TRANSFORMS.items():
            for row, (_kind, _value, reason) in transforms.items():
                with self.subTest(fan=fan_id, row=row):
                    self.assertGreater(len(reason), 20)


if __name__ == "__main__":
    unittest.main()
