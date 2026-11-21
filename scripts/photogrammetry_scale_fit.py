#!/usr/bin/env python3
"""Fit a uniform model-units-to-mm scale from independent 3D distances.

Input CSV columns:
  reference_id, model_distance, known_distance_mm, uncertainty_mm

This only fits a global scalar. It cannot fix perspective errors, lens distortion,
non-rigid reconstruction warping, bad point correspondence, or anisotropic scale.
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Constraint:
    reference_id: str
    model_distance: float
    known_distance_mm: float
    uncertainty_mm: float


def load_constraints(path: Path) -> list[Constraint]:
    rows: list[Constraint] = []
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            required = {"reference_id", "model_distance", "known_distance_mm", "uncertainty_mm"}
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"Missing CSV columns: {', '.join(sorted(missing))}")
            for line_no, row in enumerate(reader, start=2):
                if not any((value or "").strip() for value in row.values()):
                    continue
                try:
                    item = Constraint(
                        reference_id=(row.get("reference_id") or f"row-{line_no}").strip(),
                        model_distance=float(row["model_distance"]),
                        known_distance_mm=float(row["known_distance_mm"]),
                        uncertainty_mm=float(row["uncertainty_mm"]),
                    )
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"Invalid numeric value on CSV line {line_no}: {exc}") from exc
                if not all(math.isfinite(v) for v in (item.model_distance, item.known_distance_mm, item.uncertainty_mm)):
                    raise ValueError(f"Non-finite value on CSV line {line_no}")
                if item.model_distance <= 0 or item.known_distance_mm <= 0 or item.uncertainty_mm <= 0:
                    raise ValueError(f"Distances and uncertainty must be positive on CSV line {line_no}")
                rows.append(item)
    except OSError as exc:
        raise ValueError(f"Cannot read {path}: {exc}") from exc
    if len(rows) < 2:
        raise ValueError("At least two independent scale constraints are required; use more than one axis/plane where possible")
    return rows


def fit_scale(items: list[Constraint]) -> tuple[float, list[dict[str, float | str]], float, float]:
    """Return mm/model-unit scale, row residuals, weighted RMS mm, max abs % residual."""
    numerator = sum((item.model_distance * item.known_distance_mm) / (item.uncertainty_mm ** 2) for item in items)
    denominator = sum((item.model_distance ** 2) / (item.uncertainty_mm ** 2) for item in items)
    if denominator <= 0 or not math.isfinite(denominator):
        raise ValueError("Scale fit is singular")
    scale = numerator / denominator
    details: list[dict[str, float | str]] = []
    weighted_error_sum = 0.0
    total_weight = 0.0
    max_abs_percent = 0.0
    for item in items:
        predicted = scale * item.model_distance
        residual = predicted - item.known_distance_mm
        percent = 100.0 * residual / item.known_distance_mm
        weight = 1.0 / (item.uncertainty_mm ** 2)
        weighted_error_sum += weight * residual ** 2
        total_weight += weight
        max_abs_percent = max(max_abs_percent, abs(percent))
        details.append({
            "reference_id": item.reference_id,
            "predicted_mm": predicted,
            "known_mm": item.known_distance_mm,
            "residual_mm": residual,
            "residual_percent": percent,
        })
    weighted_rms = math.sqrt(weighted_error_sum / total_weight)
    return scale, details, weighted_rms, max_abs_percent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path, help="CSV of 3D model distances and independently known dimensions")
    parser.add_argument("--model-unit", default="model unit", help="Name of the model distance unit (default: 'model unit')")
    args = parser.parse_args(argv)
    try:
        constraints = load_constraints(args.csv_file)
        scale, details, weighted_rms, max_abs_percent = fit_scale(constraints)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Scale factor: {scale:.9g} mm per {args.model_unit}")
    print(f"Constraints: {len(constraints)}")
    print(f"Weighted RMS residual: {weighted_rms:.4f} mm")
    print(f"Maximum absolute residual: {max_abs_percent:.3f}%")
    print("\nPer-reference checks:")
    for detail in details:
        print(
            f"  {detail['reference_id']}: predicted {detail['predicted_mm']:.3f} mm, "
            f"known {detail['known_mm']:.3f} mm, residual {detail['residual_mm']:+.3f} mm "
            f"({detail['residual_percent']:+.3f}%)"
        )
    print("\nApply this as a uniform scale only after verifying the reference point correspondence.")
    print("Large or direction-dependent residuals indicate bad references or reconstruction distortion; do not hide them with separate X/Y/Z scaling.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
