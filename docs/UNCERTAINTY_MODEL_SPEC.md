# MI50 fan/system uncertainty model specification

_Status: M1 v1.0 accepted by the project owner on 2026-11-21. This is the approved design baseline for M2 v1; it does not constitute physical validation of the current fan or MI50 cooling data._

_Last updated: 2026-11-21_

## 1. Purpose, measurand, and scope

Define a traceable uncertainty model for the existing fan/system operating-point solver. The primary measurand is the steady-state total volumetric flow at the intersection of a single-fan pressure/flow curve and a system pressure-drop curve for the existing identical-fans-in-parallel model:

\[
g(Q,\mathbf{x}) = \Delta p_{\mathrm{fan}}(Q/N,\mathbf{x}_{\mathrm{fan}})
                 - \Delta p_{\mathrm{system}}(Q,\mathbf{x}_{\mathrm{system}}) = 0.
\]

`Q` is total flow, `N` is the fixed integer number of identical parallel fans, and `x` contains uncertain curve coordinates and documented shared effects. Derived outputs are total flow, per-fan flow, common static pressure, and ideal bulk-air temperature rise. The temperature rise is an air-stream energy balance, not a GPU junction, HBM, VRM, or heatsink temperature prediction.

M2 v1 is limited to:

- tabulated fan and system curves;
- fixed fan count and documented fan model, configuration, RPM, voltage, and PWM;
- fixed heat load, air density, and specific heat;
- existing piecewise-linear interpolation, physical curve validation, bisection, and no-extrapolation behavior;
- an opt-in Monte Carlo path separate from the deterministic API and CLI.

Probabilistic RPM scaling and the one-point quadratic system-resistance model are out of scope for M2 v1. The central-value CSV format remains unchanged.

## 2. Accepted v1 design decisions

The project owner accepted the following v1 recommendations by instructing the work to proceed without requesting amendments:

| Topic | Accepted decision | Consequence |
|---|---|---|
| Physical curve validity | Conditional rejection sampling | Reject invalid sampled curves; do not sort, clip, isotonic-regress, or otherwise repair them |
| Trial budget | Fixed attempted-trial count | Every requested trial is attempted once; no hidden retries to accumulate successful roots |
| Shared effects | One latent draw per source ID | Reuse the same draw at every target, including targets in both curve sidecars |
| Distinct sources | Explicit independence assumption | Distinct source IDs are independent only under the declared v1 assumption |
| Unsupported dependence | Fail closed | Known cross-source dependence not represented by a shared source ID stops the run |
| Initial distributions | Normal, Student-t, uniform, triangular | Empirical resampling and other families are deferred |
| Hard bounds | Not probability distributions | A hard-bound-only coordinate cannot be sampled without a justified PDF |
| Endpoints | Exact model anchors remain exact | Uncertain inferred coordinates, especially free-air flow, remain uncertain |
| M2 inputs | Tabulated curves, fixed operating conditions | No uncertain RPM, fan-count, thermal constants, or quadratic reference inputs in v1 |
| Outputs | Joint trial vectors | Report marginal intervals and covariance/correlation from the same accepted trial population |

These decisions are the M1 implementation baseline. Any change to them requires a separately documented, versioned specification change before implementation changes.

## 3. Metrology vocabulary

Uncertainty evaluation method, uncertainty metric, and probability distribution are separate concepts.

| Term | Interpretation and required record |
|---|---|
| Standard uncertainty, `u` | Standard-deviation measure associated with an input estimate. Record its derivation and PDF interpretation. |
| Expanded uncertainty, `U` | `U = k u_c`, with coverage factor `k`, coverage probability/basis, and degrees of freedom where applicable. Do not turn `U` into a PDF without justified assumptions. |
| Type A evaluation | Evaluation using statistical analysis of observations. Retain observations or sufficient summary statistics, sample count, estimator, repeatability conditions, and relevant degrees of freedom. |
| Type B evaluation | Evaluation using other information such as calibration certificates, specifications, resolution, or prior data. Retain the source and rationale for the assigned PDF. |
| Accuracy limit / tolerance | A permissible bound, not automatically a standard uncertainty or PDF. Keep as a hard bound unless a distribution is justified independently. |
| Repeatability | Variation under stated repeatability conditions. Distinguish one reading from the mean of `n` readings. |
| Digitization uncertainty | Local line-picking uncertainty and shared axis calibration/scale uncertainty are distinct sources. |
| Coverage interval | An interval intended to contain the measurand with a stated probability, conditional on the model and available information. It is not a confidence interval. |

