#!/usr/bin/env python3
"""Monte Carlo propagation for tabulated fan/system operating-point curves.

This is an opt-in path. It deliberately leaves the deterministic solver and
its command-line interface unchanged. See schemas/curve-uncertainty-v1.schema.json
and docs/UNCERTAINTY_MODEL_SPEC.md for the sidecar contract and limitations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import statistics
import sys
from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path
from typing import Any, Iterable

from analysis.fan_operating_point import (
    FanCurve,
    SystemCurve,
    _validate_points,
    solve_operating_point,
)
from analysis.operating_point_sensitivity import _reject_output_input_collision

SCHEMA_VERSION = "1.0"
REPORT_VERSION = "1.1"
QUANTILE_METHOD = "Hyndman-Fan type 7 (linear interpolation)"
DKW_QUANTILE_PRECISION_METHOD = (
    "Dvoretzky-Kiefer-Wolfowitz (DKW) inequality with conservative order-statistic inversion"
)
OUTPUT_FIELDS = (
    "total_flow_cfm",
    "per_fan_flow_cfm",
    "common_static_pressure_mmh2o",
    "ideal_bulk_air_temperature_rise_c",
)
FAILURE_REASONS = (
    "invalid_source_effect",
    "invalid_fan_curve",
    "invalid_system_curve",
    "no_positive_flow_root",
    "system_curve_range_too_short",
    "unbracketed_operating_point",
    "fan_curve_range_failure",
    "system_curve_range_failure",
    "solver_failure",
)
_CLASSIFICATIONS = {
    "manufacturer_numeric_data",
    "calibrated_measurement",
    "approximate_manual_digitization",
    "estimate",
    "synthetic_test_fixture",
    "hypothetical_screening_input",
}
_DISTRIBUTIONS = {"normal", "student_t", "uniform", "triangular"}
_QUANTITIES = {"flow_cfm", "static_pressure_mmh2o"}
_STATES = {"sampled", "fixed_by_definition", "held_fixed_assumption"}


@dataclass(frozen=True)
class _Sidecar:
    path: Path
    raw: dict[str, Any]
    sha256: str
    curve_type: str
    sources: dict[str, dict[str, Any]]
    held_fixed: tuple[dict[str, Any], ...]


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _enum_string(value: Any, allowed: set[str], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"{label} has unsupported value {value!r}")
    return value


def _strict_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _keys(
    value: dict[str, Any],
    *,
    required: set[str],
    optional: set[str] = frozenset(),
    label: str,
) -> None:
    missing = required - value.keys()
    extra = value.keys() - required - optional
    if missing:
        raise ValueError(f"{label}: missing field(s): {', '.join(sorted(missing))}")
    if extra:
        raise ValueError(f"{label}: unsupported field(s): {', '.join(sorted(extra))}")


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be a finite number")
    return result


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_under_root(path_value: str | Path, root: Path) -> Path:
    path = Path(path_value)
    return (path if path.is_absolute() else root / path).resolve()


def _validate_measurement_basis(value: Any, label: str) -> dict[str, Any]:
    basis = _object(value, label)
    _keys(
        basis,
        required={
            "flow_basis",
            "flow_reference_conditions",
            "pressure_basis",
            "pressure_reference",
            "velocity_pressure_correction",
        },
        label=label,
    )
    _enum_string(
        basis["flow_basis"],
        {"actual_volumetric_flow", "standard_volumetric_flow"},
        f"{label}.flow_basis",
    )
    conditions = _object(basis["flow_reference_conditions"], f"{label}.flow_reference_conditions")
    _keys(
        conditions,
        required={"temperature_c", "absolute_pressure_kpa", "relative_humidity_percent"},
        label=f"{label}.flow_reference_conditions",
    )
    temperature = _finite_number(
        conditions["temperature_c"], f"{label}.flow_reference_conditions.temperature_c"
    )
    pressure = _finite_number(
        conditions["absolute_pressure_kpa"],
        f"{label}.flow_reference_conditions.absolute_pressure_kpa",
    )
    humidity = _finite_number(
        conditions["relative_humidity_percent"],
        f"{label}.flow_reference_conditions.relative_humidity_percent",
    )
    if temperature <= -273.15 or pressure <= 0 or not 0 <= humidity <= 100:
        raise ValueError(f"{label}.flow_reference_conditions contains invalid temperature, pressure, or humidity")
    if basis["pressure_basis"] != "static_pressure":
        raise ValueError(f"{label}.pressure_basis must be 'static_pressure' for v1")
    _nonempty_string(basis["pressure_reference"], f"{label}.pressure_reference")
    _nonempty_string(basis["velocity_pressure_correction"], f"{label}.velocity_pressure_correction")
    return basis


def _validate_operating_condition(value: Any, label: str) -> dict[str, Any]:
    condition = _object(value, label)
    _keys(
        condition,
        required={"configuration_id", "fan_model", "fan_count", "rpm", "voltage_v", "pwm_percent"},
        label=label,
    )
    _nonempty_string(condition["configuration_id"], f"{label}.configuration_id")
    _nonempty_string(condition["fan_model"], f"{label}.fan_model")
    count = condition["fan_count"]
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError(f"{label}.fan_count must be a positive integer")
    rpm = _finite_number(condition["rpm"], f"{label}.rpm")
    voltage = _finite_number(condition["voltage_v"], f"{label}.voltage_v")
    pwm = _finite_number(condition["pwm_percent"], f"{label}.pwm_percent")
    if rpm <= 0 or voltage <= 0 or not 0 <= pwm <= 100:
        raise ValueError(f"{label} has an invalid RPM, voltage, or PWM value")
    return condition


def _validate_distribution(source: dict[str, Any], label: str) -> None:
    distribution = _object(source.get("distribution"), f"{label}.distribution")
    _keys(distribution, required={"family", "parameters"}, label=f"{label}.distribution")
    family = _enum_string(distribution["family"], _DISTRIBUTIONS, f"{label}.distribution.family")
    params = _object(distribution["parameters"], f"{label}.distribution.parameters")
    expected = {
        "normal": {"mean", "standard_deviation"},
        "student_t": {"location", "scale", "degrees_of_freedom"},
        "uniform": {"lower", "upper"},
        "triangular": {"lower", "mode", "upper"},
    }[family]
    _keys(params, required=expected, label=f"{label}.distribution.parameters")
    numbers = {key: _finite_number(value, f"{label}.distribution.parameters.{key}") for key, value in params.items()}
    tolerance = 1e-12
    if family == "normal":
        if numbers["mean"] != 0 or numbers["standard_deviation"] <= 0:
            raise ValueError(f"{label}: normal correction requires mean=0 and standard_deviation>0")
    elif family == "student_t":
        if numbers["location"] != 0 or numbers["scale"] <= 0 or numbers["degrees_of_freedom"] <= 2:
            raise ValueError(f"{label}: Student-t correction requires location=0, scale>0, and df>2")
    elif family == "uniform":
        if numbers["lower"] >= numbers["upper"] or not math.isclose(
            numbers["lower"] + numbers["upper"], 0.0, abs_tol=tolerance, rel_tol=0.0
        ):
            raise ValueError(f"{label}: uniform correction must have lower<upper and zero mean")
    else:
        lower, mode, upper = numbers["lower"], numbers["mode"], numbers["upper"]
        if lower >= upper or not lower <= mode <= upper or not math.isclose(
            lower + mode + upper, 0.0, abs_tol=tolerance, rel_tol=0.0
        ):
            raise ValueError(f"{label}: triangular correction must be ordered and have zero mean")


def _draw_source(source: dict[str, Any], rng: random.Random) -> float:
    distribution = source["distribution"]
    family = distribution["family"]
    p = distribution["parameters"]
    if family == "normal":
        return rng.normalvariate(p["mean"], p["standard_deviation"])
    if family == "student_t":
        df = p["degrees_of_freedom"]
        chi_square = rng.gammavariate(df / 2.0, 2.0)
        if not math.isfinite(chi_square) or chi_square <= 0:
            return math.nan
        return p["location"] + p["scale"] * rng.gauss(0.0, 1.0) / math.sqrt(chi_square / df)
    if family == "uniform":
        return rng.uniform(p["lower"], p["upper"])
    return rng.triangular(p["lower"], p["upper"], p["mode"])


def _load_sidecar(
    sidecar_path: Path,
    *,
    expected_type: str,
    curve_path: Path,
    curve_points: tuple[tuple[float, float], ...],
    repo_root: Path,
) -> _Sidecar:
    try:
        raw_bytes = sidecar_path.read_bytes()
        raw = json.loads(raw_bytes, object_pairs_hook=_strict_object_pairs)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read valid JSON sidecar {sidecar_path}: {exc}") from exc
    data = _object(raw, str(sidecar_path))
    _keys(
        data,
        required={
            "schema_version",
            "curve_type",
            "central_values",
            "provenance",
            "measurement_basis",
            "operating_condition",
            "distinct_source_ids_independent",
            "known_dependencies",
            "coordinate_coverage",
            "uncertainty_sources",
        },
        label=str(sidecar_path),
    )
    if data["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"{sidecar_path}: unsupported schema_version {data['schema_version']!r}")
    if data["curve_type"] != expected_type:
        raise ValueError(f"{sidecar_path}: expected curve_type {expected_type!r}")
    central = _object(data["central_values"], f"{sidecar_path}.central_values")
    _keys(central, required={"path", "sha256"}, label=f"{sidecar_path}.central_values")
    central_value_name = _nonempty_string(central["path"], "central_values.path")
    if Path(central_value_name).is_absolute():
        raise ValueError(f"{sidecar_path}: central_values.path must be repository-relative")
    central_path = _resolve_under_root(central_value_name, repo_root)
    if not central_path.is_relative_to(repo_root):
        raise ValueError(f"{sidecar_path}: central_values.path must remain inside the repository root")
    if central_path != curve_path:
        raise ValueError(f"{sidecar_path}: central_values.path does not identify the supplied curve file")
    expected_hash = _nonempty_string(central["sha256"], "central_values.sha256")
    if len(expected_hash) != 64 or any(ch not in "0123456789abcdef" for ch in expected_hash):
        raise ValueError(f"{sidecar_path}: central_values.sha256 must be lowercase SHA-256 hex")
    actual_hash = _sha256(curve_path)
    if actual_hash != expected_hash:
        raise ValueError(f"{sidecar_path}: central-value CSV SHA-256 mismatch")

    provenance = _object(data["provenance"], f"{sidecar_path}.provenance")
    _keys(provenance, required={"classification", "description", "source_record"}, label=f"{sidecar_path}.provenance")
    _enum_string(provenance["classification"], _CLASSIFICATIONS, f"{sidecar_path}.provenance.classification")
    _nonempty_string(provenance["description"], f"{sidecar_path}.provenance.description")
    _nonempty_string(provenance["source_record"], f"{sidecar_path}.provenance.source_record")
    _validate_measurement_basis(data["measurement_basis"], f"{sidecar_path}.measurement_basis")
    _validate_operating_condition(data["operating_condition"], f"{sidecar_path}.operating_condition")

    if data["distinct_source_ids_independent"] is not True:
        raise ValueError(f"{sidecar_path}: v1 requires an explicit distinct_source_ids_independent=true declaration")
    if not isinstance(data["known_dependencies"], list):
        raise ValueError(f"{sidecar_path}.known_dependencies must be an array")
    if data["known_dependencies"]:
        raise ValueError(f"{sidecar_path}: known cross-source dependencies are unsupported by v1")

    coverage = data["coordinate_coverage"]
    if not isinstance(coverage, list) or len(coverage) != len(curve_points):
        raise ValueError(f"{sidecar_path}: coordinate_coverage must contain exactly one entry per CSV data row")
    coverage_by_row: dict[int, dict[str, str]] = {}
    held_fixed: list[dict[str, Any]] = []
    for expected_row, entry_value in enumerate(coverage, start=1):
        entry = _object(entry_value, f"{sidecar_path}.coordinate_coverage[{expected_row}]")
        _keys(
            entry,
            required={"row_index", "flow_cfm", "static_pressure_mmh2o"},
            optional={"held_fixed_reasons"},
            label=f"{sidecar_path}.coordinate_coverage[{expected_row}]",
        )
        row_index = entry["row_index"]
        if isinstance(row_index, bool) or not isinstance(row_index, int) or row_index != expected_row:
            raise ValueError(f"{sidecar_path}: coordinate_coverage row_index values must be consecutive and one-based")
        states: dict[str, str] = {}
        for quantity in ("flow_cfm", "static_pressure_mmh2o"):
            state = _enum_string(entry[quantity], _STATES, f"{sidecar_path}: row {expected_row} {quantity} coverage state")
            anchor = (expected_type == "fan" and (
                (expected_row == 1 and quantity == "flow_cfm")
                or (expected_row == len(curve_points) and quantity == "static_pressure_mmh2o")
            )) or (expected_type == "system" and expected_row == 1)
            if anchor and state != "fixed_by_definition":
                raise ValueError(f"{sidecar_path}: row {expected_row} {quantity} must be fixed_by_definition")
            if not anchor and state == "fixed_by_definition":
                raise ValueError(f"{sidecar_path}: row {expected_row} {quantity} is not a defined model anchor")
            states[quantity] = state
            if state == "held_fixed_assumption":
                reasons = entry.get("held_fixed_reasons")
                if not isinstance(reasons, dict) or quantity not in reasons:
                    raise ValueError(f"{sidecar_path}: held-fixed row {expected_row} {quantity} needs a reason")
                held_fixed.append({
                    "curve_type": expected_type,
                    "row_index": expected_row,
                    "quantity": quantity,
                    "reason": _nonempty_string(reasons[quantity], "held_fixed_reasons reason"),
                })
        reasons_obj = entry.get("held_fixed_reasons", {})
        if not isinstance(reasons_obj, dict):
            raise ValueError(f"{sidecar_path}: held_fixed_reasons must be an object")
        held_quantities = {q for q, state in states.items() if state == "held_fixed_assumption"}
        if set(reasons_obj) != held_quantities:
            raise ValueError(f"{sidecar_path}: held_fixed_reasons must match held-fixed coordinates exactly")
        coverage_by_row[expected_row] = states

    sources_value = data["uncertainty_sources"]
    if not isinstance(sources_value, list):
        raise ValueError(f"{sidecar_path}.uncertainty_sources must be an array")
    sources: dict[str, dict[str, Any]] = {}
    targeted: set[tuple[int, str]] = set()
    for source_index, source_value in enumerate(sources_value, start=1):
        label = f"{sidecar_path}.uncertainty_sources[{source_index}]"
        source = _object(source_value, label)
        _keys(
            source,
            required={
                "id", "evaluation_method", "source_record", "original_statement",
                "conversion_notes", "units", "distribution", "targets",
            },
            label=label,
        )
        source_id = _nonempty_string(source["id"], f"{label}.id")
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]*", source_id) is None:
            raise ValueError(f"{label}.id must be a stable identifier using letters, digits, '.', '_', ':', or '-'")
        if source_id in sources:
            raise ValueError(f"{sidecar_path}: duplicate uncertainty source id {source_id!r}")
        _enum_string(source["evaluation_method"], {"type_a", "type_b", "other"}, f"{label}.evaluation_method")
        _nonempty_string(source["source_record"], f"{label}.source_record")
        _nonempty_string(source["original_statement"], f"{label}.original_statement")
        _nonempty_string(source["conversion_notes"], f"{label}.conversion_notes")
        units = _nonempty_string(source["units"], f"{label}.units")
        _validate_distribution(source, label)
        targets_value = source["targets"]
        if not isinstance(targets_value, list) or not targets_value:
            raise ValueError(f"{label}.targets must be a non-empty array")
        expanded_targets: list[dict[str, Any]] = []
        source_target_keys: set[tuple[int, str]] = set()
        for target_index, target_value in enumerate(targets_value, start=1):
            target_label = f"{label}.targets[{target_index}]"
            target = _object(target_value, target_label)
            _keys(target, required={"rows", "quantity", "effect", "coefficient"}, label=target_label)
            _enum_string(target["quantity"], _QUANTITIES, f"{target_label}.quantity")
            _enum_string(target["effect"], {"additive", "relative_scale"}, f"{target_label}.effect")
            coefficient = _finite_number(target["coefficient"], f"{target_label}.coefficient")
            if coefficient == 0:
                raise ValueError(f"{target_label}.coefficient must be non-zero")
            rows_value = target["rows"]
            if rows_value == "all":
                rows = list(range(1, len(curve_points) + 1))
            elif isinstance(rows_value, list) and rows_value and all(
                isinstance(row, int) and not isinstance(row, bool) and 1 <= row <= len(curve_points)
                for row in rows_value
            ) and len(set(rows_value)) == len(rows_value):
                rows = rows_value
            else:
                raise ValueError(f"{target_label}.rows must be 'all' or unique one-based data-row indices")
            expected_units = "dimensionless" if target["effect"] == "relative_scale" else (
                "CFM" if target["quantity"] == "flow_cfm" else "mmH2O"
            )
            if units != expected_units:
                raise ValueError(f"{label}: {target['effect']} source units must be {expected_units!r}")
            for row in rows:
                key = (row, target["quantity"])
                if key in source_target_keys:
                    raise ValueError(f"{label}: duplicate target for row {row} {target['quantity']}")
                source_target_keys.add(key)
                if coverage_by_row[row][target["quantity"]] != "sampled":
                    raise ValueError(f"{label}: target row {row} {target['quantity']} is not marked sampled")
                targeted.add(key)
                expanded_targets.append({
                    "curve_type": expected_type,
                    "row_index": row,
                    "quantity": target["quantity"],
                    "effect": target["effect"],
                    "coefficient": coefficient,
                })
        source_copy = dict(source)
        source_copy["targets"] = expanded_targets
        sources[source_id] = source_copy

    for row, states in coverage_by_row.items():
        for quantity, state in states.items():
            if state == "sampled" and (row, quantity) not in targeted:
                raise ValueError(f"{sidecar_path}: sampled coordinate row {row} {quantity} has no uncertainty source")
    return _Sidecar(
        path=sidecar_path,
        raw=data,
        sha256=hashlib.sha256(raw_bytes).hexdigest(),
        curve_type=expected_type,
        sources=sources,
        held_fixed=tuple(held_fixed),
    )


def _merge_sources(sidecars: Iterable[_Sidecar]) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for sidecar in sidecars:
        for source_id, source in sidecar.sources.items():
            definition = {
            key: source[key]
            for key in (
                "evaluation_method", "source_record", "original_statement",
                "conversion_notes", "units", "distribution",
            )
        }
            if source_id not in merged:
                merged[source_id] = {**definition, "id": source_id, "targets": list(source["targets"])}
                continue
            existing = {key: merged[source_id][key] for key in definition}
            if existing != definition:
                raise ValueError(f"source id {source_id!r} has conflicting definitions across sidecars")
            merged[source_id]["targets"].extend(source["targets"])
    return merged


def _apply_draws(
    fan_points: tuple[tuple[float, float], ...],
    system_points: tuple[tuple[float, float], ...],
    sources: dict[str, dict[str, Any]],
    rng: random.Random,
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]] | str:
    point_sets = {"fan": fan_points, "system": system_points}
    scale: dict[tuple[str, int, str], float] = {}
    additive: dict[tuple[str, int, str], float] = {}
    # Draw every distinct source exactly once for every attempted trial before
    # applying effects. An invalid draw must not skip later sources and thereby
    # alter the RNG stream or violate the fixed-trial sampling contract.
    draws: dict[str, float] = {}
    invalid_draw = False
    for source_id in sorted(sources):
        try:
            draws[source_id] = _draw_source(sources[source_id], rng)
        except (OverflowError, ValueError, ZeroDivisionError):
            draws[source_id] = math.nan
        if not math.isfinite(draws[source_id]):
            invalid_draw = True
    if invalid_draw:
        return "invalid_source_effect"

    for source_id in sorted(sources):
        source = sources[source_id]
        draw = draws[source_id]
        for target in source["targets"]:
            quantity = target["quantity"]
            coefficient = target["coefficient"]
            factor_key = (target["curve_type"], target["row_index"], quantity)
            contribution = coefficient * draw
            if not math.isfinite(contribution):
                return "invalid_source_effect"
            if target["effect"] == "relative_scale":
                factor = 1.0 + contribution
                if not math.isfinite(factor) or factor <= 0:
                    return "invalid_source_effect"
                scale[factor_key] = scale.get(factor_key, 1.0) * factor
                if not math.isfinite(scale[factor_key]) or scale[factor_key] <= 0:
                    return "invalid_source_effect"
            else:
                additive[factor_key] = additive.get(factor_key, 0.0) + contribution
    sampled: dict[str, list[tuple[float, float]]] = {}
    for curve_type, points in point_sets.items():
        result: list[tuple[float, float]] = []
        for row_index, (flow, pressure) in enumerate(points, start=1):
            coordinates = {}
            for quantity, base_value in (("flow_cfm", flow), ("static_pressure_mmh2o", pressure)):
                key = (curve_type, row_index, quantity)
                value = base_value * scale.get(key, 1.0) + additive.get(key, 0.0)
                if not math.isfinite(value):
                    return "invalid_source_effect"
                coordinates[quantity] = value
            result.append((coordinates["flow_cfm"], coordinates["static_pressure_mmh2o"]))
        sampled[curve_type] = result
    return sampled["fan"], sampled["system"]


def quantile_type7(values: Iterable[float], probability: float) -> float:
    """Hyndman-Fan type 7 sample quantile (linear interpolation)."""
    data = sorted(values)
    if not data:
        raise ValueError("quantile requires at least one value")
    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("quantile probability must be between 0 and 1")
    if len(data) == 1:
        return data[0]
    h = (len(data) - 1) * probability
    lower = math.floor(h)
    upper = math.ceil(h)
    if lower == upper:
        return data[lower]
    fraction = h - lower
    return data[lower] + fraction * (data[upper] - data[lower])


def _dkw_epsilon(
    sample_count: int,
    confidence_level: float,
    familywise_marginal_count: int,
) -> float:
    """Return a Bonferroni-adjusted DKW half-width across marginal outputs."""
    if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count < 1:
        raise ValueError("sample_count must be a positive integer")
    if not math.isfinite(confidence_level) or not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be strictly between 0 and 1")
    if (
        isinstance(familywise_marginal_count, bool)
        or not isinstance(familywise_marginal_count, int)
        or familywise_marginal_count < 1
    ):
        raise ValueError("familywise_marginal_count must be a positive integer")
    alpha = 1.0 - confidence_level
    epsilon = math.sqrt(math.log(2.0 * familywise_marginal_count / alpha) / (2.0 * sample_count))
    return min(1.0, epsilon)


def _dkw_quantile_precision(
    values: list[float],
    probability: float,
    epsilon: float,
) -> dict[str, Any]:
    """Invert a DKW CDF band into conservative order-statistic quantile bounds.

    For p-epsilon > 0, the lower bound is order statistic
    floor(n * (p-epsilon)), using the first order statistic when that rank
    would be zero. For p+epsilon < 1, the upper bound is order statistic
    floor(n * (p+epsilon)) + 1. These are the left/right empirical inverse
    conventions; they deliberately avoid interpolated values.

    If p-epsilon <= 0 or p+epsilon >= 1, the corresponding confidence limit
    is unbounded on the real line and is represented by JSON null.
    Decimal arithmetic on the shortest round-trip float strings prevents
    binary floating-point artifacts from changing an exact order-statistic
    boundary by one rank.
    """
    ordered = sorted(values)
    if not ordered:
        raise ValueError("quantile precision requires at least one value")
    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("quantile probability must be between 0 and 1")
    if not math.isfinite(epsilon) or not 0 <= epsilon <= 1:
        raise ValueError("DKW epsilon must be between 0 and 1")

    count = len(ordered)
    probability_decimal = Decimal(str(probability))
    epsilon_decimal = Decimal(str(epsilon))
    lower_probability_decimal = probability_decimal - epsilon_decimal
    upper_probability_decimal = probability_decimal + epsilon_decimal
    lower_probability_used = float(max(Decimal(0), lower_probability_decimal))
    upper_probability_used = float(min(Decimal(1), upper_probability_decimal))

    if lower_probability_decimal <= 0:
        lower_rank = None
    else:
        lower_rank = max(
            1,
            int((Decimal(count) * lower_probability_decimal).to_integral_value(rounding=ROUND_FLOOR)),
        )

    if upper_probability_decimal >= 1:
        upper_rank = None
    else:
        upper_rank = (
            int((Decimal(count) * upper_probability_decimal).to_integral_value(rounding=ROUND_FLOOR))
            + 1
        )

    return {
        "probability": probability,
        "type7_estimate": quantile_type7(ordered, probability),
        "confidence_bounds": {
            "lower": ordered[lower_rank - 1] if lower_rank is not None else None,
            "upper": ordered[upper_rank - 1] if upper_rank is not None else None,
            "lower_unbounded": lower_rank is None,
            "upper_unbounded": upper_rank is None,
            "lower_probability_used": lower_probability_used,
            "upper_probability_used": upper_probability_used,
            "lower_order_statistic_rank_1_based": lower_rank,
            "upper_order_statistic_rank_1_based": upper_rank,
        },
    }


def _summarize(
    values: list[float],
    coverage_probability: float,
    quantile_precision_confidence: float,
    familywise_marginal_count: int,
) -> dict[str, Any]:
    tail = (1.0 - coverage_probability) / 2.0
    epsilon = _dkw_epsilon(
        len(values), quantile_precision_confidence, familywise_marginal_count
    )
    return {
        "sample_count": len(values),
        "mean": statistics.fmean(values),
        "standard_uncertainty": statistics.stdev(values) if len(values) >= 2 else None,
        "median": quantile_type7(values, 0.5),
        "minimum": min(values),
        "maximum": max(values),
        "central_empirical_coverage_interval": {
            "probability": coverage_probability,
            "lower": quantile_type7(values, tail),
            "upper": quantile_type7(values, 1.0 - tail),
            "quantile_method": QUANTILE_METHOD,
            "interpretation": "marginal interval conditional on the declared input model and accepted trial population",
        },
        "monte_carlo_quantile_precision": {
            "method": DKW_QUANTILE_PRECISION_METHOD,
            "familywise_confidence_level": quantile_precision_confidence,
            "familywise_marginal_count": familywise_marginal_count,
            "dkw_epsilon": epsilon,
            "lower_coverage_endpoint": _dkw_quantile_precision(values, tail, epsilon),
            "upper_coverage_endpoint": _dkw_quantile_precision(values, 1.0 - tail, epsilon),
            "interpretation": (
                "Confidence bounds for the population quantile locations due only to finite Monte Carlo "
                "sample size; they are not predictive coverage intervals or measurement-uncertainty bounds."
            ),
        },
    }


def _joint_moments(vectors: list[tuple[float, ...]]) -> tuple[list[list[float]] | None, list[list[float | None]] | None]:
    if len(vectors) < 2:
        return None, None
    width = len(vectors[0])
    means = [statistics.fmean(row[i] for row in vectors) for i in range(width)]
    sums = [[0.0 for _ in range(width)] for _ in range(width)]
    for row in vectors:
        for i in range(width):
            for j in range(width):
                sums[i][j] += (row[i] - means[i]) * (row[j] - means[j])
    covariance = [[sums[i][j] / (len(vectors) - 1) for j in range(width)] for i in range(width)]
    standard = [math.sqrt(max(0.0, covariance[i][i])) for i in range(width)]
    correlation: list[list[float | None]] = []
    for i in range(width):
        row: list[float | None] = []
        for j in range(width):
            denominator = standard[i] * standard[j]
            row.append(covariance[i][j] / denominator if denominator > 0 else None)
        correlation.append(row)
    return covariance, correlation


def _failure_reason(exc: Exception) -> str:
    message = str(exc).lower()
    if "no positive-flow operating point" in message or "zero flow" in message:
        return "no_positive_flow_root"
    if "no intersection within supplied system-curve range" in message:
        return "system_curve_range_too_short"
    if "could not bracket" in message:
        return "unbracketed_operating_point"
    if "outside the supplied fan curve" in message:
        return "fan_curve_range_failure"
    if "outside the supplied system curve" in message:
        return "system_curve_range_failure"
    return "solver_failure"


def run_uncertainty(
    *,
    fan_curve_path: str | Path,
    system_curve_path: str | Path,
    fan_sidecar_path: str | Path,
    system_sidecar_path: str | Path,
    repo_root: str | Path = ".",
    fan_count: int,
    fan_model: str,
    configuration_id: str,
    rpm: float,
    voltage_v: float,
    pwm_percent: float,
    trials: int,
    seed: int,
    heat_load_w: float = 300.0,
    air_density_kg_m3: float = 1.204,
    air_specific_heat_j_kg_k: float = 1006.0,
    coverage_probability: float = 0.95,
    quantile_precision_confidence: float = 0.95,
    minimum_valid_fraction: float | None = None,
    allow_held_fixed: bool = False,
) -> dict[str, Any]:
    """Propagate uncertainty through the existing tabulated-curve solver."""
    if isinstance(trials, bool) or not isinstance(trials, int) or trials < 1:
        raise ValueError("trials must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    coverage_probability = _finite_number(coverage_probability, "coverage_probability")
    if not 0 < coverage_probability < 1:
        raise ValueError("coverage_probability must be strictly between 0 and 1")
    quantile_precision_confidence = _finite_number(
        quantile_precision_confidence, "quantile_precision_confidence"
    )
    if not 0 < quantile_precision_confidence < 1:
        raise ValueError("quantile_precision_confidence must be strictly between 0 and 1")
    if minimum_valid_fraction is not None:
        minimum_valid_fraction = _finite_number(minimum_valid_fraction, "minimum_valid_fraction")
        if not 0 <= minimum_valid_fraction <= 1:
            raise ValueError("minimum_valid_fraction must be between 0 and 1")
    if isinstance(fan_count, bool) or not isinstance(fan_count, int) or fan_count < 1:
        raise ValueError("fan_count must be a positive integer")

    root = Path(repo_root).resolve()
    fan_path = _resolve_under_root(fan_curve_path, root)
    system_path = _resolve_under_root(system_curve_path, root)
    fan_meta_path = _resolve_under_root(fan_sidecar_path, root)
    system_meta_path = _resolve_under_root(system_sidecar_path, root)
    fan_curve = FanCurve.from_csv(fan_path)
    system_curve = SystemCurve.from_csv(system_path)
    fan_meta = _load_sidecar(
        fan_meta_path,
        expected_type="fan",
        curve_path=fan_path,
        curve_points=fan_curve.points,
        repo_root=root,
    )
    system_meta = _load_sidecar(
        system_meta_path,
        expected_type="system",
        curve_path=system_path,
        curve_points=system_curve.points,
        repo_root=root,
    )
    if fan_meta.raw["measurement_basis"] != system_meta.raw["measurement_basis"]:
        raise ValueError("fan and system measurement bases are incompatible")
    if fan_meta.raw["operating_condition"] != system_meta.raw["operating_condition"]:
        raise ValueError("fan and system operating-condition metadata do not match")
    condition = fan_meta.raw["operating_condition"]
    expected_run_values = {
        "fan_count": fan_count,
        "fan_model": fan_model,
        "configuration_id": configuration_id,
        "rpm": rpm,
        "voltage_v": voltage_v,
        "pwm_percent": pwm_percent,
    }
    for field, value in expected_run_values.items():
        if condition[field] != value:
            raise ValueError(f"run input {field}={value!r} does not match sidecar value {condition[field]!r}")
    if not isinstance(fan_count, int) or isinstance(fan_count, bool) or fan_count < 1:
        raise ValueError("fan_count must be a positive integer")
    if not all(math.isfinite(float(v)) for v in (rpm, voltage_v, pwm_percent)):
        raise ValueError("fan operating-condition inputs must be finite")
    for name, value in (
        ("rpm", rpm), ("voltage_v", voltage_v), ("pwm_percent", pwm_percent),
        ("heat_load_w", heat_load_w), ("air_density_kg_m3", air_density_kg_m3),
        ("air_specific_heat_j_kg_k", air_specific_heat_j_kg_k),
    ):
        _finite_number(value, name)
    if heat_load_w < 0:
        raise ValueError("heat_load_w must be non-negative")
    if air_density_kg_m3 <= 0:
        raise ValueError("air_density_kg_m3 must be positive")
    if air_specific_heat_j_kg_k <= 0:
        raise ValueError("air_specific_heat_j_kg_k must be positive")

    held_fixed = list(fan_meta.held_fixed + system_meta.held_fixed)
    if held_fixed and not allow_held_fixed:
        raise ValueError(
            "one or more coordinates are held_fixed_assumption; pass allow_held_fixed=True "
            "to explicitly run with those uncertainty components omitted"
        )
    sources = _merge_sources((fan_meta, system_meta))
    rng = random.Random(seed)
    failures = {reason: 0 for reason in FAILURE_REASONS}
    output_vectors: list[tuple[float, float, float, float]] = []
    attempted = 0
    for _ in range(trials):
        attempted += 1
        draw_result = _apply_draws(fan_curve.points, system_curve.points, sources, rng)
        if isinstance(draw_result, str):
            failures[draw_result] += 1
            continue
        sampled_fan, sampled_system = draw_result
        try:
            checked_fan = _validate_points(
                sampled_fan,
                label="sampled fan curve",
                pressure_direction="decreasing",
            )
        except ValueError:
            failures["invalid_fan_curve"] += 1
            continue
        try:
            checked_system = _validate_points(
                sampled_system,
                label="sampled system curve",
                pressure_direction="increasing",
            )
        except ValueError:
            failures["invalid_system_curve"] += 1
            continue
        try:
            result = solve_operating_point(
                curve=FanCurve(checked_fan, source=f"{fan_path} [sampled]"),
                fan_count=fan_count,
                system_curve=SystemCurve(checked_system, source=f"{system_path} [sampled]"),
                heat_load_w=heat_load_w,
                air_density_kg_m3=air_density_kg_m3,
                air_specific_heat_j_kg_k=air_specific_heat_j_kg_k,
            )
        except (ValueError, RuntimeError) as exc:
            failures[_failure_reason(exc)] += 1
            continue
        output_vector = (
            result.total_flow_cfm,
            result.per_fan_flow_cfm,
            result.fan_static_pressure_mmh2o,
            result.ideal_bulk_air_temperature_rise_c,
        )
        if not all(math.isfinite(value) for value in output_vector):
            failures["solver_failure"] += 1
            continue
        output_vectors.append(output_vector)

    valid = len(output_vectors)
    failed = attempted - valid
    valid_fraction = valid / attempted
    sufficient_valid_samples = valid >= 2
    yield_check = None if minimum_valid_fraction is None else valid_fraction >= minimum_valid_fraction
    if not sufficient_valid_samples or yield_check is False:
        status = "inconclusive"
    elif held_fixed:
        status = "conditional_result_with_omitted_uncertainty"
    else:
        status = "conditional_result"

    outputs = None
    covariance = correlation = None
    if sufficient_valid_samples and yield_check is not False:
        columns = list(zip(*output_vectors))
        outputs = {
            field: _summarize(
                list(values), coverage_probability, quantile_precision_confidence, len(OUTPUT_FIELDS)
            )
            for field, values in zip(OUTPUT_FIELDS, columns)
        }
        covariance, correlation = _joint_moments(output_vectors)

    source_report = []
    for source_id in sorted(sources):
        source = sources[source_id]
        source_report.append({
            "id": source_id,
            "evaluation_method": source["evaluation_method"],
            "source_record": source["source_record"],
            "original_statement": source["original_statement"],
            "conversion_notes": source["conversion_notes"],
            "units": source["units"],
            "distribution": source["distribution"],
            "targets": source["targets"],
            "target_count": len(source["targets"]),
        })

    return {
        "report_version": REPORT_VERSION,
        "uncertainty_sidecar_schema_version": SCHEMA_VERSION,
        "model": "identical parallel fans + tabulated system curve",
        "status": status,
        "interpretation": (
            "Output distribution conditional on the declared input PDFs and independence model, "
            "physically valid sampled curves, and an in-range operating-point root."
        ),
        "run": {
            "attempted_trials": attempted,
            "valid_trials": valid,
            "failed_trials": failed,
            "valid_fraction": valid_fraction,
            "failure_counts": failures,
            "outcome_counts": {**failures, "valid_root": valid},
            "seed": seed,
            "random_number_generator": "Python random.Random (MT19937)",
            "python_version": sys.version,
            "coverage_probability": coverage_probability,
            "quantile_method": QUANTILE_METHOD,
            "quantile_precision": {
                "method": DKW_QUANTILE_PRECISION_METHOD,
                "familywise_confidence_level": quantile_precision_confidence,
                "familywise_marginal_count": len(OUTPUT_FIELDS),
                "dkw_epsilon": (
                    _dkw_epsilon(valid, quantile_precision_confidence, len(OUTPUT_FIELDS))
                    if outputs is not None else None
                ),
                "computed": outputs is not None,
                "sample_population": "valid-root output vectors only, conditional on acceptance",
                "familywise_scope": (
                    "all four marginal output distributions; each marginal DKW band covers all "
                    "quantile probabilities, with a Bonferroni union bound across marginals"
                ),
            },
            "minimum_valid_fraction": minimum_valid_fraction,
            "minimum_valid_fraction_met": yield_check,
            "sufficient_valid_samples_for_sample_covariance": sufficient_valid_samples,
        },
        "inputs": {
            "fan_curve": {"path": str(fan_path), "sha256": _sha256(fan_path)},
            "system_curve": {"path": str(system_path), "sha256": _sha256(system_path)},
            "fan_sidecar": {"path": str(fan_meta_path), "sha256": fan_meta.sha256},
            "system_sidecar": {"path": str(system_meta_path), "sha256": system_meta.sha256},
            "measurement_basis": fan_meta.raw["measurement_basis"],
            "operating_condition": condition,
            "fan_curve_provenance": fan_meta.raw["provenance"],
            "system_curve_provenance": system_meta.raw["provenance"],
            "distinct_source_ids_independent": True,
            "known_dependencies": [],
            "fixed_thermal_inputs": {
                "heat_load_w": heat_load_w,
                "air_density_kg_m3": air_density_kg_m3,
                "air_specific_heat_j_kg_k": air_specific_heat_j_kg_k,
            },
            "omitted_uncertainty": held_fixed,
            "uncertainty_sources": source_report,
            "solver_source_sha256": _sha256(Path(__file__).with_name("fan_operating_point.py")),
            "uncertainty_engine_source_sha256": _sha256(Path(__file__)),
        },
        "outputs": outputs,
        "joint_output_covariance": {
            "variable_order": list(OUTPUT_FIELDS),
            "variable_units": ["CFM", "CFM", "mmH2O", "degC"],
            "matrix": covariance,
            "interpretation": "sample covariance from the same valid joint trial vectors",
        },
        "joint_output_correlation": {
            "variable_order": list(OUTPUT_FIELDS),
            "variable_units": ["dimensionless", "dimensionless", "dimensionless", "dimensionless"],
            "matrix": correlation,
            "interpretation": "sample correlation; null where an output has zero sample standard deviation or fewer than two valid trials",
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Propagate curve-coordinate uncertainty through the tabulated fan/system solver."
    )
    parser.add_argument("--fan-curve", required=True)
    parser.add_argument("--system-curve", required=True, help="tabulated system curve; quadratic model is not supported")
    parser.add_argument("--fan-sidecar", required=True)
    parser.add_argument("--system-sidecar", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--fan-count", required=True, type=int)
    parser.add_argument("--fan-model", required=True)
    parser.add_argument("--configuration-id", required=True)
    parser.add_argument("--rpm", required=True, type=float)
    parser.add_argument("--voltage-v", required=True, type=float)
    parser.add_argument("--pwm-percent", required=True, type=float)
    parser.add_argument("--trials", required=True, type=int, help="number of attempted trials, including failures")
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--heat-load-w", type=float, default=300.0)
    parser.add_argument("--air-density-kg-m3", type=float, default=1.204)
    parser.add_argument("--air-cp-j-kg-k", type=float, default=1006.0)
    parser.add_argument("--coverage-probability", type=float, default=0.95)
    parser.add_argument(
        "--quantile-precision-confidence", type=float, default=0.95,
        help="familywise Monte Carlo quantile-precision confidence across reported outputs",
    )
    parser.add_argument("--minimum-valid-fraction", type=float)
    parser.add_argument("--allow-held-fixed", action="store_true", help="explicitly allow incomplete uncertainty coverage")
    parser.add_argument("--output", help="write JSON report to this path instead of stdout")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = run_uncertainty(
            fan_curve_path=args.fan_curve,
            system_curve_path=args.system_curve,
            fan_sidecar_path=args.fan_sidecar,
            system_sidecar_path=args.system_sidecar,
            repo_root=args.repo_root,
            fan_count=args.fan_count,
            fan_model=args.fan_model,
            configuration_id=args.configuration_id,
            rpm=args.rpm,
            voltage_v=args.voltage_v,
            pwm_percent=args.pwm_percent,
            trials=args.trials,
            seed=args.seed,
            heat_load_w=args.heat_load_w,
            air_density_kg_m3=args.air_density_kg_m3,
            air_specific_heat_j_kg_k=args.air_cp_j_kg_k,
            coverage_probability=args.coverage_probability,
            quantile_precision_confidence=args.quantile_precision_confidence,
            minimum_valid_fraction=args.minimum_valid_fraction,
            allow_held_fixed=args.allow_held_fixed,
        )
        rendered = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.output:
            inputs = report["inputs"]
            _reject_output_input_collision(
                args.output,
                [
                    Path(inputs[key]["path"])
                    for key in ("fan_curve", "system_curve", "fan_sidecar", "system_sidecar")
                ]
                + [Path(__file__), Path(__file__).with_name("fan_operating_point.py")],
            )
            Path(args.output).write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
