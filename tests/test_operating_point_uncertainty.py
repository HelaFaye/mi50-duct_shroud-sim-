import contextlib
import copy
import hashlib
import io
import json
import math
import tempfile
import unittest
from pathlib import Path

from analysis.fan_operating_point import FanCurve, SystemCurve, solve_operating_point
from analysis.operating_point_uncertainty import (
    _apply_draws,
    _dkw_epsilon,
    _dkw_quantile_precision,
    main as uncertainty_main,
    quantile_type7,
    run_uncertainty,
)


CONDITION = {
    "configuration_id": "SYNTHETIC-RIG-01",
    "fan_model": "synthetic-fan",
    "fan_count": 1,
    "rpm": 4000.0,
    "voltage_v": 12.0,
    "pwm_percent": 100.0,
}
BASIS = {
    "flow_basis": "actual_volumetric_flow",
    "flow_reference_conditions": {
        "temperature_c": 23.0,
        "absolute_pressure_kpa": 101.325,
        "relative_humidity_percent": 50.0,
    },
    "pressure_basis": "static_pressure",
    "pressure_reference": "SYNTHETIC: matched static-pressure measurement planes",
    "velocity_pressure_correction": "SYNTHETIC: no correction required by fixture",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(source_id, units, distribution, targets, record="SYNTHETIC source record"):
    return {
        "id": source_id,
        "evaluation_method": "type_b",
        "source_record": record,
        "original_statement": "SYNTHETIC: assigned zero-mean correction with the listed parameters",
        "conversion_notes": "SYNTHETIC: no conversion; parameters are already in the declared PDF units",
        "units": units,
        "distribution": distribution,
        "targets": targets,
    }


def normal(sd, mean=0.0):
    return {"family": "normal", "parameters": {"mean": mean, "standard_deviation": sd}}


def fixture_sidecar(curve_type, curve_path, held_fixed=False):
    if curve_type == "fan":
        coverage = [
            {"row_index": 1, "flow_cfm": "fixed_by_definition", "static_pressure_mmh2o": "held_fixed_assumption" if held_fixed else "sampled"},
            {"row_index": 2, "flow_cfm": "held_fixed_assumption" if held_fixed else "sampled", "static_pressure_mmh2o": "held_fixed_assumption" if held_fixed else "sampled"},
            {"row_index": 3, "flow_cfm": "held_fixed_assumption" if held_fixed else "sampled", "static_pressure_mmh2o": "fixed_by_definition"},
        ]
        if held_fixed:
            coverage[0]["held_fixed_reasons"] = {"static_pressure_mmh2o": "SYNTHETIC fixture deliberately excludes this coordinate"}
            coverage[1]["held_fixed_reasons"] = {
                "flow_cfm": "SYNTHETIC fixture deliberately excludes this coordinate",
                "static_pressure_mmh2o": "SYNTHETIC fixture deliberately excludes this coordinate",
            }
            coverage[2]["held_fixed_reasons"] = {"flow_cfm": "SYNTHETIC fixture deliberately excludes this coordinate"}
            sources = []
        else:
            sources = [
                source("shared_flow_scale", "dimensionless", normal(0.001), [
                    {"rows": [2, 3], "quantity": "flow_cfm", "effect": "relative_scale", "coefficient": 1.0}
                ]),
                source("fan_p1", "mmH2O", normal(0.005), [
                    {"rows": [1], "quantity": "static_pressure_mmh2o", "effect": "additive", "coefficient": 1.0}
                ]),
                source("fan_q2", "CFM", normal(0.02), [
                    {"rows": [2], "quantity": "flow_cfm", "effect": "additive", "coefficient": 1.0}
                ]),
                source("fan_p2", "mmH2O", normal(0.005), [
                    {"rows": [2], "quantity": "static_pressure_mmh2o", "effect": "additive", "coefficient": 1.0}
                ]),
            ]
    else:
        coverage = [
            {"row_index": 1, "flow_cfm": "fixed_by_definition", "static_pressure_mmh2o": "fixed_by_definition"},
            {"row_index": 2, "flow_cfm": "sampled" if not held_fixed else "held_fixed_assumption", "static_pressure_mmh2o": "sampled" if not held_fixed else "held_fixed_assumption"},
            {"row_index": 3, "flow_cfm": "sampled" if not held_fixed else "held_fixed_assumption", "static_pressure_mmh2o": "sampled" if not held_fixed else "held_fixed_assumption"},
        ]
        if held_fixed:
            coverage[1]["held_fixed_reasons"] = {
                "flow_cfm": "SYNTHETIC fixture deliberately excludes this coordinate",
                "static_pressure_mmh2o": "SYNTHETIC fixture deliberately excludes this coordinate",
            }
            coverage[2]["held_fixed_reasons"] = {
                "flow_cfm": "SYNTHETIC fixture deliberately excludes this coordinate",
                "static_pressure_mmh2o": "SYNTHETIC fixture deliberately excludes this coordinate",
            }
            sources = []
        else:
            sources = [
                source("shared_flow_scale", "dimensionless", normal(0.001), [
                    {"rows": [2, 3], "quantity": "flow_cfm", "effect": "relative_scale", "coefficient": 1.0}
                ]),
                source("system_p2", "mmH2O", normal(0.01), [
                    {"rows": [2], "quantity": "static_pressure_mmh2o", "effect": "additive", "coefficient": 1.0}
                ]),
                source("system_p3", "mmH2O", normal(0.02), [
                    {"rows": [3], "quantity": "static_pressure_mmh2o", "effect": "additive", "coefficient": 1.0}
                ]),
            ]
    return {
        "schema_version": "1.0",
        "curve_type": curve_type,
        "central_values": {"path": str(curve_path.relative_to(curve_path.parents[2])), "sha256": digest(curve_path)},
        "provenance": {
            "classification": "synthetic_test_fixture",
            "description": "SYNTHETIC TEST DATA ONLY; not measured MI50 data",
            "source_record": "SYNTHETIC unit-test fixture",
        },
        "measurement_basis": copy.deepcopy(BASIS),
        "operating_condition": copy.deepcopy(CONDITION),
        "distinct_source_ids_independent": True,
        "known_dependencies": [],
        "coordinate_coverage": coverage,
        "uncertainty_sources": sources,
    }


class OperatingPointUncertaintyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "data/fan_curves").mkdir(parents=True)
        (self.root / "data/system_curves").mkdir(parents=True)
        self.fan_path = self.root / "data/fan_curves/synthetic_fan.csv"
        self.system_path = self.root / "data/system_curves/synthetic_system.csv"
        self.fan_path.write_text(
            "flow_cfm,static_pressure_mmh2o\n0,10\n50,5\n100,0\n", encoding="utf-8"
        )
        self.system_path.write_text(
            "flow_cfm,static_pressure_mmh2o\n0,0\n50,2\n100,8\n", encoding="utf-8"
        )
        self.fan_sidecar = self.root / "data/fan_curves/synthetic_fan.uncertainty.json"
        self.system_sidecar = self.root / "data/system_curves/synthetic_system.uncertainty.json"
        self.write_sidecars()

    def tearDown(self):
        self.temp.cleanup()

    def write_sidecars(self, held_fixed=False):
        fan = fixture_sidecar("fan", self.fan_path, held_fixed=held_fixed)
        system = fixture_sidecar("system", self.system_path, held_fixed=held_fixed)
        self.fan_sidecar.write_text(json.dumps(fan, indent=2), encoding="utf-8")
        self.system_sidecar.write_text(json.dumps(system, indent=2), encoding="utf-8")

    def run_model(self, **overrides):
        args = {
            "fan_curve_path": self.fan_path,
            "system_curve_path": self.system_path,
            "fan_sidecar_path": self.fan_sidecar,
            "system_sidecar_path": self.system_sidecar,
            "repo_root": self.root,
            "fan_count": 1,
            "fan_model": CONDITION["fan_model"],
            "configuration_id": CONDITION["configuration_id"],
            "rpm": CONDITION["rpm"],
            "voltage_v": CONDITION["voltage_v"],
            "pwm_percent": CONDITION["pwm_percent"],
            "trials": 128,
            "seed": 20261121,
        }
        args.update(overrides)
        return run_uncertainty(**args)

    def test_all_sources_are_drawn_even_when_an_early_source_is_invalid(self):
        class CountingRng:
            def __init__(self):
                self.calls = 0

            def normalvariate(self, mean, standard_deviation):
                self.calls += 1
                return -1.0 if self.calls == 1 else 0.25

        sources = {
            "a_invalid_scale": {
                "distribution": {"family": "normal", "parameters": {"mean": 0.0, "standard_deviation": 1.0}},
                "targets": [{"curve_type": "fan", "row_index": 2, "quantity": "flow_cfm", "effect": "relative_scale", "coefficient": 1.0}],
            },
            "b_later_source": {
                "distribution": {"family": "normal", "parameters": {"mean": 0.0, "standard_deviation": 1.0}},
                "targets": [{"curve_type": "system", "row_index": 2, "quantity": "flow_cfm", "effect": "relative_scale", "coefficient": 1.0}],
            },
        }
        rng = CountingRng()
        result = _apply_draws(
            ((0.0, 10.0), (50.0, 5.0), (100.0, 0.0)),
            ((0.0, 0.0), (50.0, 2.0), (100.0, 8.0)),
            sources,
            rng,
        )
        self.assertEqual(result, "invalid_source_effect")
        self.assertEqual(rng.calls, 2)

    def test_one_valid_trial_is_inconclusive_and_suppresses_intervals(self):
        self.write_sidecars(held_fixed=True)
        report = self.run_model(allow_held_fixed=True, trials=1)
        self.assertEqual(report["run"]["valid_trials"], 1)
        self.assertFalse(report["run"]["sufficient_valid_samples_for_sample_covariance"])
        self.assertEqual(report["status"], "inconclusive")
        self.assertIsNone(report["outputs"])
        self.assertIsNone(report["joint_output_covariance"]["matrix"])

    def test_seeded_run_is_reproducible_and_uses_fixed_attempt_budget(self):
        first = self.run_model(trials=500)
        second = self.run_model(trials=500)
        self.assertEqual(first["run"], second["run"])
        self.assertEqual(first["outputs"], second["outputs"])
        self.assertEqual(first["run"]["attempted_trials"], 500)
        self.assertEqual(first["run"]["valid_trials"] + first["run"]["failed_trials"], 500)
        self.assertEqual(sum(first["run"]["outcome_counts"].values()), 500)
        self.assertEqual(first["status"], "conditional_result")

    def test_shared_source_id_is_merged_across_both_sidecars(self):
        report = self.run_model(trials=50)
        shared = next(source for source in report["inputs"]["uncertainty_sources"] if source["id"] == "shared_flow_scale")
        self.assertEqual(shared["target_count"], 4)

    def test_conflicting_shared_source_definitions_are_rejected(self):
        system = json.loads(self.system_sidecar.read_text(encoding="utf-8"))
        shared = next(source for source in system["uncertainty_sources"] if source["id"] == "shared_flow_scale")
        shared["distribution"] = normal(0.002)
        self.system_sidecar.write_text(json.dumps(system), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "conflicting definitions"):
            self.run_model()

    def test_csv_hash_mismatch_is_rejected(self):
        with self.fan_path.open("a", encoding="utf-8") as handle:
            handle.write("\n")
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            self.run_model()

    def test_unknown_schema_version_is_rejected(self):
        fan = json.loads(self.fan_sidecar.read_text(encoding="utf-8"))
        fan["schema_version"] = "2.0"
        self.fan_sidecar.write_text(json.dumps(fan), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unsupported schema_version"):
            self.run_model()

    def test_unknown_sidecar_field_is_rejected(self):
        fan = json.loads(self.fan_sidecar.read_text(encoding="utf-8"))
        fan["surprise_default"] = 0
        self.fan_sidecar.write_text(json.dumps(fan), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unsupported field"):
            self.run_model()

    def test_known_cross_source_dependency_is_rejected(self):
        fan = json.loads(self.fan_sidecar.read_text(encoding="utf-8"))
        fan["known_dependencies"] = [{"source_a": "fan_p1", "source_b": "fan_p2"}]
        self.fan_sidecar.write_text(json.dumps(fan), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "dependencies are unsupported"):
            self.run_model()

    def test_distinct_source_independence_must_be_explicit(self):
        fan = json.loads(self.fan_sidecar.read_text(encoding="utf-8"))
        fan["distinct_source_ids_independent"] = False
        self.fan_sidecar.write_text(json.dumps(fan), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "requires an explicit"):
            self.run_model()

    def test_source_ids_must_be_whitespace_free(self):
        fan = json.loads(self.fan_sidecar.read_text(encoding="utf-8"))
        fan["uncertainty_sources"][0]["id"] = "shared flow scale"
        self.fan_sidecar.write_text(json.dumps(fan), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "stable identifier"):
            self.run_model()

    def test_sampled_coordinate_without_source_is_rejected(self):
        fan = json.loads(self.fan_sidecar.read_text(encoding="utf-8"))
        fan["uncertainty_sources"] = [s for s in fan["uncertainty_sources"] if s["id"] != "fan_p1"]
        self.fan_sidecar.write_text(json.dumps(fan), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "has no uncertainty source"):
            self.run_model()

    def test_solver_relevant_fan_anchor_cannot_be_targeted(self):
        fan = json.loads(self.fan_sidecar.read_text(encoding="utf-8"))
        fan["uncertainty_sources"].append(source(
            "bad_anchor", "CFM", normal(0.1), [
                {"rows": [1], "quantity": "flow_cfm", "effect": "additive", "coefficient": 1.0}
            ]
        ))
        self.fan_sidecar.write_text(json.dumps(fan), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "is not marked sampled"):
            self.run_model()

    def test_operating_condition_mismatch_is_rejected(self):
        system = json.loads(self.system_sidecar.read_text(encoding="utf-8"))
        system["operating_condition"]["rpm"] = 3900.0
        self.system_sidecar.write_text(json.dumps(system), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "operating-condition metadata do not match"):
            self.run_model()

    def test_run_operating_condition_must_match_sidecar(self):
        with self.assertRaisesRegex(ValueError, "does not match sidecar"):
            self.run_model(rpm=3900.0)

    def test_pressure_and_flow_measurement_basis_must_match(self):
        system = json.loads(self.system_sidecar.read_text(encoding="utf-8"))
        system["measurement_basis"]["pressure_reference"] = "different reference planes"
        self.system_sidecar.write_text(json.dumps(system), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "measurement bases are incompatible"):
            self.run_model()

    def test_nonzero_mean_correction_distribution_is_rejected(self):
        fan = json.loads(self.fan_sidecar.read_text(encoding="utf-8"))
        next(s for s in fan["uncertainty_sources"] if s["id"] == "fan_p1")["distribution"] = normal(0.1, mean=0.01)
        self.fan_sidecar.write_text(json.dumps(fan), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "mean=0"):
            self.run_model()

    def test_held_fixed_coordinates_require_explicit_opt_in(self):
        self.write_sidecars(held_fixed=True)
        with self.assertRaisesRegex(ValueError, "held_fixed_assumption"):
            self.run_model()

    def test_held_fixed_opt_in_is_reported_as_omitted_uncertainty(self):
        self.write_sidecars(held_fixed=True)
        report = self.run_model(allow_held_fixed=True)
        self.assertEqual(report["status"], "conditional_result_with_omitted_uncertainty")
        self.assertGreater(len(report["inputs"]["omitted_uncertainty"]), 0)

    def test_zero_uncertainty_recovers_deterministic_solution(self):
        self.write_sidecars(held_fixed=True)
        report = self.run_model(allow_held_fixed=True, trials=10)
        deterministic = solve_operating_point(
            FanCurve.from_csv(self.fan_path), 1,
            system_curve=SystemCurve.from_csv(self.system_path),
        )
        stats = report["outputs"]["total_flow_cfm"]
        self.assertAlmostEqual(stats["mean"], deterministic.total_flow_cfm, places=8)
        self.assertAlmostEqual(stats["standard_uncertainty"], 0.0, places=12)

    def test_joint_covariance_and_correlation_are_reported(self):
        report = self.run_model(trials=500)
        covariance = report["joint_output_covariance"]["matrix"]
        correlation = report["joint_output_correlation"]["matrix"]
        self.assertEqual(len(covariance), 4)
        self.assertEqual(len(covariance[0]), 4)
        self.assertAlmostEqual(covariance[0][1], covariance[1][0], places=12)
        self.assertIsNotNone(correlation[0][0])

    def test_minimum_valid_fraction_can_mark_run_inconclusive(self):
        report = self.run_model(trials=200, minimum_valid_fraction=1.0)
        if report["run"]["valid_fraction"] < 1.0:
            self.assertEqual(report["status"], "inconclusive")
        else:
            self.assertEqual(report["run"]["minimum_valid_fraction_met"], True)

    def test_type7_quantile(self):
        self.assertAlmostEqual(quantile_type7([0.0, 10.0, 20.0, 30.0], 0.25), 7.5)
        self.assertEqual(quantile_type7([5.0], 0.95), 5.0)

    def test_dkw_quantile_precision_uses_conservative_order_statistics(self):
        result = _dkw_quantile_precision(list(range(1, 101)), 0.05, 0.02)
        bounds = result["confidence_bounds"]
        self.assertEqual(result["type7_estimate"], 5.95)
        self.assertEqual(bounds["lower_order_statistic_rank_1_based"], 3)
        # At n*(p+epsilon)=7 exactly, the conservative right-inverse bound
        # is the next order statistic (floor(7)+1), not rank 7.
        self.assertEqual(bounds["upper_order_statistic_rank_1_based"], 8)
        self.assertEqual(bounds["lower"], 3)
        self.assertEqual(bounds["upper"], 8)
        self.assertFalse(bounds["lower_unbounded"])
        self.assertFalse(bounds["upper_unbounded"])

    def test_dkw_quantile_precision_reports_unbounded_tail_limits(self):
        lower_unbounded = _dkw_quantile_precision(list(range(1, 11)), 0.05, 0.05)
        lower_bounds = lower_unbounded["confidence_bounds"]
        self.assertTrue(lower_bounds["lower_unbounded"])
        self.assertIsNone(lower_bounds["lower"])
        self.assertIsNone(lower_bounds["lower_order_statistic_rank_1_based"])
        self.assertFalse(lower_bounds["upper_unbounded"])

        upper_unbounded = _dkw_quantile_precision(list(range(1, 11)), 0.95, 0.05)
        upper_bounds = upper_unbounded["confidence_bounds"]
        self.assertTrue(upper_bounds["upper_unbounded"])
        self.assertIsNone(upper_bounds["upper"])
        self.assertIsNone(upper_bounds["upper_order_statistic_rank_1_based"])
        self.assertFalse(upper_bounds["lower_unbounded"])

    def test_dkw_epsilon_is_familywise_across_four_marginals(self):
        expected = math.sqrt(math.log(2.0 * 4 / 0.05) / (2.0 * 1000))
        self.assertAlmostEqual(_dkw_epsilon(1000, 0.95, 4), expected)

    def test_report_includes_quantile_precision_diagnostics(self):
        report = self.run_model(trials=250, quantile_precision_confidence=0.90)
        self.assertEqual(report["report_version"], "1.1")
        run_precision = report["run"]["quantile_precision"]
        self.assertTrue(run_precision["computed"])
        self.assertEqual(run_precision["familywise_confidence_level"], 0.90)
        self.assertEqual(run_precision["familywise_marginal_count"], 4)
        for field in (
            "total_flow_cfm",
            "per_fan_flow_cfm",
            "common_static_pressure_mmh2o",
            "ideal_bulk_air_temperature_rise_c",
        ):
            precision = report["outputs"][field]["monte_carlo_quantile_precision"]
            self.assertAlmostEqual(precision["familywise_confidence_level"], 0.90)
            for endpoint_name in ("lower_coverage_endpoint", "upper_coverage_endpoint"):
                endpoint = precision[endpoint_name]
                bounds = endpoint["confidence_bounds"]
                self.assertEqual(bounds["lower_unbounded"], bounds["lower"] is None)
                self.assertEqual(bounds["upper_unbounded"], bounds["upper"] is None)
                if bounds["lower"] is not None:
                    self.assertLessEqual(bounds["lower"], endpoint["type7_estimate"])
                if bounds["upper"] is not None:
                    self.assertLessEqual(endpoint["type7_estimate"], bounds["upper"])

    def test_invalid_quantile_precision_confidence_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "quantile_precision_confidence must be strictly between 0 and 1"):
            self.run_model(quantile_precision_confidence=1.0)

    def test_json_schema_file_is_present_and_parses(self):
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "curve-uncertainty-v1.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["schema_version"]["const"], "1.0")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_student_t_and_triangular_distributions_are_supported(self):
        fan = json.loads(self.fan_sidecar.read_text(encoding="utf-8"))
        next(s for s in fan["uncertainty_sources"] if s["id"] == "fan_p1")["distribution"] = {
            "family": "student_t",
            "parameters": {"location": 0.0, "scale": 0.004, "degrees_of_freedom": 5.0},
        }
        self.fan_sidecar.write_text(json.dumps(fan), encoding="utf-8")
        system = json.loads(self.system_sidecar.read_text(encoding="utf-8"))
        next(s for s in system["uncertainty_sources"] if s["id"] == "system_p2")["distribution"] = {
            "family": "triangular",
            "parameters": {"lower": -0.02, "mode": 0.0, "upper": 0.02},
        }
        self.system_sidecar.write_text(json.dumps(system), encoding="utf-8")
        report = self.run_model(trials=100)
        self.assertEqual(report["run"]["attempted_trials"], 100)
        self.assertGreater(report["run"]["valid_trials"], 0)

    def test_invalid_sampled_fan_curves_are_counted(self):
        fan = json.loads(self.fan_sidecar.read_text(encoding="utf-8"))
        next(s for s in fan["uncertainty_sources"] if s["id"] == "fan_p1")["distribution"] = normal(20.0)
        self.fan_sidecar.write_text(json.dumps(fan), encoding="utf-8")
        report = self.run_model(trials=500, seed=13, minimum_valid_fraction=0.99)
        self.assertGreater(report["run"]["failure_counts"]["invalid_fan_curve"], 0)
        self.assertEqual(report["run"]["attempted_trials"], 500)
        self.assertEqual(report["status"], "inconclusive")
        self.assertIsNone(report["outputs"])

    def test_invalid_sampled_system_curves_are_counted(self):
        system = json.loads(self.system_sidecar.read_text(encoding="utf-8"))
        next(s for s in system["uncertainty_sources"] if s["id"] == "system_p2")["distribution"] = normal(20.0)
        self.system_sidecar.write_text(json.dumps(system), encoding="utf-8")
        report = self.run_model(trials=500, seed=29)
        self.assertGreater(report["run"]["failure_counts"]["invalid_system_curve"], 0)
        self.assertEqual(report["run"]["attempted_trials"], 500)

    def test_short_system_curve_is_reported_without_extrapolation(self):
        self.system_path.write_text(
            "flow_cfm,static_pressure_mmh2o\n0,0\n20,0.2\n40,1\n", encoding="utf-8"
        )
        system = json.loads(self.system_sidecar.read_text(encoding="utf-8"))
        system["central_values"]["sha256"] = digest(self.system_path)
        system["uncertainty_sources"] = []
        system["coordinate_coverage"] = [
            {"row_index": 1, "flow_cfm": "fixed_by_definition", "static_pressure_mmh2o": "fixed_by_definition"},
            {"row_index": 2, "flow_cfm": "held_fixed_assumption", "static_pressure_mmh2o": "held_fixed_assumption",
             "held_fixed_reasons": {"flow_cfm": "SYNTHETIC fixed coordinate", "static_pressure_mmh2o": "SYNTHETIC fixed coordinate"}},
            {"row_index": 3, "flow_cfm": "held_fixed_assumption", "static_pressure_mmh2o": "held_fixed_assumption",
             "held_fixed_reasons": {"flow_cfm": "SYNTHETIC fixed coordinate", "static_pressure_mmh2o": "SYNTHETIC fixed coordinate"}},
        ]
        self.system_sidecar.write_text(json.dumps(system), encoding="utf-8")
        report = self.run_model(trials=20, allow_held_fixed=True)
        self.assertEqual(report["run"]["failure_counts"]["system_curve_range_too_short"], 20)
        self.assertEqual(report["status"], "inconclusive")
        self.assertIsNone(report["outputs"])

    def test_duplicate_json_object_keys_are_rejected(self):
        self.fan_sidecar.write_text(
            '{"schema_version":"1.0","schema_version":"1.0"}', encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "duplicate JSON object key"):
            self.run_model()

    def test_invalid_trial_effects_are_counted_not_retried(self):
        fan = json.loads(self.fan_sidecar.read_text(encoding="utf-8"))
        source_scale = next(s for s in fan["uncertainty_sources"] if s["id"] == "shared_flow_scale")
        source_scale["distribution"] = {"family": "uniform", "parameters": {"lower": -2.0, "upper": 2.0}}
        self.fan_sidecar.write_text(json.dumps(fan), encoding="utf-8")
        system = json.loads(self.system_sidecar.read_text(encoding="utf-8"))
        source_scale_sys = next(s for s in system["uncertainty_sources"] if s["id"] == "shared_flow_scale")
        source_scale_sys["distribution"] = copy.deepcopy(source_scale["distribution"])
        self.system_sidecar.write_text(json.dumps(system), encoding="utf-8")
        report = self.run_model(trials=100, seed=3)
        self.assertEqual(report["run"]["attempted_trials"], 100)
        self.assertGreater(report["run"]["failure_counts"]["invalid_source_effect"], 0)
        self.assertEqual(report["run"]["valid_trials"] + report["run"]["failed_trials"], 100)


    def _cli_args(self, output):
        return [
            "--fan-curve", str(self.fan_path),
            "--system-curve", str(self.system_path),
            "--fan-sidecar", str(self.fan_sidecar),
            "--system-sidecar", str(self.system_sidecar),
            "--repo-root", str(self.root),
            "--fan-count", "1",
            "--fan-model", CONDITION["fan_model"],
            "--configuration-id", CONDITION["configuration_id"],
            "--rpm", str(CONDITION["rpm"]),
            "--voltage-v", str(CONDITION["voltage_v"]),
            "--pwm-percent", str(CONDITION["pwm_percent"]),
            "--trials", "16",
            "--seed", "7",
            "--output", str(output),
        ]

    def test_cli_output_must_not_overwrite_an_input(self):
        for protected in (self.fan_path, self.system_path, self.fan_sidecar, self.system_sidecar):
            with self.subTest(protected=protected.name):
                original = protected.read_bytes()
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as raised:
                        uncertainty_main(self._cli_args(protected))
                self.assertEqual(raised.exception.code, 2)
                self.assertEqual(protected.read_bytes(), original)

    def test_cli_writes_report_to_new_output_file(self):
        output = self.root / "report.json"
        self.assertEqual(uncertainty_main(self._cli_args(output)), 0)
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["run"]["attempted_trials"], 16)


if __name__ == "__main__":
    unittest.main()