A normal distribution is not inferred merely because a document uses `±`. A coverage factor such as `k = 2` does not automatically guarantee 95% coverage. Known significant bias is corrected in the central value with its correction and uncertainty documented; it is not hidden as an unexplained non-zero-mean residual source.

## 4. Input provenance and measurement compatibility

Each central-value CSV keeps the existing columns:

```csv
flow_cfm,static_pressure_mmh2o
```

Each curve receives a sibling JSON sidecar named `<curve-stem>.uncertainty.json`. The sidecar is linked to the exact central-value file by SHA-256 over the exact CSV bytes. `central_values.path` is repository-relative and must resolve to the curve passed to the run.

Sidecars record:

- provenance classification, description, and source record;
- flow basis (`actual_volumetric_flow` or `standard_volumetric_flow`) and reference/measurement temperature, absolute pressure, and relative humidity;
- pressure basis (`static_pressure` for v1), pressure reference/measurement planes, and velocity-pressure correction description;
- fan model, fan count, configuration ID, RPM, voltage, and PWM;
- explicit source definitions and coordinate coverage.

The fan and system sidecars must agree exactly on measurement-basis and operating-condition metadata. A static-pressure fan curve must not be compared with a different pressure basis without an explicit model conversion. The selected static-pressure reference and velocity-pressure treatment must be compatible across the two curves.

The current ARCTIC P9 Max 4300 RPM curve is an approximate manual chart digitization. Its source image, axis calibration, line-picking procedure, and defensible error bounds are not present in the repository. It has no quantified probabilistic uncertainty. The MI50 system-curve template is header-only; no measured MI50 system curve currently exists. Therefore, the current repository inputs do not support a real MI50 uncertainty result. Synthetic curves are for software verification only.

## 5. Sidecar v1 data contract

The structural JSON Schema is [`../schemas/curve-uncertainty-v1.schema.json`](../schemas/curve-uncertainty-v1.schema.json). Runtime validation additionally enforces cross-field and repository-specific rules that JSON Schema cannot express by itself. Unknown fields and schema versions are rejected rather than ignored.

Required top-level fields:

- `schema_version`: exactly `1.0`;
- `curve_type`: `fan` or `system`;
- `central_values`: repository-relative path and lowercase SHA-256;
- `provenance`: classification, description, and source record;
- `measurement_basis`: flow basis/reference conditions and static-pressure reference/correction;
- `operating_condition`: configuration ID, fan model/count, RPM, voltage, and PWM;
- `distinct_source_ids_independent`: explicitly `true`;
- `known_dependencies`: empty array for v1; a known unsupported dependency rejects the run;
- `coordinate_coverage`: one ordered entry for every CSV data row;
- `uncertainty_sources`: source definitions and their target mappings.

### 5.1 Coordinate coverage and anchors

Every flow and pressure coordinate must have exactly one state:

- `sampled`: at least one uncertainty-source target must affect it;
- `fixed_by_definition`: allowed only for model anchors;
- `held_fixed_assumption`: uncertainty is intentionally omitted and a non-empty reason is required.

The anchors are: fan first-row flow equals zero; fan last-row pressure equals zero; system first-row flow and pressure equal zero. The fan shutoff pressure and free-air flow coordinate are not exact merely because the endpoints are anchored. Uncertain free-air flow must be represented as a sampled coordinate.

A probabilistic run refuses any `held_fixed_assumption` coordinate unless the caller explicitly enables `--allow-held-fixed`. Such a run is reported as having omitted uncertainty and is not described as a complete uncertainty result. Hard-bound-only coordinates are not sampleable in v1; they must remain visibly held fixed under an explicit exclusion or the run must stop.

### 5.2 Source identity, units, and target effects

