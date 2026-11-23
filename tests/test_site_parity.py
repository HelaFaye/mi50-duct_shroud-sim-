"""Cross-checks between the browser editor (site/js) and the Python reference.

* The JS operating-point solver must reproduce analysis/fan_operating_point.py.
* The embedded fan data module must be regenerated whenever a source CSV changes.
* The generated OpenSCAD model must render to the same solid as the JS mesh.

Node.js and OpenSCAD are optional locally; tests that need them are skipped
when the executable is absent. CI provides Node.
"""

from __future__ import annotations

import json
import math
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

from analysis.fan_operating_point import FanCurve, SystemCurve, solve_operating_point
from scripts import build_site_data

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
OPENSCAD = shutil.which("openscad")

P9 = FanCurve.from_csv(ROOT / "data/fan_curves/arctic_p9_max_4300rpm_manufacturer_cfd.csv")
NFA14 = FanCurve.from_csv(ROOT / "data/fan_curves/noctua_nf_a14_pwm_1500rpm_manufacturer.csv")
SYSTEM_TABLE = ((0.0, 0.0), (20.0, 0.4), (40.0, 1.5), (60.0, 3.6), (80.0, 6.5))


def _cases():
    cases = []
    for fan in (P9, NFA14):
        for count in (1, 2, 3):
            for pressure, flow in ((2.0, 50.0), (0.5, 40.0), (5.0, 20.0)):
                cases.append({"fan_points": fan.points, "fan_count": count, "heat_load_w": 300.0,
                              "system": {"type": "quadratic", "pressureMmH2O": pressure, "flowCfm": flow}})
            cases.append({"fan_points": fan.points, "fan_count": count, "heat_load_w": 250.0,
                          "system": {"type": "table", "points": SYSTEM_TABLE}})
    return cases


def _python_solve(case):
    fan = FanCurve(tuple(map(tuple, case["fan_points"])))
    system = case["system"]
    try:
        if system["type"] == "table":
            result = solve_operating_point(fan, case["fan_count"], heat_load_w=case["heat_load_w"],
                                           system_curve=SystemCurve(tuple(map(tuple, system["points"]))))
        else:
            result = solve_operating_point(fan, case["fan_count"], system_pressure_mmh2o=system["pressureMmH2O"],
                                           system_reference_flow_cfm=system["flowCfm"], heat_load_w=case["heat_load_w"])
    except (ValueError, RuntimeError) as exc:
        return {"error": str(exc)}
    return {"ok": result}


def _run_node(script: str, payload) -> object:
    completed = subprocess.run(
        [NODE, str(ROOT / script)], input=json.dumps(payload), capture_output=True, text=True,
        cwd=ROOT, timeout=60, check=True,
    )
    return json.loads(completed.stdout)


class SiteDataFreshnessTests(unittest.TestCase):
    def test_embedded_fan_data_matches_source_csvs(self):
        expected = build_site_data.build()
        actual = (ROOT / "site/js/fan_data.js").read_text(encoding="utf-8")
        self.assertEqual(actual, expected, "run python3 scripts/build_site_data.py")


@unittest.skipUnless(NODE, "Node.js is not installed")
class JsSolverParityTests(unittest.TestCase):
    def test_js_solver_reproduces_python_solver(self):
        cases = _cases()
        js_results = _run_node("site/tests/solve_cases.mjs", cases)
        self.assertEqual(len(js_results), len(cases))
        solved = 0
        for case, js in zip(cases, js_results):
            py = _python_solve(case)
            with self.subTest(fan_count=case["fan_count"], system=case["system"]["type"]):
                self.assertEqual("ok" in js, "ok" in py, f"JS {js} vs Python {py}")
                if "ok" not in py:
                    continue
                solved += 1
                for field in ("total_flow_cfm", "per_fan_flow_cfm", "fan_static_pressure_mmh2o",
                              "system_pressure_drop_mmh2o", "ideal_bulk_air_temperature_rise_c"):
                    self.assertTrue(
                        math.isclose(js["ok"][field], getattr(py["ok"], field), rel_tol=1e-12, abs_tol=1e-12),
                        f"{field}: JS {js['ok'][field]!r} vs Python {getattr(py['ok'], field)!r}",
                    )
        self.assertGreaterEqual(solved, 20)


def _stl_volume_and_bounds(path: Path):
    data = path.read_bytes()
    vertices = []
    if data[:5] == b"solid":
        for line in data.decode("ascii", "replace").splitlines():
            parts = line.split()
            if parts and parts[0] == "vertex":
                vertices.append(tuple(map(float, parts[1:4])))
    else:
        count = struct.unpack("<I", data[80:84])[0]
        for i in range(count):
            f = struct.unpack("<12f", data[84 + 50 * i: 84 + 50 * i + 48])
            vertices.extend((f[3:6], f[6:9], f[9:12]))
    volume = 0.0
    for i in range(0, len(vertices), 3):
        a, b, c = vertices[i: i + 3]
        volume += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
                   + a[2] * (b[0] * c[1] - b[1] * c[0]))
    lows = [min(v[k] for v in vertices) for k in range(3)]
    highs = [max(v[k] for v in vertices) for k in range(3)]
    return volume / 6.0, lows, highs


@unittest.skipUnless(NODE and OPENSCAD, "Node.js and OpenSCAD are both required")
class OpenScadGeometryParityTests(unittest.TestCase):
    def test_generated_scad_renders_the_same_solid_as_the_browser_mesh(self):
        overrides = {"fan_count": 2, "fan_size_mm": 60, "outlet_offset_y_mm": 6, "outlet_offset_z_mm": -2}
        with tempfile.TemporaryDirectory() as tmp:
            scad = Path(tmp) / "shroud.scad"
            stl = Path(tmp) / "shroud.stl"
            mesh = _run_node("site/tests/export_case.mjs", {"overrides": overrides, "scad_path": str(scad)})
            subprocess.run([OPENSCAD, "-o", str(stl), str(scad)], check=True, capture_output=True, timeout=600)
            volume, lows, highs = _stl_volume_and_bounds(stl)
        self.assertTrue(math.isclose(volume, mesh["volume_mm3"], rel_tol=1e-3), f"{volume} vs {mesh['volume_mm3']}")
        for got, want in zip(lows + highs, mesh["bounds"]["min"] + mesh["bounds"]["max"]):
            self.assertAlmostEqual(got, want, places=2)


if __name__ == "__main__":
    unittest.main()
