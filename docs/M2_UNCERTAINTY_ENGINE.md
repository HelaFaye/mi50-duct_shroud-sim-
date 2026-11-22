# M2 v1 uncertainty propagation engine

_Status: M2 v1 prototype committed and CI-verified. M2 v1.1 DKW quantile-precision refinement committed as [`0f8e869`](https://github.com/HelaFaye/mi50-duct_shroud-sim-/commit/0f8e86976c7053c84b72bf3a4dfdcdf408f52e28); local compilation and all 56 tests passed. GitHub Actions [run 44999641433](https://github.com/HelaFaye/mi50-duct_shroud-sim-/actions/runs/44999641433) passed on Python 3.10, 3.12, and 3.14._

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
  --quantile-precision-confidence 0.95 \
  --output <report.json>
```

`--minimum-valid-fraction` optionally supplies an explicit yield threshold. There is no hidden default. Without this option, the report records the valid fraction and leaves `minimum_valid_fraction_met` unset; it does not automatically classify a low yield as inconclusive. Supply a threshold when valid yield is an acceptance criterion. `--allow-held-fixed` is required when the sidecars declare any uncertainty coordinates held fixed.

The requested trial count is the attempted count, not a target number of successful roots. Every unique source is drawn once per attempt, even when another source's draw is invalid; this keeps the random stream and attempt semantics reproducible. `outcome_counts` accounts for every attempt, including `valid_root`; failures are also retained separately by category. Fewer than two valid roots are always inconclusive because sample standard uncertainty and covariance cannot be estimated. If an explicit minimum valid fraction is not met, the run is also inconclusive and output intervals are suppressed. No extrapolation or curve repair is performed.

The two-valid-root minimum is only a mathematical minimum for sample standard deviation and covariance. It is not a statistical precision criterion for empirical tail quantiles. The M2 v1.1 candidate adds a distribution-free DKW diagnostic for the Monte Carlo precision of both reported coverage endpoints. Its default 95% confidence is familywise across the four marginal output distributions; the DKW band is simultaneous over quantile probabilities within each marginal, with a Bonferroni union bound across the four marginals. The order-statistic inversion uses the left empirical inverse at p-epsilon for the lower limit and the right empirical inverse at p+epsilon for the upper limit: for n accepted samples, the finite lower rank is floor(n(p-epsilon)) (using rank 1 when the positive probability is below 1/n), and the finite upper rank is floor(n(p+epsilon))+1. These one-sided inverse conventions deliberately widen exact rank-boundary cases. If p-epsilon is non-positive, the lower confidence limit is unbounded; if p+epsilon is at least one, the upper confidence limit is unbounded. Such limits are serialized as null with an explicit unbounded flag; they must not be replaced by the observed sample minimum or maximum. The diagnostic uses only accepted valid-root vectors and therefore describes finite Monte Carlo sampling error conditional on the declared input model and acceptance process. It is not another predictive interval, does not quantify measurement uncertainty, and does not establish that the input PDFs are defensible. It does not impose an automatic pass/fail sample-size threshold: inspect the reported quantile bounds relative to the endpoint estimates and the engineering decision tolerance.

## Report

The JSON report records:

- curve and sidecar SHA-256 hashes;
- deterministic solver and uncertainty-engine source hashes;
- sidecar schema version, Python runtime, RNG, seed, and trial count;
- source definitions, original uncertainty statements, conversion notes, target mappings, measurement basis, operating conditions, and any held-fixed omissions;
- valid/failed counts, valid fraction, failure categories, and optional yield-threshold result;
- marginal output means, sample standard uncertainties, medians, extrema, and central empirical intervals using Hyndman-Fan type 7;
- DKW order-statistic confidence bounds for the Monte Carlo precision of each central-interval endpoint, with familywise confidence across all four marginal outputs;
- covariance and correlation matrices computed from the same valid joint output vectors.

The central empirical coverage intervals are marginal and conditional on the declared PDFs, dependence assumptions, physically valid sampled curves, and existence of an in-range root. They are not confidence intervals or simultaneous joint coverage regions. The separate DKW bounds are confidence bounds for the finite-sample Monte Carlo estimation of the population quantile locations only; they do not widen or replace the predictive coverage intervals. Neither report establishes physical validation of the hardware.

## Verification coverage

The 30 new tests use generated synthetic curves and synthetic sidecars. They cover CSV hash binding, schema-version and unknown-field rejection, duplicate JSON keys, source sharing across curves, conflicting source definitions, unsupported dependence, explicit held-fixed opt-in, coordinate/anchor validation, measurement and operating-condition compatibility, supported distributions, seeded reproducibility, full source-draw accounting for invalid attempts, exact attempted-trial accounting, insufficient-valid-sample handling, invalid curve/effect reporting, no-extrapolation/root-range behavior, zero-uncertainty recovery, marginal quantiles, and joint covariance/correlation.

The original 21 tests plus the 30 M2 v1 tests passed locally: 51/51 total. GitHub Actions run [44986689330](https://github.com/HelaFaye/mi50-duct_shroud-sim-/actions/runs/44986689330) passed compilation and the full unit-test step on Python 3.10, 3.12, and 3.14. Five M2 v1.1 DKW regression tests cover familywise epsilon, conservative order-statistic inversion, unbounded tail handling, report diagnostics, and confidence-parameter validation. The complete local suite passed: 21 original tests + 30 M2 v1 tests + 5 M2 v1.1 tests = 56/56. GitHub Actions run [44999641433](https://github.com/HelaFaye/mi50-duct_shroud-sim-/actions/runs/44999641433) for commit `0f8e86976c7053c84b72bf3a4dfdcdf408f52e28` passed both compilation and the full unit-test step on Python 3.10, 3.12, and 3.14.

No real MI50 uncertainty result can be produced from the current repository: the P9 curve is approximate manual digitization without defensible quantified uncertainty, and the MI50 system curve remains a header-only template. Use these synthetic tests for software verification only.