Each source has a unique stable `id` containing only letters, digits, `.`, `_`, `:`, and `-`, `evaluation_method`, `source_record`, `original_statement`, `conversion_notes`, `units`, `distribution`, and one or more `targets`. `original_statement` preserves the source's original uncertainty wording/value; `conversion_notes` records how it was mapped to the normalized PDF. A source ID denotes one scalar latent random variable, sampled once per attempted trial and reused at all its targets.

- Repeated source IDs across the fan and system sidecars represent one shared draw. Their evaluation method, source record, units, and distribution must match exactly; their target lists are combined.
- Independent point-local residuals use distinct source IDs.
- Distinct IDs are independent only under the explicit v1 declaration. `known_dependencies` must remain empty; known unsupported dependence stops the run.
- Arbitrary covariance matrices, copulas, and general joint PDFs are deferred.

A target specifies one-based CSV data-row indices (or `all`), quantity, effect, and a finite non-zero coefficient. Units are `CFM`, `mmH2O`, or `dimensionless` as applicable. Additive sources use the coordinate's units; relative-scale sources are dimensionless. For source draw `z`, coefficient `a`, and central coordinate `x0`:

- additive effect: `a z`;
- relative-scale effect: factor `1 + a z`.

For multiple sources on one coordinate, multiply all relative-scale factors and then add additive corrections:

\[
x_{\mathrm{sample}} = x_0\prod_j(1+a_j z_j)+\sum_k a_k z_k.
\]

A non-positive relative-scale factor invalidates that attempted realization. It is not reflected, made absolute, or clipped. A source ID used across different quantities must be dimensionless and used through compatible relative-scale effects.

### 5.3 Distribution definitions

The source variable is a zero-mean correction. Known bias belongs in the corrected central value. Supported families and parameterization:

| Family | Parameters | Required constraints |
|---|---|---|
| `normal` | `mean`, `standard_deviation` | mean exactly zero; finite positive standard deviation |
| `student_t` | `location`, `scale`, `degrees_of_freedom` | location zero; positive scale; degrees of freedom greater than 2 |
| `uniform` | `lower`, `upper` | ordered bounds and zero expected value |
| `triangular` | `lower`, `mode`, `upper` | ordered parameters and zero expected value |

For Student-t, `scale` is not the standard deviation. With `nu` degrees of freedom, variance is `scale² × nu/(nu-2)`. To parameterize a Student-t source with standard uncertainty `u`, use `scale = u × sqrt((nu-2)/nu)`.

The sidecar retains the original uncertainty statement and all conversions from `U`, `k`, coverage probability, sample statistics, resolution, or calibration limits to PDF parameters in `original_statement` and `conversion_notes`. `source_record` identifies the underlying calibration, repeatability, manufacturer, or digitization record. Empirical resampling, lognormal, and other families are deferred. A bounded tolerance is not automatically converted to a uniform PDF.

## 6. Physical curve constraints and sampling

Each sampled curve is passed through the existing deterministic point validator. It must satisfy:

- finite, non-negative coordinates;
- strictly increasing flow;
- non-increasing fan pressure and non-decreasing system pressure;
- the exact model endpoint conditions above;
- no extrapolation during the operating-point solve.

For every attempted trial:

1. Draw every unique source ID once in sorted ID order.
2. Apply that draw to every target, including targets on both curves.
3. Reject non-positive scale factors or non-finite effects.
4. Validate the sampled fan curve and system curve.
5. Solve using the existing operating-point solver without extrapolation.
6. Record exactly one categorized outcome.

Do not sort perturbed rows, clip values, apply isotonic regression, project values onto a monotone cone, or silently repair curves. Those operations alter the declared input distribution.

The result distribution is conditional on the declared input PDFs, source independence/shared-source model, physically valid sampled curves, and existence of a positive operating-point root inside both supplied curve domains. Rejection sampling changes the accepted input distribution; this conditional effect must be stated. A poor valid/root yield makes a run inconclusive rather than a reason for hidden retries. A monotone parameterization is deferred until its implied point marginals and covariance are derived and validated.

## 7. M2 v1 fixed-input policy

M2 v1 uses only a tabulated fan curve and tabulated system curve. Fan count, fan model, configuration ID, RPM, voltage, PWM, heat load, air density, and specific heat are fixed and recorded. Both sidecars must match the explicit run operating conditions and each other.

