#!/usr/bin/env python3
"""Solve an identical parallel fan array against a system resistance curve.

Two system models are supported:
* a quadratic approximation, dp = K * Q_total**2, fitted from one point;
* a measured/digitized multi-point system curve in CSV.

The fan curve CSV columns are flow_cfm,static_pressure_mmh2o. A system curve
CSV uses the same column names, but pressure must be non-decreasing with flow
and the first point must be (0 CFM, 0 mmH2O). Neither curve is extrapolated.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from bisect import bisect_left
from dataclasses import asdict, dataclass
from functools import cached_property
from pathlib import Path
from typing import Iterable


CURVE_COLUMNS = {"flow_cfm", "static_pressure_mmh2o"}


def _read_curve_csv(path: str | Path) -> list[tuple[float, float]]:
    csv_path = Path(path)
    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        missing = CURVE_COLUMNS - headers
        if missing:
            raise ValueError(
                f"{csv_path}: missing required CSV column(s): "
                + ", ".join(sorted(missing))
            )
        points: list[tuple[float, float]] = []
        for row_number, row in enumerate(reader, start=2):
            try:
                flow = float(row["flow_cfm"])
                pressure = float(row["static_pressure_mmh2o"])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"{csv_path}:{row_number}: flow and pressure must be numeric"
                ) from exc
            points.append((flow, pressure))
    return points


def _validate_points(
    points: Iterable[tuple[float, float]],
    *,
    label: str,
    pressure_direction: str,
) -> tuple[tuple[float, float], ...]:
    pts = tuple(points)
    if len(pts) < 2:
        raise ValueError(f"{label}: at least two curve points are required")
    for index, (flow, pressure) in enumerate(pts, start=1):
        if not math.isfinite(flow) or not math.isfinite(pressure):
            raise ValueError(f"{label}: point {index} contains a non-finite value")
        if flow < 0 or pressure < 0:
            raise ValueError(f"{label}: flow and pressure must be non-negative")
        if index > 1:
            previous_flow, previous_pressure = pts[index - 2]
            if flow <= previous_flow:
                raise ValueError(f"{label}: flow values must be strictly increasing")
            if pressure_direction == "decreasing" and pressure > previous_pressure + 1e-6:
                raise ValueError(f"{label}: pressure must be non-increasing with flow")
            if pressure_direction == "increasing" and pressure < previous_pressure - 1e-6:
                raise ValueError(f"{label}: pressure must be non-decreasing with flow")
    if abs(pts[0][0]) > 1e-9:
        raise ValueError(f"{label}: first point must be at 0 CFM")
    if pressure_direction == "decreasing":
        if pts[0][1] <= 0:
            raise ValueError(f"{label}: shutoff pressure must be greater than 0")
        if abs(pts[-1][1]) > 1e-6:
            raise ValueError(f"{label}: last point must be at 0 mmH2O (free-air point)")
    else:
        if abs(pts[0][1]) > 1e-6:
            raise ValueError(f"{label}: system curve must start at 0 mmH2O")
        if pts[-1][1] <= 0:
            raise ValueError(f"{label}: system curve must contain a positive pressure drop")
    return pts


class _PiecewiseLinearCurve:
    """Shared piecewise-linear interpolation with strict range checks."""

    points: tuple[tuple[float, float], ...]
    source: str
    _curve_name = "curve"

    @property
    def max_flow_cfm(self) -> float:
        return self.points[-1][0]

    @cached_property
    def _flows(self) -> tuple[float, ...]:
        # Cached on the instance (not a dataclass field); points are immutable.
        return tuple(flow for flow, _ in self.points)

    def pressure_at(self, flow_cfm: float) -> float:
        if not math.isfinite(flow_cfm):
            raise ValueError("flow must be finite")
        points = self.points
        low_flow = points[0][0]
        high_flow = points[-1][0]
        tolerance = 1e-10 * max(1.0, high_flow)
        if flow_cfm < low_flow - tolerance or flow_cfm > high_flow + tolerance:
            raise ValueError(
                f"flow {flow_cfm:.6g} CFM is outside the supplied {self._curve_name} "
                f"({low_flow:.6g}–{high_flow:.6g} CFM); extrapolation is disabled"
            )
        flow_cfm = min(max(flow_cfm, low_flow), high_flow)
        # First segment whose right-hand flow is >= the query (same segment the
        # original linear scan selected), found by binary search.
        index = bisect_left(self._flows, flow_cfm, 1)
        if index >= len(points):
            return points[-1][1]
        q0, p0 = points[index - 1]
        q1, p1 = points[index]
        fraction = (flow_cfm - q0) / (q1 - q0)
        return p0 + fraction * (p1 - p0)


@dataclass(frozen=True)
class FanCurve(_PiecewiseLinearCurve):
    """A single fan's static-pressure curve at one fixed speed."""

    points: tuple[tuple[float, float], ...]
    source: str = "unspecified"
    _curve_name = "fan curve"

    @classmethod
    def from_csv(cls, path: str | Path) -> "FanCurve":
        points = _validate_points(
            _read_curve_csv(path), label=str(path), pressure_direction="decreasing"
        )
        return cls(points, source=str(path))

    @property
    def shutoff_pressure_mmh2o(self) -> float:
        return self.points[0][1]

    @property
    def free_air_flow_cfm(self) -> float:
        return self.points[-1][0]


