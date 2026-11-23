#!/usr/bin/env python3
"""Bounded RPM-based electrical interpolation for fan telemetry tables.

Each supply-voltage table is treated independently. Current and power are
interpolated separately against RPM; published power is never recomputed from
voltage and current. Extrapolation and voltage interpolation are disabled.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ELECTRICAL_COLUMNS = (
    "source_table_row",
    "pwm_percent",
    "supply_voltage_v",
    "fan_speed_rpm",
    "current_a",
    "power_w",
)


def _parse_integer(value: str | None, *, field: str, row: int) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"row {row}: {field} must be an integer") from exc
    return parsed


def _parse_finite(value: str | None, *, field: str, row: int) -> float:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"row {row}: {field} must be numeric") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"row {row}: {field} must be finite")
    return parsed


def _lerp(left: float, right: float, fraction: float) -> float:
    return left + (right - left) * fraction


@dataclass(frozen=True)
class ElectricalRPMPoint:
    """One unique RPM coordinate, retaining all agreeing source rows."""

    fan_speed_rpm: float
    current_a: float
    power_w: float
    pwm_percent: tuple[int, ...]
    source_table_rows: tuple[int, ...]


@dataclass(frozen=True)
class FanElectricalCurve:
    """Electrical telemetry for one exact supply voltage."""

    supply_voltage_v: float
    points: tuple[ElectricalRPMPoint, ...]
    source: str

    @property
    def rpm_range(self) -> tuple[float, float]:
        return self.points[0].fan_speed_rpm, self.points[-1].fan_speed_rpm

    def interpolate(self, target_rpm: float) -> dict[str, Any]:
        """Interpolate current and power independently, without extrapolation."""
        if isinstance(target_rpm, bool) or not isinstance(target_rpm, (int, float)):
            raise ValueError("target_rpm must be a finite non-negative number")
        target = float(target_rpm)
        if not math.isfinite(target) or target < 0.0:
            raise ValueError("target_rpm must be a finite non-negative number")

        low, high = self.rpm_range
        if target < low or target > high:
            raise ValueError(
                f"RPM {target:g} is outside the {self.supply_voltage_v:g} V measured range "
                f"({low:g}–{high:g} RPM); extrapolation is disabled"
            )

        for point in self.points:
            if target == point.fan_speed_rpm:
                return {
                    "requested_rpm": target,
                    "method": "source_observation",
                    "lower_rpm": point.fan_speed_rpm,
                    "upper_rpm": point.fan_speed_rpm,
                    "lower_pwm_percent": list(point.pwm_percent),
                    "upper_pwm_percent": list(point.pwm_percent),
                    "source_table_rows": list(point.source_table_rows),
                    "current_a": point.current_a,
                    "power_w": point.power_w,
                }

        for left, right in zip(self.points, self.points[1:]):
            if left.fan_speed_rpm < target < right.fan_speed_rpm:
                fraction = (target - left.fan_speed_rpm) / (
                    right.fan_speed_rpm - left.fan_speed_rpm
                )
                return {
                    "requested_rpm": target,
                    "method": "linear_interpolation_in_rpm",
                    "lower_rpm": left.fan_speed_rpm,
                    "upper_rpm": right.fan_speed_rpm,
                    "lower_pwm_percent": list(left.pwm_percent),
                    "upper_pwm_percent": list(right.pwm_percent),
                    "source_table_rows": {
                        "lower": list(left.source_table_rows),
                        "upper": list(right.source_table_rows),
                    },
                    "current_a": _lerp(left.current_a, right.current_a, fraction),
                    "power_w": _lerp(left.power_w, right.power_w, fraction),
                }

        # Every in-range coordinate is either an exact point or in a segment.
        raise RuntimeError("could not locate RPM inside the measured interpolation range")


@dataclass(frozen=True)
class FanElectricalDataset:
    """Validated voltage-indexed dataset and byte-level source provenance."""

    curves: dict[float, FanElectricalCurve]
    source_path: str
    source_sha256: str
    record_count: int


def load_fan_electrical_dataset(path: str | Path) -> FanElectricalDataset:
    """Load a source-oriented electrical CSV without modifying its contents.

    Repeated RPM values are consolidated only when current and power agree
    exactly. Conflicting telemetry at one RPM is ambiguous for RPM interpolation
    and is rejected rather than averaged or silently selected.
    """
    csv_path = Path(path)
    raw = csv_path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{csv_path}: CSV must be UTF-8 text") from exc

    reader = csv.DictReader(io.StringIO(text, newline=""))
    if tuple(reader.fieldnames or ()) != ELECTRICAL_COLUMNS:
        raise ValueError(
            f"{csv_path}: expected columns in this exact order: "
            + ",".join(ELECTRICAL_COLUMNS)
        )

    grouped: dict[float, list[dict[str, Any]]] = {}
    seen_keys: set[tuple[float, int]] = set()
    for csv_row, row in enumerate(reader, start=2):
        if None in row or any(value is None for value in row.values()):
            raise ValueError(
                f"{csv_path}: row {csv_row} must contain exactly "
                f"{len(ELECTRICAL_COLUMNS)} fields"
            )
        table_row = _parse_integer(row["source_table_row"], field="source_table_row", row=csv_row)
        pwm = _parse_integer(row["pwm_percent"], field="pwm_percent", row=csv_row)
        voltage = _parse_finite(row["supply_voltage_v"], field="supply_voltage_v", row=csv_row)
        rpm = _parse_finite(row["fan_speed_rpm"], field="fan_speed_rpm", row=csv_row)
        current = _parse_finite(row["current_a"], field="current_a", row=csv_row)
        power = _parse_finite(row["power_w"], field="power_w", row=csv_row)

        if table_row < 1:
            raise ValueError(f"row {csv_row}: source_table_row must be positive")
        if not 0 <= pwm <= 100:
            raise ValueError(f"row {csv_row}: pwm_percent must be from 0 through 100")
        if voltage <= 0.0:
            raise ValueError(f"row {csv_row}: supply_voltage_v must be positive")
        if not rpm.is_integer() or rpm < 0.0:
            raise ValueError(f"row {csv_row}: fan_speed_rpm must be a non-negative integer")
        if current < 0.0 or power < 0.0:
            raise ValueError(f"row {csv_row}: current_a and power_w must be non-negative")

        key = (voltage, pwm)
        if key in seen_keys:
            raise ValueError(
                f"row {csv_row}: duplicate PWM {pwm}% at {voltage:g} V"
            )
        seen_keys.add(key)
        grouped.setdefault(voltage, []).append({
            "table_row": table_row,
            "pwm": pwm,
            "rpm": rpm,
            "current": current,
            "power": power,
        })

    if not grouped:
        raise ValueError(f"{csv_path}: no electrical observations found")

    curves: dict[float, FanElectricalCurve] = {}
    for voltage, records in grouped.items():
        source_rows = [record["table_row"] for record in records]
        if source_rows != list(range(1, len(records) + 1)):
            raise ValueError(
                f"{csv_path}: {voltage:g} V source_table_row must run consecutively from 1"
            )
        pwm_values = [record["pwm"] for record in records]
        if pwm_values != sorted(pwm_values):
            raise ValueError(f"{csv_path}: {voltage:g} V PWM rows must retain source order")

        by_rpm: dict[float, list[dict[str, Any]]] = {}
        for record in records:
            by_rpm.setdefault(record["rpm"], []).append(record)

        points: list[ElectricalRPMPoint] = []
        for rpm in sorted(by_rpm):
            duplicates = by_rpm[rpm]
            telemetry = {(item["current"], item["power"]) for item in duplicates}
            if len(telemetry) != 1:
                raise ValueError(
                    f"{csv_path}: conflicting current/power observations at "
                    f"{voltage:g} V and {rpm:g} RPM; RPM is not a unique interpolation coordinate"
                )
            current, power = next(iter(telemetry))
            points.append(ElectricalRPMPoint(
                fan_speed_rpm=rpm,
                current_a=current,
                power_w=power,
                pwm_percent=tuple(item["pwm"] for item in duplicates),
                source_table_rows=tuple(item["table_row"] for item in duplicates),
            ))

        if len(points) < 2:
            raise ValueError(f"{voltage:g} V table needs at least two unique RPM observations")
        curves[voltage] = FanElectricalCurve(
            supply_voltage_v=voltage,
            points=tuple(points),
            source=str(csv_path),
        )

    return FanElectricalDataset(
        curves=curves,
        source_path=str(csv_path),
        source_sha256=hashlib.sha256(raw).hexdigest(),
        record_count=sum(len(records) for records in grouped.values()),
    )


def estimate_fan_electrical(
    dataset: FanElectricalDataset,
    supply_voltage_v: float,
    target_rpm: float,
    fan_count: int = 1,
) -> dict[str, Any]:
    """Estimate per-fan and parallel-array electrical telemetry at fixed voltage."""
    if isinstance(fan_count, bool) or not isinstance(fan_count, int) or fan_count < 1:
        raise ValueError("fan_count must be a positive integer")
    if isinstance(supply_voltage_v, bool) or not isinstance(supply_voltage_v, (int, float)):
        raise ValueError("supply_voltage_v must exactly match a source voltage table")
    voltage = float(supply_voltage_v)
    if not math.isfinite(voltage) or voltage not in dataset.curves:
        supported = ", ".join(f"{item:g}" for item in sorted(dataset.curves))
        raise ValueError(
            f"no exact {voltage:g} V source table; voltage interpolation is disabled "
            f"(available: {supported} V)"
        )

    curve = dataset.curves[voltage]
    estimate = curve.interpolate(target_rpm)
    current = estimate["current_a"]
    power = estimate["power_w"]
    return {
        "source": {
            "path": dataset.source_path,
            "sha256": dataset.source_sha256,
            "record_count": dataset.record_count,
        },
        "supply_voltage_v": voltage,
        "target_rpm": float(target_rpm),
        "fan_count_parallel": fan_count,
        "interpolation": estimate,
        "per_fan": {"current_a": current, "power_w": power},
        "parallel_array_estimate": {
            "current_a": current * fan_count,
            "power_w": power * fan_count,
        },
        "array_assumption": (
            "identical fans connected in parallel to the same supply voltage, "
            "with each fan operating at the requested RPM"
        ),
        "limitations": [
            "current and power are interpolated independently from the published rounded values",
            "power is not recomputed from voltage multiplied by current",
            "only exact source supply voltages are supported; voltage interpolation is disabled",
            "RPM extrapolation is disabled",
            "array totals are estimates under the identical-fan, parallel-wiring assumption",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Estimate fan current and power by bounded RPM interpolation at an exact source voltage."
    )
    parser.add_argument("--measurement-csv", required=True, help="source electrical PWM CSV")
    parser.add_argument("--voltage-v", required=True, type=float, help="exact source voltage (no voltage interpolation)")
    parser.add_argument("--rpm", required=True, type=float, help="target fan speed in RPM")
    parser.add_argument("--fan-count", type=int, default=1, help="identical parallel fans (default: 1)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        dataset = load_fan_electrical_dataset(args.measurement_csv)
        result = estimate_fan_electrical(
            dataset,
            args.voltage_v,
            args.rpm,
            args.fan_count,
        )
    except (OSError, ValueError, RuntimeError, ArithmeticError) as exc:
        parser.error(str(exc))

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    else:
        interpolation = result["interpolation"]
        print("Fan electrical estimate")
        print(f"  Source voltage:       {result['supply_voltage_v']:.2f} V")
        print(f"  Requested speed:      {result['target_rpm']:.2f} RPM")
        print(f"  Interpolation:        {interpolation['method']}")
        print(f"  Per-fan current:      {result['per_fan']['current_a']:.5f} A")
        print(f"  Per-fan power:        {result['per_fan']['power_w']:.5f} W")
        print(f"  Parallel fan count:   {result['fan_count_parallel']}")
        print(f"  Array current:        {result['parallel_array_estimate']['current_a']:.5f} A")
        print(f"  Array power:          {result['parallel_array_estimate']['power_w']:.5f} W")
        print("  NOTE: interpolation estimate, not a direct measurement at the requested RPM.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
