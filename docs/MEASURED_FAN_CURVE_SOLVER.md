# Measured fan-curve operating-point analysis

_Status: initial isolated implementation for the Cybenetics NF-A14x25 G2 raw data. It is separate from the strict M2/M3 `FanCurve` model and does not alter the raw CSV._

## Purpose

`analysis/measured_fan_operating_point.py` analyzes pressure-flow tables whose measured pressure ordinates are not strictly non-increasing. It is designed for source data such as the Cybenetics NF-A14x25 G2 report, whose eight points per PWM setting include small local pressure increases and signed terminal readings.

The module does not import, modify, or weaken the validation contract of `analysis.fan_operating_point.FanCurve`. It only reuses the existing `SystemCurve` for tabulated system resistance. This separation is intentional: M2's accepted uncertainty specification rejects invalid sampled curves and prohibits repairing samples through sorting, clipping, smoothing, or isotonic projection.

## Command line

A hypothetical quadratic screening run across all nine measured PWM settings and one to three identical parallel fans:

```bash
python3 -m analysis.measured_fan_operating_point \
  --measurement-csv data/fan_curves/noctua_nf_a14x25_g2_cybenetics_25FN140A_raw.csv \
  --pwms 20,30,40,50,60,70,80,90,100 \
  --fan-counts 1,2,3 \
  --system-pressure-mmh2o 2.0 \
  --system-reference-flow-cfm 50 \
  --pressure-expanded-uncertainty-pa 0.6727 \
  --output results/g2_measured_operating_points_screening.json
```

The quadratic reference is hypothetical, not measured MI50 resistance. Once a measured system curve is available, use `--system-curve data/system_curves/<measured-file>.csv` instead. The tool does not apply affinity-law RPM scaling: each PWM setting is loaded from its own measured table, retaining the RPM recorded at each point.

## Data contract and validation

The loader requires the eight source columns already present in the G2 long-form CSV. It retains CSV row order, source row indices, point numbering, PWM, airflow, signed static pressure, point-level RPM, current, and power.

- Source row indices must be consecutive and in file order.
- Each PWM group must have consecutive point indices and at least two observations.
- Flow must be finite, non-negative, and strictly increasing within a PWM group because interpolation requires a unique flow coordinate.
- Pressure may be finite and signed; pressure monotonicity is deliberately not required.
- RPM must be finite and positive; current and power must be finite and non-negative.
- Interpolation is piecewise linear and never extrapolates beyond the measured fan-flow or supplied system-curve ranges.

The source CSV is read-only input. No normalized, smoothed, clipped, or fitted source file is written.

## Intersection algorithm

For `N` identical fans in parallel, each fan sees `Q_total/N`, while the system curve sees `Q_total`. The solver constructs the union of all relevant flow breakpoints from the scaled fan curve and (when supplied) the tabulated system curve.

For a tabulated system curve, both fan and system pressure are affine on each interval, so all interval roots are found exactly by linear interpolation. For the quadratic screening model, the fan segment is affine and the system model is quadratic; the resulting quadratic residual is solved analytically on each fan segment. A candidate root is accepted only when it lies inside the exact segment that generated that polynomial (within the configured floating-point flow tolerance). Roots of extrapolated segment lines are rejected, even when they happen to lie inside the overall curve domain. Valid positive roots are deduplicated at a scale-aware flow tolerance.

Scenario status is one of:

- `unique_intersection`: exactly one isolated positive mathematical root;
- `multiple_intersections`: more than one isolated positive mathematical root;
- `no_positive_intersection`: no isolated positive root in the common domain;
- `coincident_segment`: at least one interval has coincident fan and system curves, so the intersection is not isolated.

The solver does not silently choose one root when several are present. A coincident segment is reported separately from isolated roots. A short system curve truncates the common domain; it is never extrapolated.

## Interpretation and measurement uncertainty

A multiple-root result is a property of the piecewise-linear interpolation through the measured ordinates. It is not proof that a physical fan has several distinct stable operating states. Small local pressure reversals can introduce extra mathematical roots. An initial implementation defect accepted roots of each segment's quadratic outside the segment that generated it. That amounted to extrapolating each local line and produced spurious additional roots. The corrected implementation rejects those candidates. With the illustrative 2.0 mmH2O at 50 CFM quadratic, the 27 G2 PWM/fan-count combinations each have one segment-bounded mathematical intersection. This is a correction to the earlier result, not evidence that the hypothetical system resistance is representative of the MI50.

Cybenetics reports an expanded apparatus-level static-pressure uncertainty of ±0.6727 Pa with `k = 2`. Dividing by 9.80665 Pa per mmH2O gives approximately ±0.068596 mmH2O. The largest adjacent pressure increase in the nine detailed G2 tables is 0.04 mmAq, smaller than that expanded apparatus uncertainty. This comparison is provided as diagnostic context only. It does not assign the apparatus uncertainty independently to each point, establish a joint probability model, or authorize an M2 uncertainty sidecar.

The optional `--pressure-expanded-uncertainty-pa` argument explicitly supplies an apparatus-level source uncertainty for diagnostic comparison. For Cybenetics report 25FN140A, use `0.6727` Pa, which converts to approximately `0.068596` mmH2O. The report includes per-PWM maximum adjacent pressure increases and this comparison to make the caveat visible. It does not repair the measured curve or remove roots. Do not pass this value when analyzing a different source unless that source independently specifies the same uncertainty.

The report's airflow expanded-uncertainty equation is stated as valid only from 2.4 CFM upward; it is not applied to zero-flow measurements. No pointwise uncertainty distribution or covariance model is inferred by this solver.

## Electrical telemetry

At every isolated root, the solver linearly interpolates the point-level RPM, current, and power at the per-fan flow. Estimated array current and power are the interpolated per-fan values multiplied by fan count. These are explicitly labelled estimates under the identical-fan assumption; they are not separate measurements of a multi-fan installation.

## Boundaries

- This tool is deterministic exploratory analysis, not M2 uncertainty propagation and not the canonical M3 sensitivity engine.
- The raw G2 observations remain unchanged and are still not valid inputs to `FanCurve.from_csv()`.
- A hypothetical quadratic system reference does not characterize the MI50 heatsink, duct, or shroud.
- The result is not CFD, installed airflow validation, or a GPU/HBM/VRM temperature prediction.
- A future solver-compatible G2 curve needs a separately reviewed derivation and metrology treatment, with raw data retained alongside it.