The quadratic system-reference model, probabilistic RPM variation, affinity-law scaling, and uncertainty in thermal constants are out of scope. A sidecar with an operating condition that does not match the run is rejected. A missing sidecar never means zero uncertainty.

## 8. Trial accounting and output reporting

The requested trial count is the number of attempted input realizations, including all failures. Do not retry invalid samples invisibly until enough roots succeed. Every attempt ends in one outcome:

- `invalid_source_effect`;
- `invalid_fan_curve`;
- `invalid_system_curve`;
- `no_positive_flow_root`;
- `system_curve_range_too_short`;
- `unbracketed_operating_point`;
- `fan_curve_range_failure`;
- `system_curve_range_failure`;
- `solver_failure`;
- `valid_root`.

The report includes exact curve and sidecar hashes; solver and engine source hashes; sidecar schema version; Python version and RNG; seed; attempted count; valid/failed counts and reasons; valid fraction; source definitions/targets; explicit omissions; fixed run inputs; and requested coverage probability/quantile method.

Retain the valid output vectors from the same trials for total flow, per-fan flow, common pressure, and ideal bulk-air temperature rise. Report marginal means, sample standard deviations where defined, medians, minima/maxima, and central empirical marginal coverage intervals. Also report covariance and correlation matrices from the same joint vectors. Marginal intervals are not a simultaneous joint coverage region. M2 uses the Hyndman-Fan type 7 sample quantile estimator. Do not call these coverage intervals confidence intervals or equate them automatically with `U = k u_c`.

A minimum valid-fraction threshold is optional and must be explicitly supplied; there is no hidden universal acceptance threshold. At least two valid roots are required to report sample standard uncertainties and output covariance; fewer than two makes the run `inconclusive` and suppresses all output summaries/intervals. If a supplied valid-fraction threshold is not met, the run is also `inconclusive` and contains no output interval. A result with held-fixed uncertainty is clearly marked incomplete.

The bulk-air temperature output is conditional on fixed heat load, density, and specific heat. It remains an ideal air-stream energy balance, not a component temperature.

## 9. M1 acceptance record

All recommendations below are accepted as the M1 v1 design baseline on 2026-11-21:

- [x] Metrology vocabulary and separation of evaluation method, uncertainty metric, and PDF.
- [x] v1 scope: tabulated curves and fixed operating/thermal inputs.
- [x] Sidecar location, exact central CSV SHA-256 binding, measurement-basis metadata, and strict versioning.
- [x] Source-ID and target semantics, including cross-sidecar shared sources.
- [x] Initial normal, Student-t, uniform, and triangular distributions and zero-mean correction convention.
- [x] Explicit distinct-source independence assumption and fail-closed unsupported-correlation behavior.
- [x] Conditional rejection sampling, exact endpoint treatment, and no-repair policy.
- [x] Fixed attempted-trial accounting and structured failure categories.
- [x] Marginal interval terminology and joint output/covariance reporting.
- [x] Explicit reporting of held-fixed/unquantified input uncertainty and the boundary between airflow and GPU temperatures.

M1 is complete. M2 implementation must follow this accepted specification and the structural schema; any change requires a versioned review.

## 10. References

- [JCGM 100:2008, Guide to the Expression of Uncertainty in Measurement](https://doi.org/10.59161/JCGM100-2008E) — uncertainty evaluation, Type A/Type B evaluations, covariance, expanded uncertainty, and degrees of freedom.
- [JCGM 100:2008/Amd.1:2026](https://doi.org/10.59161/PPDI3267) — amendment on nonlinearity in measurement models; relevant to the nonlinear operating-point model.
- [JCGM 101:2008, Propagation of distributions using a Monte Carlo method](https://doi.org/10.59161/JCGM101-2008) — Monte Carlo propagation for a scalar output quantity.
- [JCGM 102:2011, Extension to any number of output quantities](https://doi.org/10.59161/JCGM102-2011) — Monte Carlo propagation for multiple outputs and their joint distribution/covariance.
- [JCGM publications / GUM suite](https://www.bipm.org/en/committees/jc/jcgm/publications) — official publication listing.
- [VIM 2.36, coverage interval](https://jcgm.bipm.org/vim/en/2.36.html) — distinguishes a coverage interval from a confidence interval.