def validate_curve(points: Iterable[tuple[float, float]], label: str = "fan curve") -> None:
    """Backward-compatible public fan-curve validator."""
    _validate_points(points, label=label, pressure_direction="decreasing")


@dataclass(frozen=True)
class SystemCurve(_PiecewiseLinearCurve):
    """Total-flow pressure-drop curve for the installed duct/heatsink path."""

    points: tuple[tuple[float, float], ...]
    source: str = "unspecified system curve"
    _curve_name = "system curve"

    @classmethod
    def from_csv(cls, path: str | Path) -> "SystemCurve":
        points = _validate_points(
            _read_curve_csv(path), label=str(path), pressure_direction="increasing"
        )
        return cls(points, source=str(path))


@dataclass(frozen=True)
class OperatingPoint:
    fan_count_parallel: int
    total_flow_cfm: float
    per_fan_flow_cfm: float
    fan_static_pressure_mmh2o: float
    system_pressure_drop_mmh2o: float
    system_resistance_k_mmh2o_per_cfm2: float | None
    heat_load_w: float
    ideal_bulk_air_temperature_rise_c: float
    air_density_kg_m3: float
    air_specific_heat_j_kg_k: float
    fan_curve_source: str
    system_curve_source: str
    system_model: str
    model: str = "identical parallel fans + system resistance curve"


