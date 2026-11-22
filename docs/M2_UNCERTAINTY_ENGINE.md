# M2 v1 uncertainty propagation engine

_Status: first implementation overlay prepared; integration validation and CI remain pending._

## Purpose

`analysis/operating_point_uncertainty.py` is an opt-in Monte Carlo path for tabulated fan/system curves. It calls the existing deterministic curve validator and operating-point solver. It does not alter `analysis/fan_operating_point.py`, its public API, or its CLI.

The implementation follows the accepted [M1 specification](UNCERTAINTY_MODEL_SPEC.md) and structural [sidecar JSON Schema](../schemas/curve-uncertainty-v1.schema.json). Runtime validation enforces additional semantic checks: row counts and anchors, exact curve hashes, sampled-coordinate coverage, units/effects, zero-mean corrections, cross-sidecar source identity, and measurement/operating-condition agreement.

## Sidecar paths and requirements

For a curve `data/example.csv`, use a sibling `data/example.uncertainty.json`. Its `central_values.path` is repository-relative and its `sha256` is over the exact CSV bytes. Fan and system sidecars must both be supplied. A missing sidecar does not mean zero uncertainty.

Every coordinate is `sampled`, `fixed_by_definition`, or `held_fixed_assumption`. Sampled coordinates require a non-zero target coefficient and a supported distribution. Held-fixed coordinates require a reason; runs containing them refuse by default and require `--allow-held-fixed`. Such reports are explicitly marked incomplete and list the omissions.

The engine supports normal, Student-t, uniform, and triangular zero-mean corrections. Shared source IDs are drawn once per attempted trial and merged across the fan/system sidecars. Distinct source IDs are independent only under the declared v1 assumption. Non-empty `known_dependencies` is rejected.

## CLI

Run from the repository root using:

```bash
python3 -m analysis.operating_point_uncertainty \
  --fan-curve <fan-curve.csv> \
  --system-curve <tabulated-system-curve.csv> \
  --fan-sidecar <fan-curve.uncertainty.json> \
  --system-sidecar <system-curve.uncertainty.json> \
  --repo-root . \
  --fan-count <integer> \
  --fan-model <model-id> \
  --configuration-id <test-configuration-id> \
  --rpm <measured-fixed-rpm> \
  --voltage-v <fixed-voltage> \
  --pwm-percent <fixed-pwm> \
  --trials 100000 \
  --seed 20261121 \
  --coverage-probability 0.95 \
  --output <report.json>
```

`--minimum-valid-fraction` optionally supplies an explicit yield threshold. The engine has no hidden default threshold. `--allow-held-fixed` is required when the sidecars declare any uncertainty coordinates held fixed.

The requested trial count is the attempted count, not a target number of successful roots. Every unique source is drawn once per attempt, even when another source's draw is invalid; this keeps the random stream and attempt semantics reproducible. `outcome_counts` accounts for every attempt, including `valid_root`; failures are also retained separately by category. Fewer than two valid roots are always inconclusive because sample standard uncertainty and covariance cannot be estimated. If an explicit minimum valid fraction is not met, the run is also inconclusive and output intervals are suppressed. No extrapolation or curve repair is performed.

## Report

The JSON report records:

- curve and sidecar SHA-256 hashes;
- deterministic solver and uncertainty-engine source hashes;
- sidecar schema version, Python runtime, RNG, seed, and trial count;
- source definitions, original uncertainty statements, conversion notes, target mappings, measurement basis, operating conditions, and any held-fixed omissions;
- valid/failed counts, valid fraction, failure categories, and optional yield-threshold result;
- marginal output means, sample standard uncertainties, medians, extrema, and central empirical intervals using Hyndman-Fan type 7;
- covariance and correlation matrices computed from the same valid joint output vectors.

Intervals are marginal and conditional on the declared PDFs, dependence assumptions, physically valid sampled curves, and existence of an in-range root. They are not confidence intervals, not simultaneous joint coverage regions, and not physical validation of the hardware.

## Verification coverage

The 30 new tests use generated synthetic curves and synthetic sidecars. They cover CSV hash binding, schema-version and unknown-field rejection, duplicate JSON keys, source sharing across curves, conflicting source definitions, unsupported dependence, explicit held-fixed opt-in, coordinate/anchor validation, measurement and operating-condition compatibility, supported distributions, seeded reproducibility, full source-draw accounting for invalid attempts, exact attempted-trial accounting, insufficient-valid-sample handling, invalid curve/effect reporting, no-extrapolation/root-range behavior, zero-uncertainty recovery, marginal quantiles, and joint covariance/correlation.

No real MI50 uncertainty result can be produced from the current repository: the P9 curve is approximate manual digitization without defensible quantified uncertainty, and the MI50 system curve remains a header-only template. Use these synthetic tests for software verification only.
