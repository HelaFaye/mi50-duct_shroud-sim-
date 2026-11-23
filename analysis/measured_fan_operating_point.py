#!/usr/bin/env python3
"""Operating-point analysis for measured fan curves that are not monotonic.

This module is deliberately separate from ``fan_operating_point`` and its
strict ``FanCurve`` contract.  It preserves signed measured pressure values
and finds every positive intersection with either a tabulated ``SystemCurve``
or a quadratic screening resistance model.  It does not smooth, clip, sort,
or otherwise repair measurements.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from analysis.fan_operating_point import SystemCurve

REQUIRED_COLUMNS = {
    "source_row_index",
    "pwm_percent",
    "point_in_setting",
    "flow_cfm",
    "static_pressure_mmaq",
    "fan_speed_rpm",
    "current_a",
    "power_w",
}
MEASUREMENT_PRESSURE_UNIT = "mmAq"
SOLVER_PRESSURE_UNIT = "mmH2O"
# mmAq and mmH2O are equivalent nominal water-column units for this model.
PRESSURE_UNIT_SCALE_TO_MMH2O = 1.0
PA_PER_MMH2O = 9.80665
FLOW_ABS_TOLERANCE = 1e-9
PRESSURE_ABS_TOLERANCE = 1e-10
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class MeasuredFanPoint:
    source_row_index: int
    pwm_percent: int
    point_in_setting: int
    flow_cfm: float
    static_pressure_mmaq: float
    fan_speed_rpm: float
    current_a: float
    power_w: float


@dataclass(frozen=True)
class MeasuredFanCurve:
    """One unmodified measured P-Q table at a single PWM setting."""

    pwm_percent: int
    points: tuple[MeasuredFanPoint, ...]
    source: str

    @property
    def min_flow_cfm(self) -> float:
        return self.points[0].flow_cfm

    @property
    def max_flow_cfm(self) -> float:
        return self.points[-1].flow_cfm

    @property
    def rpm_range(self) -> tuple[float, float]:
        rpms = [point.fan_speed_rpm for point in self.points]
        return min(rpms), max(rpms)

    @property
    def max_adjacent_pressure_increase_mmaq(self) -> float:
        return max(
            0.0,
            max(
                (right.static_pressure_mmaq - left.static_pressure_mmaq for left, right in zip(self.points, self.points[1:])),
                default=0.0,
            ),
        )

    def interpolate(self, flow_cfm: float) -> dict[str, float]:
        """Linearly interpolate pressure and point telemetry without extrapolation."""
        if not math.isfinite(flow_cfm):
            raise ValueError("flow must be finite")
        low = self.min_flow_cfm
        high = self.max_flow_cfm
        tolerance = 1e-10 * max(1.0, high)
        if flow_cfm < low - tolerance or flow_cfm > high + tolerance:
            raise ValueError(
                f"flow {flow_cfm:.9g} CFM is outside measured PWM {self.pwm_percent}% "
                f"range ({low:.9g}–{high:.9g} CFM); extrapolation is disabled"
            )
        flow_cfm = min(max(flow_cfm, low), high)
        for left, right in zip(self.points, self.points[1:]):
            if flow_cfm <= right.flow_cfm:
                fraction = (flow_cfm - left.flow_cfm) / (
                    right.flow_cfm - left.flow_cfm
                )
                return {
                    "static_pressure_mmaq": _lerp(
                        left.static_pressure_mmaq,
                        right.static_pressure_mmaq,
                        fraction,
                    ),
                    "fan_speed_rpm": _lerp(
                        left.fan_speed_rpm, right.fan_speed_rpm, fraction
                    ),
                    "current_a": _lerp(left.current_a, right.current_a, fraction),
                    "power_w": _lerp(left.power_w, right.power_w, fraction),
                }
        point = self.points[-1]
        return {
            "static_pressure_mmaq": point.static_pressure_mmaq,
            "fan_speed_rpm": point.fan_speed_rpm,
            "current_a": point.current_a,
            "power_w": point.power_w,
        }


def _lerp(a: float, b: float, fraction: float) -> float:
    return a + (b - a) * fraction


def _finite_float(value: str | None, *, label: str, row: int) -> float:
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"row {row}: {label} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"row {row}: {label} must be finite")
    return result


def load_measured_fan_curves(
    path: str | Path,
    pwm_values: Iterable[int] | None = None,
) -> dict[int, MeasuredFanCurve]:
    """Load and validate source-ordered measured P-Q tables by PWM.

    Pressure is allowed to be signed and non-monotonic. Flow must remain
    strictly increasing within each setting because interpolation requires an
    unambiguous flow coordinate. Original CSV bytes are never rewritten.
    """
    csv_path = Path(path)
    requested = None if pwm_values is None else tuple(pwm_values)
    if requested is not None:
        if not requested:
            raise ValueError("at least one PWM setting is required")
        if len(set(requested)) != len(requested):
            raise ValueError("PWM settings must not contain duplicates")
        if any(not isinstance(pwm, int) or isinstance(pwm, bool) or not 0 <= pwm <= 100 for pwm in requested):
            raise ValueError("PWM settings must be integers from 0 through 100")

    grouped: dict[int, list[MeasuredFanPoint]] = {}
    expected_source_index = 1
    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - headers
        if missing:
            raise ValueError(
                f"{csv_path}: missing required column(s): {', '.join(sorted(missing))}"
            )
        for csv_row, row in enumerate(reader, start=2):
            source_row_value = _finite_float(
                row["source_row_index"], label="source_row_index", row=csv_row
            )
            if not source_row_value.is_integer():
                raise ValueError(f"row {csv_row}: source_row_index must be an integer")
            source_row_index = int(source_row_value)
            if source_row_index != expected_source_index:
                raise ValueError(
                    f"row {csv_row}: source_row_index must preserve sequential source order; "
                    f"expected {expected_source_index}, got {source_row_index}"
                )
            expected_source_index += 1

            pwm_value = _finite_float(row["pwm_percent"], label="pwm_percent", row=csv_row)
            if not pwm_value.is_integer() or not 0 <= pwm_value <= 100:
                raise ValueError(f"row {csv_row}: pwm_percent must be an integer from 0 through 100")
            pwm = int(pwm_value)
            point_value = _finite_float(row["point_in_setting"], label="point_in_setting", row=csv_row)
            if not point_value.is_integer() or point_value < 1:
                raise ValueError(f"row {csv_row}: point_in_setting must be a positive integer")

            point = MeasuredFanPoint(
                source_row_index=source_row_index,
                pwm_percent=pwm,
                point_in_setting=int(point_value),
                flow_cfm=_finite_float(row["flow_cfm"], label="flow_cfm", row=csv_row),
                static_pressure_mmaq=_finite_float(
                    row["static_pressure_mmaq"], label="static_pressure_mmaq", row=csv_row
                ),
                fan_speed_rpm=_finite_float(row["fan_speed_rpm"], label="fan_speed_rpm", row=csv_row),
                current_a=_finite_float(row["current_a"], label="current_a", row=csv_row),
                power_w=_finite_float(row["power_w"], label="power_w", row=csv_row),
            )
            if point.flow_cfm < 0:
                raise ValueError(f"row {csv_row}: flow_cfm must be non-negative")
            if point.fan_speed_rpm <= 0:
                raise ValueError(f"row {csv_row}: fan_speed_rpm must be positive")
            if point.current_a < 0 or point.power_w < 0:
                raise ValueError(f"row {csv_row}: current_a and power_w must be non-negative")
            grouped.setdefault(pwm, []).append(point)

    if not grouped:
        raise ValueError(f"{csv_path}: no measurement records found")

    curves: dict[int, MeasuredFanCurve] = {}
    for pwm, points_list in sorted(grouped.items()):
        points = tuple(points_list)
        point_indices = [point.point_in_setting for point in points]
        if point_indices != list(range(1, len(points) + 1)):
            raise ValueError(
                f"PWM {pwm}%: point_in_setting must be consecutive and retain source order"
            )
        if len(points) < 2:
            raise ValueError(f"PWM {pwm}%: at least two measured points are required")
        for index, (left, right) in enumerate(zip(points, points[1:]), start=1):
            if right.flow_cfm <= left.flow_cfm:
                raise ValueError(
                    f"PWM {pwm}%: flow must be strictly increasing between points "
                    f"{index} and {index + 1}; raw pressure is not required to be monotonic"
                )
        curves[pwm] = MeasuredFanCurve(pwm, points, str(csv_path))

    if requested is None:
        return curves
    missing_pwm = sorted(set(requested) - set(curves))
    if missing_pwm:
        raise ValueError(f"{csv_path}: requested PWM setting(s) not found: {missing_pwm}")
    return {pwm: curves[pwm] for pwm in requested}


def _unique_sorted(values: Iterable[float], tolerance: float) -> list[float]:
    result: list[float] = []
    for value in sorted(values):
        if not result or abs(value - result[-1]) > tolerance:
            result.append(value)
    return result


def _fan_segment(curve: MeasuredFanCurve, total_flow_midpoint: float, fan_count: int):
    per_fan_midpoint = total_flow_midpoint / fan_count
    for left, right in zip(curve.points, curve.points[1:]):
        if per_fan_midpoint <= right.flow_cfm:
            slope_total = (right.static_pressure_mmaq - left.static_pressure_mmaq) / (
                fan_count * (right.flow_cfm - left.flow_cfm)
            )
            intercept = left.static_pressure_mmaq - slope_total * fan_count * left.flow_cfm
            return slope_total, intercept
    raise RuntimeError("could not identify measured fan segment inside interpolation domain")


def _quadratic_roots(a: float, b: float, c: float) -> list[float]:
    """Return finite real roots using a cancellation-resistant formulation."""
    if not all(math.isfinite(value) for value in (a, b, c)):
        return []

    scale = max(abs(a), abs(b), abs(c))
    if scale == 0.0:
        return []

    # Normalize to avoid overflow in the discriminant calculation.
    a, b, c = a / scale, b / scale, c / scale

    if a == 0.0:
        if b == 0.0:
            return []
        root = -c / b
        return [root] if math.isfinite(root) else []

    b_squared = b * b
    four_ac = 4.0 * a * c
    discriminant = math.fsum((b_squared, -four_ac))
    discriminant_scale = max(1.0, abs(b_squared), abs(four_ac))
    tolerance = 32.0 * math.ulp(discriminant_scale)

    # Correct a small negative roundoff error, but preserve small positive
    # discriminants because they can represent distinct real roots.
    if discriminant < 0.0:
        if abs(discriminant) > tolerance:
            return []
        discriminant = 0.0

    square_root = math.sqrt(discriminant)

    if square_root == 0.0:
        root = -b / (2.0 * a)
        return [root] if math.isfinite(root) else []

    # Stable quadratic formula: calculate the large root using q, then
    # recover the smaller root using the product-of-roots identity.
    q = -0.5 * (b + math.copysign(square_root, b))

    if q == 0.0:
        root = -b / (2.0 * a)
        return [root] if math.isfinite(root) else []

    roots = (q / a, c / q)
    return sorted(root for root in roots if math.isfinite(root))


def solve_measured_operating_points(
    curve: MeasuredFanCurve,
    fan_count: int,
    *,
    system_curve: SystemCurve | None = None,
    system_pressure_mmh2o: float | None = None,
    system_reference_flow_cfm: float | None = None,
) -> dict[str, Any]:
    """Find all positive fan/system intersections, retaining measured anomalies.

    With a tabulated system curve, both sides are piecewise linear between the
    union of their breakpoints. With the quadratic screening model, each fan
    segment yields a quadratic residual and can contain zero, one, or two roots.
    """
    if not isinstance(fan_count, int) or isinstance(fan_count, bool) or fan_count < 1:
        raise ValueError("fan_count must be a positive integer")
    if system_curve is not None:
        if system_pressure_mmh2o is not None or system_reference_flow_cfm is not None:
            raise ValueError("provide system_curve or quadratic reference values, not both")
        system_model = "tabulated_system_curve"
        min_total_flow = fan_count * curve.min_flow_cfm
        max_total_flow = min(fan_count * curve.max_flow_cfm, system_curve.max_flow_cfm)
        resistance_k = None
    else:
        if system_pressure_mmh2o is None or system_reference_flow_cfm is None:
            raise ValueError("provide system_curve or both quadratic reference values")
        if not math.isfinite(system_pressure_mmh2o) or not math.isfinite(system_reference_flow_cfm):
            raise ValueError("quadratic system reference values must be finite")
        if system_pressure_mmh2o <= 0 or system_reference_flow_cfm <= 0:
            raise ValueError("quadratic system reference pressure and flow must be positive")
        resistance_k = system_pressure_mmh2o / (system_reference_flow_cfm ** 2)
        if not math.isfinite(resistance_k) or resistance_k <= 0:
            raise ValueError("quadratic system resistance must be finite and positive")
        system_model = "quadratic_screening_reference"
        min_total_flow = fan_count * curve.min_flow_cfm
        max_total_flow = fan_count * curve.max_flow_cfm

    if max_total_flow <= min_total_flow:
        raise ValueError("common fan/system interpolation domain must have positive flow range")

    flow_tolerance = FLOW_ABS_TOLERANCE * max(1.0, max_total_flow)
    if max_total_flow - min_total_flow <= flow_tolerance:
        raise ValueError("common fan/system interpolation domain is below flow resolution")

    pressure_tolerance = PRESSURE_ABS_TOLERANCE
    breaks = [min_total_flow, max_total_flow]
    breaks.extend(
        point.flow_cfm * fan_count
        for point in curve.points
        if min_total_flow < point.flow_cfm * fan_count < max_total_flow
    )
    if system_curve is not None:
        breaks.extend(
            flow for flow, _ in system_curve.points
            if min_total_flow < flow < max_total_flow
        )
    breaks = _unique_sorted(breaks, flow_tolerance)

    roots: list[float] = []
    coincident_segments: list[list[float]] = []
    for left, right in zip(breaks, breaks[1:]):
        midpoint = (left + right) / 2.0
        fan_slope, fan_intercept = _fan_segment(curve, midpoint, fan_count)

        if system_curve is not None:
            sys_left = system_curve.pressure_at(left)
            sys_right = system_curve.pressure_at(right)
            system_slope = (sys_right - sys_left) / (right - left)
            system_intercept = sys_left - system_slope * left
            residual_left = fan_slope * left + fan_intercept - sys_left
            residual_right = fan_slope * right + fan_intercept - sys_right
            if abs(residual_left) <= pressure_tolerance and abs(residual_right) <= pressure_tolerance:
                coincident_segments.append([left, right])
                continue
            if abs(residual_left) <= pressure_tolerance:
                roots.append(left)
            if abs(residual_right) <= pressure_tolerance:
                roots.append(right)
            if residual_left * residual_right < 0.0:
                roots.append(
                    left + (right - left) * (-residual_left) / (residual_right - residual_left)
                )
        else:
            assert resistance_k is not None
            # fan_pressure(total_flow) - K*total_flow^2 = 0
            # A root of this segment's quadratic is valid only inside the
            # measured flow interval that produced its affine fan-pressure
            # expression.  Filtering only against the global flow domain
            # silently extrapolates every segment and creates spurious roots.
            for candidate in _quadratic_roots(
                -resistance_k, fan_slope, fan_intercept
            ):
                if (
                    math.isfinite(candidate)
                    and candidate >= left - flow_tolerance
                    and candidate <= right + flow_tolerance
                ):
                    roots.append(min(max(candidate, left), right))

    bounded_roots = [
        min(max(root, min_total_flow), max_total_flow)
        for root in roots
        if math.isfinite(root)
        and root > max(0.0, min_total_flow - flow_tolerance)
        and root <= max_total_flow + flow_tolerance
    ]
    unique_roots = _unique_sorted(bounded_roots, flow_tolerance)

    merged_coincident: list[list[float]] = []
    for segment_left, segment_right in sorted(coincident_segments):
        if merged_coincident and abs(segment_left - merged_coincident[-1][1]) <= flow_tolerance:
            merged_coincident[-1][1] = segment_right
        else:
            merged_coincident.append([segment_left, segment_right])

    # Endpoints of a coincident interval belong to a continuum of
    # intersections, not to isolated mathematical roots.
    unique_roots = [
        root for root in unique_roots
        if not any(
            left - flow_tolerance <= root <= right + flow_tolerance
            for left, right in merged_coincident
        )
    ]

    root_records: list[dict[str, Any]] = []
    for total_flow in unique_roots:
        per_fan_flow = total_flow / fan_count
        measured = curve.interpolate(per_fan_flow)
        fan_pressure_mmh2o = measured["static_pressure_mmaq"] * PRESSURE_UNIT_SCALE_TO_MMH2O
        if system_curve is not None:
            system_pressure = system_curve.pressure_at(total_flow)
        else:
            assert resistance_k is not None
            system_pressure = resistance_k * total_flow ** 2
        root_records.append({
            "total_flow_cfm": total_flow,
            "per_fan_flow_cfm": per_fan_flow,
            "fan_static_pressure_mmh2o": fan_pressure_mmh2o,
            "system_pressure_drop_mmh2o": system_pressure,
            "pressure_residual_mmh2o": fan_pressure_mmh2o - system_pressure,
            "interpolated_fan_speed_rpm": measured["fan_speed_rpm"],
            "per_fan_current_a": measured["current_a"],
            "per_fan_power_w": measured["power_w"],
            "array_current_a_estimate": measured["current_a"] * fan_count,
            "array_power_w_estimate": measured["power_w"] * fan_count,
            "electrical_array_estimate_basis": "per-fan telemetry linearly interpolated at the operating point, multiplied by fan count",
        })

    if merged_coincident:
        status = "coincident_segment"
    elif len(root_records) == 0:
        status = "no_positive_intersection"
    elif len(root_records) == 1:
        status = "unique_intersection"
    else:
        status = "multiple_intersections"

    return {
        "status": status,
        "mathematical_intersection_count": len(root_records),
        "fan_count_parallel": fan_count,
        "pwm_percent": curve.pwm_percent,
        "system_model": system_model,
        "common_flow_domain_cfm": [min_total_flow, max_total_flow],
        "roots": root_records,
        "coincident_segments_total_flow_cfm": merged_coincident,
        "limitations": [
            "measured pressure reversals and signed terminal values are retained; no smoothing, clipping, or monotonic projection is applied",
            "quadratic roots are retained only inside the measured segment that generated each polynomial; segment extrapolation is disabled",
            "all intersections inside the common supplied curve domain are reported; multiple intersections are not silently reduced to one operating point",
            "mmAq measurements are treated as nominally equivalent to mmH2O for pressure comparison",
            "interpolated current and power, and fan-count-scaled array totals, are estimates between measured points",
        ],
    }


def _parse_int_list(value: str, label: str, *, minimum: int, maximum: int) -> list[int]:
    try:
        items = [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{label} must be a comma-separated integer list") from exc
    if not items:
        raise argparse.ArgumentTypeError(f"{label} must contain at least one value")
    if len(set(items)) != len(items):
        raise argparse.ArgumentTypeError(f"{label} must not contain duplicates")
    if any(item < minimum or item > maximum for item in items):
        raise argparse.ArgumentTypeError(f"{label} values must be in {minimum}..{maximum}")
    return items


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze all measured fan/system intersections without repairing raw fan measurements."
    )
    parser.add_argument("--measurement-csv", required=True, help="long-form measured fan P-Q CSV")
    parser.add_argument("--pwms", required=True, type=lambda v: _parse_int_list(v, "--pwms", minimum=0, maximum=100))
    parser.add_argument("--fan-counts", required=True, type=lambda v: _parse_int_list(v, "--fan-counts", minimum=1, maximum=100))
    system_group = parser.add_mutually_exclusive_group(required=True)
    system_group.add_argument("--system-curve", help="tabulated system curve CSV")
    system_group.add_argument("--system-pressure-mmh2o", type=float, help="hypothetical quadratic screening reference pressure")
    parser.add_argument("--system-reference-flow-cfm", type=float, help="quadratic reference flow; required with pressure")
    parser.add_argument(
        "--pressure-expanded-uncertainty-pa",
        type=float,
        help="optional source-declared expanded static-pressure uncertainty in Pa; not a pointwise PDF",
    )
    parser.add_argument("--output", help="write JSON report to this path instead of stdout")
    return parser


def run_measured_sweep(
    measurement_csv: str | Path,
    *,
    pwm_values: Iterable[int],
    fan_counts: Iterable[int],
    system_curve: SystemCurve | None = None,
    system_pressure_mmh2o: float | None = None,
    system_reference_flow_cfm: float | None = None,
    pressure_expanded_uncertainty_pa: float | None = None,
) -> dict[str, Any]:
    path = Path(measurement_csv)
    pwms = tuple(pwm_values)
    counts = tuple(fan_counts)
    if not counts or len(set(counts)) != len(counts):
        raise ValueError("fan_counts must be non-empty and contain no duplicates")
    if any(not isinstance(n, int) or isinstance(n, bool) or n < 1 for n in counts):
        raise ValueError("fan_counts must contain positive integers")
    curves = load_measured_fan_curves(path, pwms)
    if pressure_expanded_uncertainty_pa is not None:
        if not math.isfinite(pressure_expanded_uncertainty_pa) or pressure_expanded_uncertainty_pa <= 0:
            raise ValueError("pressure_expanded_uncertainty_pa must be finite and positive")
        pressure_expanded_uncertainty_mmh2o = pressure_expanded_uncertainty_pa / PA_PER_MMH2O
    else:
        pressure_expanded_uncertainty_mmh2o = None

    scenarios: list[dict[str, Any]] = []
    for pwm in pwms:
        curve = curves[pwm]
        for fan_count in counts:
            result = solve_measured_operating_points(
                curve,
                fan_count,
                system_curve=system_curve,
                system_pressure_mmh2o=system_pressure_mmh2o,
                system_reference_flow_cfm=system_reference_flow_cfm,
            )
            scenarios.append(result)

    if system_curve is not None:
        system = {"model": "tabulated_system_curve", "source": system_curve.source}
    else:
        system = {
            "model": "quadratic_screening_reference",
            "reference_pressure_mmh2o": system_pressure_mmh2o,
            "reference_flow_cfm": system_reference_flow_cfm,
            "resistance_k_mmh2o_per_cfm2": (
                system_pressure_mmh2o / system_reference_flow_cfm ** 2
                if system_pressure_mmh2o is not None and system_reference_flow_cfm is not None
                else None
            ),
            "warning": "hypothetical screening input unless supported by a measured system curve",
        }

    raw = path.read_bytes()
    curve_diagnostics = []
    for pwm in pwms:
        curve = curves[pwm]
        maximum_increase = curve.max_adjacent_pressure_increase_mmaq
        curve_diagnostics.append({
            "pwm_percent": pwm,
            "measurement_points": len(curve.points),
            "rpm_min": curve.rpm_range[0],
            "rpm_max": curve.rpm_range[1],
            "maximum_adjacent_pressure_increase_mmaq": maximum_increase,
            "declared_pressure_expanded_uncertainty_mmh2o": pressure_expanded_uncertainty_mmh2o,
            "maximum_increase_within_declared_expanded_uncertainty": (
                maximum_increase <= pressure_expanded_uncertainty_mmh2o
                if pressure_expanded_uncertainty_mmh2o is not None else None
            ),
            "interpretation": (
                "comparison with caller-declared apparatus-level expanded pressure uncertainty; "
                "context only, not a pointwise uncertainty assignment"
                if pressure_expanded_uncertainty_mmh2o is not None
                else "no pressure uncertainty comparison supplied"
            ),
        })
    return {
        "report_version": "1.0",
        "analysis": "measured_fan_operating_point_sweep",
        "interpretation": "Measured-curve intersection analysis; does not repair or force monotonicity on laboratory fan measurements.",
        "source": {
            "path": str(path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "measurement_record_count": sum(len(curves[pwm].points) for pwm in pwms),
            "selected_pwm_settings": list(pwms),
            "pressure_measurement_unit": MEASUREMENT_PRESSURE_UNIT,
            "solver_pressure_unit": SOLVER_PRESSURE_UNIT,
            "pressure_unit_scale": PRESSURE_UNIT_SCALE_TO_MMH2O,
            "declared_pressure_expanded_uncertainty_pa": pressure_expanded_uncertainty_pa,
            "declared_pressure_expanded_uncertainty_mmh2o": pressure_expanded_uncertainty_mmh2o,
        },
        "inputs": {"fan_counts_parallel": list(counts), "system": system},
        "curve_diagnostics": curve_diagnostics,
        "run": {
            "scenario_count": len(scenarios),
            "unique_intersections": sum(s["status"] == "unique_intersection" for s in scenarios),
            "multiple_intersection_scenarios": sum(s["status"] == "multiple_intersections" for s in scenarios),
            "no_intersection_scenarios": sum(s["status"] == "no_positive_intersection" for s in scenarios),
            "coincident_segment_scenarios": sum(s["status"] == "coincident_segment" for s in scenarios),
        },
        "scenarios": scenarios,
        "global_limitations": [
            "the G2 source data are independent laboratory measurements, not a measurement of the installed MI50 system",
            "a hypothetical quadratic reference is useful for software/model screening only and is not MI50 system characterization",
            "the solver reports every piecewise-mathematical positive intersection; it does not assume uniqueness when pressure data are non-monotonic",
            "local pressure reversals can create extra numerical intersections even when the reversals are smaller than the report's expanded apparatus uncertainty; do not interpret every root as a distinct physical steady state",
            "no uncertainty distribution or M2 uncertainty sidecar is inferred from the report uncertainty summary",
        ],
    }



def _path_has_symlink_component(path: Path) -> bool:
    """Return whether any existing component of a path is a symlink."""
    absolute = path if path.is_absolute() else Path.cwd() / path
    current = Path(absolute.anchor)

    for component in absolute.parts[1:]:
        if component in ("", "."):
            continue
        current = current / component
        try:
            if current.is_symlink():
                return True
        except OSError:
            return True

    return False


def _resolve_safe_output_path(
    output_value: str | Path,
    *,
    repo_root: str | Path,
    input_paths: Iterable[str | Path],
) -> Path:
    """Validate an output destination and return its resolved absolute path.

    Repository-local reports are restricted to results/. External destinations
    must be explicit absolute paths. Symlinks, missing parent directories,
    non-file targets, and analysis-input collisions are rejected.
    """
    raw = Path(output_value).expanduser()
    if not str(output_value).strip() or raw.name in ("", ".", ".."):
        raise ValueError("--output must identify a file")

    lexical = raw if raw.is_absolute() else Path.cwd() / raw

    if _path_has_symlink_component(lexical):
        raise ValueError("--output must not contain symlink components")

    root = Path(repo_root).resolve()
    resolved = lexical.resolve(strict=False)
    results_root = root / "results"

    if _path_has_symlink_component(results_root):
        raise ValueError("repository results directory must not contain symlinks")

    resolved_results = results_root.resolve(strict=False)

    if not resolved_results.is_relative_to(root):
        raise ValueError("repository results directory must resolve inside repository root")

    if resolved.is_relative_to(root):
        if not resolved.is_relative_to(resolved_results):
            raise ValueError(
                f"repository-local --output must resolve inside {resolved_results}"
            )
    elif not raw.is_absolute():
        raise ValueError(
            "external --output destinations must be specified as absolute paths"
        )

    if not resolved.parent.is_dir():
        raise ValueError(
            f"--output parent directory must already exist: {resolved.parent}"
        )

    if resolved.exists() and not resolved.is_file():
        raise ValueError("--output must identify a regular file")

    for input_value in input_paths:
        source = Path(input_value)
        source = source if source.is_absolute() else Path.cwd() / source
        resolved_source = source.resolve(strict=False)

        same_file = resolved == resolved_source

        if not same_file and resolved.exists() and source.exists():
            try:
                same_file = resolved.samefile(source)
            except OSError:
                same_file = False

        if same_file:
            raise ValueError(
                f"--output must not overwrite an analysis input: {source}"
            )

    return resolved


def _atomic_write_text(path: str | Path, content: str) -> None:
    """Atomically replace a report using a temporary file in its directory."""
    target = Path(path)

    if not target.parent.is_dir():
        raise ValueError(
            f"output parent directory does not exist: {target.parent}"
        )

    if _path_has_symlink_component(target):
        raise ValueError("output target must not contain symlink components")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temporary = Path(temporary_name)

    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())

        # Recheck after preparing the temporary file.
        if _path_has_symlink_component(target):
            raise ValueError("output target acquired a symlink component")

        os.replace(temporary, target)

    except BaseException:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise



def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.system_curve and args.system_reference_flow_cfm is not None:
        parser.error("--system-reference-flow-cfm is only valid with --system-pressure-mmh2o")
    if args.system_pressure_mmh2o is not None and args.system_reference_flow_cfm is None:
        parser.error("--system-reference-flow-cfm is required with --system-pressure-mmh2o")
    try:
        system_curve = SystemCurve.from_csv(args.system_curve) if args.system_curve else None
        report = run_measured_sweep(
            args.measurement_csv,
            pwm_values=args.pwms,
            fan_counts=args.fan_counts,
            system_curve=system_curve,
            system_pressure_mmh2o=args.system_pressure_mmh2o,
            system_reference_flow_cfm=args.system_reference_flow_cfm,
            pressure_expanded_uncertainty_pa=args.pressure_expanded_uncertainty_pa,
        )
        rendered = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.output:
            protected_inputs = [args.measurement_csv]
            if args.system_curve:
                protected_inputs.append(args.system_curve)

            output_path = _resolve_safe_output_path(
                args.output,
                repo_root=REPOSITORY_ROOT,
                input_paths=protected_inputs,
            )
            _atomic_write_text(output_path, rendered)
        else:
            sys.stdout.write(rendered)
        return 0
    except (OSError, ValueError, RuntimeError, ArithmeticError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