def solve_operating_point(
    curve: FanCurve,
    fan_count: int,
    system_pressure_mmh2o: float | None = None,
    system_reference_flow_cfm: float | None = None,
    heat_load_w: float = 300.0,
    air_density_kg_m3: float = 1.204,
    air_specific_heat_j_kg_k: float = 1006.0,
    system_curve: SystemCurve | None = None,
) -> OperatingPoint:
    """Find the fan/system intersection using bisection, without extrapolation.

    Pass either ``system_curve`` or both quadratic reference values. For N
    identical fans in parallel, each fan supplies Q_total/N at the common
    static pressure rise across the complete system.
    """
    if not isinstance(fan_count, int) or isinstance(fan_count, bool) or fan_count < 1:
        raise ValueError("fan_count must be a positive integer")

    if system_curve is not None:
        if system_pressure_mmh2o is not None or system_reference_flow_cfm is not None:
            raise ValueError("provide a system_curve or quadratic reference values, not both")
        resistance_k = None
        system_model = "measured/digitized piecewise-linear system curve"
        system_source = system_curve.source
        upper_bound = min(fan_count * curve.free_air_flow_cfm, system_curve.max_flow_cfm)

        def system_pressure_at(flow: float) -> float:
            return system_curve.pressure_at(flow)
    else:
        if system_pressure_mmh2o is None or system_reference_flow_cfm is None:
            raise ValueError(
                "provide --system-curve or both --system-pressure-mmh2o and "
                "--system-reference-flow-cfm"
            )
        scalar_reference = {
            "system_pressure_mmh2o": system_pressure_mmh2o,
            "system_reference_flow_cfm": system_reference_flow_cfm,
        }
        for name, value in scalar_reference.items():
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if system_pressure_mmh2o <= 0 or system_reference_flow_cfm <= 0:
            raise ValueError("system reference pressure and flow must both be greater than 0")
        resistance_k = system_pressure_mmh2o / (system_reference_flow_cfm**2)
        system_model = "quadratic approximation fitted from one reference point"
        system_source = "user-supplied quadratic reference point"
        upper_bound = fan_count * curve.free_air_flow_cfm

        def system_pressure_at(flow: float) -> float:
            return resistance_k * flow**2

    scalar_inputs = {
        "heat_load_w": heat_load_w,
        "air_density_kg_m3": air_density_kg_m3,
        "air_specific_heat_j_kg_k": air_specific_heat_j_kg_k,
    }
    for name, value in scalar_inputs.items():
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")
    if heat_load_w < 0:
        raise ValueError("heat_load_w must be non-negative")
    if air_density_kg_m3 <= 0 or air_specific_heat_j_kg_k <= 0:
        raise ValueError("air density and specific heat must be greater than 0")

    def residual(total_flow_cfm: float) -> float:
        return curve.pressure_at(total_flow_cfm / fan_count) - system_pressure_at(total_flow_cfm)

    lower = 0.0
    upper = upper_bound
    f_lower = residual(lower)
    f_upper = residual(upper)
    if f_lower <= 0:
        raise RuntimeError("No positive-flow operating point: system pressure meets/exceeds fan shutoff pressure")
    if f_upper > 0:
        if system_curve is not None and system_curve.max_flow_cfm < fan_count * curve.free_air_flow_cfm:
            raise RuntimeError(
                f"No intersection within supplied system-curve range (0–{system_curve.max_flow_cfm:g} CFM); "
                "add higher-flow system measurements. Extrapolation is disabled."
            )
        raise RuntimeError("Could not bracket a fan/system operating point; check the curve data")
    if f_upper == 0:
        total_flow = upper
    else:
        for _ in range(120):
            midpoint = (lower + upper) / 2.0
            f_midpoint = residual(midpoint)
            if f_midpoint > 0:
                lower = midpoint
            else:
                upper = midpoint
            if upper - lower <= 1e-9 * max(1.0, upper):
                break
        total_flow = (lower + upper) / 2.0

    per_fan_flow = total_flow / fan_count
    fan_pressure = curve.pressure_at(per_fan_flow)
    system_pressure = system_pressure_at(total_flow)
    flow_m3_s = total_flow * 0.00047194745
    if flow_m3_s <= 0:
        raise RuntimeError("Solved operating point has zero flow")
    temperature_rise = heat_load_w / (air_density_kg_m3 * air_specific_heat_j_kg_k * flow_m3_s)

    return OperatingPoint(
        fan_count_parallel=fan_count,
        total_flow_cfm=total_flow,
        per_fan_flow_cfm=per_fan_flow,
        fan_static_pressure_mmh2o=fan_pressure,
        system_pressure_drop_mmh2o=system_pressure,
        system_resistance_k_mmh2o_per_cfm2=resistance_k,
        heat_load_w=heat_load_w,
        ideal_bulk_air_temperature_rise_c=temperature_rise,
        air_density_kg_m3=air_density_kg_m3,
        air_specific_heat_j_kg_k=air_specific_heat_j_kg_k,
        fan_curve_source=curve.source,
        system_curve_source=system_source,
        system_model=system_model,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Solve a parallel fan array against a quadratic or supplied system curve."
    )
    parser.add_argument("--curve", required=True, help="fan CSV: flow_cfm,static_pressure_mmh2o")
    parser.add_argument("--fan-count", type=int, default=1, help="number of identical parallel fans (default: 1)")
    parser.add_argument("--system-curve", help="CSV system curve: total flow_cfm,static_pressure_mmh2o")
    parser.add_argument("--system-pressure-mmh2o", type=float, help="quadratic system pressure at reference flow")
    parser.add_argument("--system-reference-flow-cfm", type=float, help="flow at which quadratic reference pressure applies")
    parser.add_argument("--heat-load-w", type=float, default=300.0, help="bulk-air heat load in watts (default: 300)")
    parser.add_argument("--air-density-kg-m3", type=float, default=1.204, help="default: 1.204")
    parser.add_argument("--air-cp-j-kg-k", type=float, default=1006.0, help="default: 1006")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        curve = FanCurve.from_csv(args.curve)
        if args.system_curve:
            if args.system_pressure_mmh2o is not None or args.system_reference_flow_cfm is not None:
                parser.error("--system-curve cannot be combined with quadratic reference arguments")
            system_curve = SystemCurve.from_csv(args.system_curve)
            result = solve_operating_point(
                curve=curve, fan_count=args.fan_count, system_curve=system_curve,
                heat_load_w=args.heat_load_w, air_density_kg_m3=args.air_density_kg_m3,
                air_specific_heat_j_kg_k=args.air_cp_j_kg_k,
            )
        else:
            if args.system_pressure_mmh2o is None or args.system_reference_flow_cfm is None:
                parser.error("provide --system-curve or both quadratic reference arguments")
            result = solve_operating_point(
                curve=curve, fan_count=args.fan_count,
                system_pressure_mmh2o=args.system_pressure_mmh2o,
                system_reference_flow_cfm=args.system_reference_flow_cfm,
                heat_load_w=args.heat_load_w, air_density_kg_m3=args.air_density_kg_m3,
                air_specific_heat_j_kg_k=args.air_cp_j_kg_k,
            )
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))

    if args.json:
        print(json.dumps(asdict(result), indent=2))
    else:
        print("MI50 fan/system operating-point estimate")
        print(f"  Fan curve:                 {result.fan_curve_source}")
        print(f"  Identical parallel fans:   {result.fan_count_parallel}")
        print(f"  Total flow:                {result.total_flow_cfm:.2f} CFM")
        print(f"  Flow per fan:              {result.per_fan_flow_cfm:.2f} CFM")
        print(f"  Fan static pressure:       {result.fan_static_pressure_mmh2o:.3f} mmH2O")
        print(f"  System pressure drop:      {result.system_pressure_drop_mmh2o:.3f} mmH2O")
        print(f"  System model:              {result.system_model}")
        if result.system_resistance_k_mmh2o_per_cfm2 is None:
            print("  System K:                  not fitted (tabulated curve)")
        else:
            print(f"  System K:                  {result.system_resistance_k_mmh2o_per_cfm2:.6g} mmH2O/CFM^2")
        print(f"  Heat load:                 {result.heat_load_w:.1f} W")
        print(f"  Ideal bulk-air rise:       {result.ideal_bulk_air_temperature_rise_c:.2f} °C")
        print("  NOTE: reduced-order screening estimate; not CFD or a GPU temperature prediction.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
