#!/usr/bin/env python3
"""Deterministic fan-count, RPM, and system-resistance scenario sweeps.

This is a separate opt-in analysis path. It calls the existing deterministic
operating-point solver and does not modify its API or command-line interface.
RPM affinity-law scaling is deliberately opt-in and is reported as a model
assumption, not as a measured multi-speed fan curve.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from itertools import product
from pathlib import Path
from typing import Any, Iterable

from analysis.fan_operating_point import (
    FanCurve,
    SystemCurve,
    _validate_points,
    classify_solver_failure,
    solve_operating_point,
)

REPORT_VERSION = "1.0"
RPM_SCALING_MODES = {"none", "affinity-law"}
OUTPUT_FIELDS = (
    "total_flow_cfm",
    "per_fan_flow_cfm",
    "fan_static_pressure_mmh2o",
    "system_pressure_drop_mmh2o",
    "ideal_bulk_air_temperature_rise_c",
)


def _finite_number(value: Any, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be a finite number")
    if positive and result <= 0:
        raise ValueError(f"{label} must be greater than zero")
    return result


def _resolve_under_root(path_value: str | Path, root: Path) -> Path:
    path = Path(path_value)
    resolved = (path if path.is_absolute() else root / path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"path {path_value!s} must resolve inside repository root {root}")
    return resolved


def _reject_output_input_collision(
    output_path: str | Path,
    input_paths: Iterable[str | Path],
) -> None:
    """Prevent a report from overwriting a file used to produce it."""
    output = Path(output_path)
    resolved_output = output.resolve()

    for input_value in input_paths:
        source = Path(input_value)
        same_file = resolved_output == source.resolve()

        if not same_file and output.exists() and source.exists():
            same_file = output.samefile(source)

        if same_file:
            raise ValueError(
                f"--output must not overwrite an analysis input: {source}"
            )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unique_positive_floats(values: Iterable[float], label: str) -> tuple[float, ...]:
    result = tuple(_finite_number(value, f"{label} entry", positive=True) for value in values)
    if not result:
        raise ValueError(f"{label} must contain at least one value")
    if len(set(result)) != len(result):
        raise ValueError(f"{label} must not contain duplicates")
    return result


def _positive_fan_counts(values: Iterable[int]) -> tuple[int, ...]:
    result: list[int] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError("fan_counts entries must be positive integers")
        result.append(value)
    if not result:
        raise ValueError("fan_counts must contain at least one value")
    if len(set(result)) != len(result):
        raise ValueError("fan_counts must not contain duplicates")
    return tuple(result)


def _affinity_scaled_fan_curve(
    curve: FanCurve, reference_rpm: float, target_rpm: float
) -> tuple[FanCurve, float]:
    """Scale a fixed-geometry fan curve using Q~N and pressure~N^2."""
    reference = _finite_number(reference_rpm, "reference_rpm", positive=True)
    target = _finite_number(target_rpm, "target_rpm", positive=True)
    ratio = target / reference
    if math.isclose(ratio, 1.0, rel_tol=1e-12, abs_tol=1e-12):
        return curve, ratio
    points = tuple((flow * ratio, pressure * ratio * ratio) for flow, pressure in curve.points)
    source = (
        f"{curve.source} [affinity-law-derived from {reference:g} RPM to {target:g} RPM; "
        "constant density and fixed geometry assumed]"
    )
    points = _validate_points(
        points,
        label=source,
        pressure_direction="decreasing",
    )
    scaled = FanCurve(
        points,
        source=source,
    )
    return scaled, ratio


def _resistance_scaled_system_curve(
    curve: SystemCurve, multiplier: float
) -> SystemCurve:
    """Apply a uniform pressure-ordinate multiplier to a tabulated system curve."""
    factor = _finite_number(multiplier, "system_resistance_multiplier", positive=True)
    points = tuple((flow, pressure * factor) for flow, pressure in curve.points)
    source = f"{curve.source} [uniform pressure multiplier={factor:g}]"
    points = _validate_points(
        points,
        label=source,
        pressure_direction="increasing",
    )
    return SystemCurve(
        points,
        source=source,
    )


_failure_category = classify_solver_failure


def _relative_comparison(value: float, baseline: float) -> dict[str, float | None]:
    delta = value - baseline
    percentage = (delta / abs(baseline) * 100.0) if baseline != 0 else None
    return {"absolute_change": delta, "relative_change_percent": percentage}


def run_sensitivity(
    *,
    fan_curve_path: str | Path,
    reference_rpm: float,
    rpm_values: Iterable[float],
    fan_counts: Iterable[int],
    baseline_fan_count: int,
    system_resistance_multipliers: Iterable[float],
    system_pressure_mmh2o: float | None = None,
    system_reference_flow_cfm: float | None = None,
    system_curve_path: str | Path | None = None,
    rpm_scaling_mode: str = "none",
    repo_root: str | Path = ".",
    heat_load_w: float = 300.0,
    air_density_kg_m3: float = 1.204,
    air_specific_heat_j_kg_k: float = 1006.0,
    fan_curve_provenance: str = "unspecified by caller",
) -> dict[str, Any]:
    """Run a deterministic Cartesian sweep against the existing solver.

    The baseline is the reference RPM, ``baseline_fan_count``, and a resistance
    multiplier of 1.0. That baseline must be present in all three sweep axes.
    Supply either a quadratic reference point or a tabulated system curve.
    """
    reference_rpm = _finite_number(reference_rpm, "reference_rpm", positive=True)
    rpms = _unique_positive_floats(rpm_values, "rpm_values")
    counts = _positive_fan_counts(fan_counts)
    multipliers = _unique_positive_floats(
        system_resistance_multipliers, "system_resistance_multipliers"
    )
    if isinstance(baseline_fan_count, bool) or not isinstance(baseline_fan_count, int) or baseline_fan_count < 1:
        raise ValueError("baseline_fan_count must be a positive integer")
    if baseline_fan_count not in counts:
        raise ValueError("fan_counts must include baseline_fan_count")
    if not any(math.isclose(value, reference_rpm, rel_tol=1e-12, abs_tol=1e-12) for value in rpms):
        raise ValueError("rpm_values must include reference_rpm for the baseline scenario")
    if not any(math.isclose(value, 1.0, rel_tol=1e-12, abs_tol=1e-12) for value in multipliers):
        raise ValueError("system_resistance_multipliers must include 1.0 for the baseline scenario")
    if rpm_scaling_mode not in RPM_SCALING_MODES:
        raise ValueError(f"rpm_scaling_mode must be one of {sorted(RPM_SCALING_MODES)}")
    if rpm_scaling_mode == "none" and any(
        not math.isclose(value, reference_rpm, rel_tol=1e-12, abs_tol=1e-12) for value in rpms
    ):
        raise ValueError(
            "rpm_values differ from reference_rpm; explicitly select rpm_scaling_mode='affinity-law' "
            "or supply only the reference RPM"
        )

    root = Path(repo_root).resolve()
    fan_path = _resolve_under_root(fan_curve_path, root)
    fan_curve = FanCurve.from_csv(fan_path)
    if system_curve_path is not None:
        if system_pressure_mmh2o is not None or system_reference_flow_cfm is not None:
            raise ValueError("provide system_curve_path or quadratic reference values, not both")
        system_path = _resolve_under_root(system_curve_path, root)
        base_system_curve = SystemCurve.from_csv(system_path)
        system_mode = "tabulated_curve_uniform_pressure_multiplier"
        quadratic_reference = None
    else:
        if system_pressure_mmh2o is None or system_reference_flow_cfm is None:
            raise ValueError("provide system_curve_path or both quadratic reference values")
        reference_pressure = _finite_number(
            system_pressure_mmh2o, "system_pressure_mmh2o", positive=True
        )
        reference_flow = _finite_number(
            system_reference_flow_cfm, "system_reference_flow_cfm", positive=True
        )
        system_path = None
        base_system_curve = None
        system_mode = "quadratic_screening_K_multiplier"
        quadratic_reference = {
            "pressure_mmh2o": reference_pressure,
            "flow_cfm": reference_flow,
            "base_K_mmh2o_per_cfm2": _finite_number(
                reference_pressure / reference_flow / reference_flow,
                "quadratic system resistance coefficient",
                positive=True,
            ),
        }

    heat_load_w = _finite_number(heat_load_w, "heat_load_w")
    air_density_kg_m3 = _finite_number(air_density_kg_m3, "air_density_kg_m3", positive=True)
    air_specific_heat_j_kg_k = _finite_number(
        air_specific_heat_j_kg_k, "air_specific_heat_j_kg_k", positive=True
    )
    if heat_load_w < 0:
        raise ValueError("heat_load_w must be non-negative")
    if not isinstance(fan_curve_provenance, str) or not fan_curve_provenance.strip():
        raise ValueError("fan_curve_provenance must be a non-empty string")

    scenario_rows: list[dict[str, Any]] = []
    for target_rpm, fan_count, resistance_multiplier in product(rpms, counts, multipliers):
        ratio_estimate = target_rpm / reference_rpm
        if not math.isfinite(ratio_estimate):
            ratio_estimate = None

        row: dict[str, Any] = {
            "rpm": target_rpm,
            "rpm_ratio_to_reference": ratio_estimate,
            "rpm_curve_basis": (
                "reference_curve"
                if math.isclose(target_rpm, reference_rpm, rel_tol=1e-12, abs_tol=1e-12)
                else "affinity_law_derived"
            ),
            "fan_count_parallel": fan_count,
            "system_resistance_multiplier": resistance_multiplier,
        }

        try:
            scaled_fan, rpm_ratio = _affinity_scaled_fan_curve(
                fan_curve, reference_rpm, target_rpm
            )
            row["rpm_ratio_to_reference"] = rpm_ratio

            if system_mode == "tabulated_curve_uniform_pressure_multiplier":
                assert base_system_curve is not None
                sampled_system = _resistance_scaled_system_curve(
                    base_system_curve, resistance_multiplier
                )
                solve_kwargs = {"system_curve": sampled_system}
            else:
                assert quadratic_reference is not None
                solve_kwargs = {
                    "system_pressure_mmh2o": (
                        quadratic_reference["pressure_mmh2o"] * resistance_multiplier
                    ),
                    "system_reference_flow_cfm": quadratic_reference["flow_cfm"],
                }

        except (ValueError, RuntimeError, ArithmeticError) as exc:
            row.update({
                "status": "failed",
                "outputs": None,
                "failure_category": "curve_scaling_failure",
                "error": str(exc),
            })
            scenario_rows.append(row)
            continue

        try:
            result = solve_operating_point(
                curve=scaled_fan,
                fan_count=fan_count,
                heat_load_w=heat_load_w,
                air_density_kg_m3=air_density_kg_m3,
                air_specific_heat_j_kg_k=air_specific_heat_j_kg_k,
                **solve_kwargs,
            )
            outputs = {field: getattr(result, field) for field in OUTPUT_FIELDS}
            outputs["system_resistance_k_mmh2o_per_cfm2"] = result.system_resistance_k_mmh2o_per_cfm2
            row.update({"status": "solved", "outputs": outputs, "failure_category": None, "error": None})
        except (ValueError, RuntimeError, ArithmeticError) as exc:
            row.update({
                "status": "failed",
                "outputs": None,
                "failure_category": _failure_category(exc),
                "error": str(exc),
            })
        scenario_rows.append(row)

    baseline_index = next(
        index for index, row in enumerate(scenario_rows)
        if math.isclose(row["rpm"], reference_rpm, rel_tol=1e-12, abs_tol=1e-12)
        and row["fan_count_parallel"] == baseline_fan_count
        and math.isclose(row["system_resistance_multiplier"], 1.0, rel_tol=1e-12, abs_tol=1e-12)
    )
    baseline_row = scenario_rows[baseline_index]
    if baseline_row["status"] != "solved":
        raise ValueError(f"baseline scenario did not solve: {baseline_row['error']}")
    baseline_outputs = baseline_row["outputs"]
    for row in scenario_rows:
        if row["status"] == "solved":
            row["comparison_to_baseline"] = {
                field: _relative_comparison(row["outputs"][field], baseline_outputs[field])
                for field in OUTPUT_FIELDS
            }
        else:
            row["comparison_to_baseline"] = None

    solved_count = sum(row["status"] == "solved" for row in scenario_rows)
    failed_count = len(scenario_rows) - solved_count
    if system_mode == "tabulated_curve_uniform_pressure_multiplier":
        system_input = {
            "model": system_mode,
            "path": str(system_path),
            "sha256": _sha256(system_path),
            "multiplier_interpretation": "uniformly scales every tabulated pressure ordinate; curve shape is preserved",
        }
    else:
        system_input = {
            "model": system_mode,
            "quadratic_reference": quadratic_reference,
            "multiplier_interpretation": "multiplies quadratic K by scaling reference pressure at fixed reference flow",
        }

    rpm_scaling = {
        "mode": rpm_scaling_mode,
        "reference_rpm": reference_rpm,
        "target_rpm_values": list(rpms),
        "flow_exponent": 1 if rpm_scaling_mode == "affinity-law" else None,
        "pressure_exponent": 2 if rpm_scaling_mode == "affinity-law" else None,
        "assumptions": (
            [
                "same fan geometry and impeller diameter",
                "constant air density between reference and target speeds",
                "similar aerodynamic operating regime; Reynolds-number effects must be reviewed",
                "compressibility and tip-speed Mach-number similarity must also be checked",
                "fan pressure and flow are derived by Q proportional to RPM and pressure proportional to RPM squared",
                "derived target-speed curves are model scenarios, not measured curves",
            ]
            if rpm_scaling_mode == "affinity-law" else []
        ),
        "electrical_input_power": "not modeled; RPM is not used as a substitute for measured motor/fan electrical input",
    }

    return {
        "report_version": REPORT_VERSION,
        "analysis": "deterministic_operating_point_sensitivity",
        "status": "complete" if failed_count == 0 else "partial",
        "interpretation": (
            "Deterministic scenario comparisons conditional on the supplied fan/system curve inputs and model assumptions; "
            "not uncertainty propagation, measurement validation, or a prediction of GPU component temperatures."
        ),
        "run": {
            "scenario_count": len(scenario_rows),
            "solved_scenarios": solved_count,
            "failed_scenarios": failed_count,
            "baseline_scenario_index_zero_based": baseline_index,
        },
        "inputs": {
            "fan_curve": {"path": str(fan_path), "sha256": _sha256(fan_path), "provenance": fan_curve_provenance},
            "reference_rpm": reference_rpm,
            "fan_counts_parallel": list(counts),
            "system_resistance_multipliers": list(multipliers),
            "system": system_input,
            "rpm_scaling": rpm_scaling,
            "fixed_thermal_inputs": {
                "heat_load_w": heat_load_w,
                "air_density_kg_m3": air_density_kg_m3,
                "air_specific_heat_j_kg_k": air_specific_heat_j_kg_k,
            },
            "solver_source_sha256": _sha256(Path(__file__).with_name("fan_operating_point.py")),
        },
        "baseline": {
            "rpm": reference_rpm,
            "fan_count_parallel": baseline_fan_count,
            "system_resistance_multiplier": 1.0,
            "outputs": baseline_outputs,
        },
        "scenarios": scenario_rows,
        "limitations": [
            "parallel fan arrays assume identical fans and equal flow sharing",
            "the system-resistance multiplier is a scenario parameter, not a measured change in MI50 resistance",
            "RPM affinity-law results require a similarity assessment and must not be mistaken for measured multi-speed curves",
            "motor electrical input and fan interaction effects are not modeled",
            "ideal bulk-air temperature rise is not GPU, HBM, VRM, or heatsink temperature",
        ],
    }


def _parse_float_list(value: str, label: str) -> list[float]:
    try:
        result = [float(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{label} must be a comma-separated list of numbers") from exc
    if not result:
        raise argparse.ArgumentTypeError(f"{label} must contain at least one value")
    if not all(math.isfinite(item) for item in result):
        raise argparse.ArgumentTypeError(f"{label} values must be finite")
    return result


def _parse_int_list(value: str, label: str) -> list[int]:
    try:
        result = [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{label} must be a comma-separated list of integers") from exc
    if not result:
        raise argparse.ArgumentTypeError(f"{label} must contain at least one value")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run deterministic fan-count, RPM, and system-resistance sensitivity scenarios."
    )
    parser.add_argument("--fan-curve", required=True, help="single-fan CSV at reference RPM")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--reference-rpm", required=True, type=float)
    parser.add_argument("--rpms", required=True, type=lambda value: _parse_float_list(value, "--rpms"))
    parser.add_argument("--rpm-scaling-mode", choices=sorted(RPM_SCALING_MODES), default="none")
    parser.add_argument("--fan-counts", required=True, type=lambda value: _parse_int_list(value, "--fan-counts"))
    parser.add_argument("--baseline-fan-count", required=True, type=int)
    parser.add_argument(
        "--system-resistance-multipliers", required=True,
        type=lambda value: _parse_float_list(value, "--system-resistance-multipliers"),
        help="positive resistance factors; must include 1.0 for the baseline",
    )
    system_group = parser.add_mutually_exclusive_group(required=True)
    system_group.add_argument("--system-curve", help="tabulated system-curve CSV")
    system_group.add_argument("--system-pressure-mmh2o", type=float, help="quadratic reference pressure (screening input)")
    parser.add_argument("--system-reference-flow-cfm", type=float, help="quadratic reference flow; required with reference pressure")
    parser.add_argument("--heat-load-w", type=float, default=300.0)
    parser.add_argument("--air-density-kg-m3", type=float, default=1.204)
    parser.add_argument("--air-cp-j-kg-k", type=float, default=1006.0)
    parser.add_argument("--fan-curve-provenance", default="unspecified by caller")
    parser.add_argument("--output", help="write JSON report to this path instead of stdout")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.system_curve and args.system_reference_flow_cfm is not None:
        parser.error("--system-reference-flow-cfm is only valid with --system-pressure-mmh2o")
    if args.system_pressure_mmh2o is not None and args.system_reference_flow_cfm is None:
        parser.error("--system-reference-flow-cfm is required with --system-pressure-mmh2o")
    try:
        report = run_sensitivity(
            fan_curve_path=args.fan_curve,
            repo_root=args.repo_root,
            reference_rpm=args.reference_rpm,
            rpm_values=args.rpms,
            rpm_scaling_mode=args.rpm_scaling_mode,
            fan_counts=args.fan_counts,
            baseline_fan_count=args.baseline_fan_count,
            system_resistance_multipliers=args.system_resistance_multipliers,
            system_pressure_mmh2o=args.system_pressure_mmh2o,
            system_reference_flow_cfm=args.system_reference_flow_cfm,
            system_curve_path=args.system_curve,
            heat_load_w=args.heat_load_w,
            air_density_kg_m3=args.air_density_kg_m3,
            air_specific_heat_j_kg_k=args.air_cp_j_kg_k,
            fan_curve_provenance=args.fan_curve_provenance,
        )
        rendered = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.output:
            protected_paths = [
                Path(report["inputs"]["fan_curve"]["path"]),
                Path(__file__).with_name("fan_operating_point.py"),
            ]
            system_input_path = report["inputs"]["system"].get("path")
            if system_input_path is not None:
                protected_paths.append(Path(system_input_path))

            _reject_output_input_collision(args.output, protected_paths)
            Path(args.output).write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
