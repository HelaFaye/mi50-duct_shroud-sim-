import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from photogrammetry_scale_fit import Constraint, fit_scale, load_constraints


class ScaleFitTests(unittest.TestCase):
    def test_recovers_uniform_scale(self):
        items = [
            Constraint("length", 10.0, 267.0, 0.5),
            Constraint("width", 4.0, 106.8, 0.2),
            Constraint("height", 2.0, 53.4, 0.2),
        ]
        scale, details, rms, max_percent = fit_scale(items)
        self.assertAlmostEqual(scale, 26.7, places=8)
        self.assertEqual(len(details), 3)
        self.assertAlmostEqual(rms, 0.0, places=8)
        self.assertAlmostEqual(max_percent, 0.0, places=8)

    def test_weighted_fit_gives_more_weight_to_precise_reference(self):
        items = [
            Constraint("precise", 10.0, 100.0, 0.01),
            Constraint("loose", 10.0, 110.0, 10.0),
        ]
        scale, _, _, _ = fit_scale(items)
        self.assertAlmostEqual(scale, 10.00001, places=4)

    def test_rejects_single_constraint(self):
        with self.assertRaisesRegex(ValueError, "At least two"):
            from photogrammetry_scale_fit import load_constraints
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "one.csv"
                path.write_text(
                    "reference_id,model_distance,known_distance_mm,uncertainty_mm\nref,1,10,0.1\n",
                    encoding="utf-8",
                )
                load_constraints(path)

    def test_rejects_nonpositive_uncertainty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            path.write_text(
                "reference_id,model_distance,known_distance_mm,uncertainty_mm\nref,1,10,0\nref2,2,20,0.1\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "positive"):
                load_constraints(path)


if __name__ == "__main__":
    unittest.main()
