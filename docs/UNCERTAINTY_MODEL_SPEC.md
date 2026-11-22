# MI50 fan/system uncertainty model specification

_Status: M1 review draft v0.2. Decisions below are engineering recommendations for owner acceptance; they are not yet approved implementation requirements. M2 remains blocked._

_Last updated: 2026-11-21_

## 1. Purpose, measurand, and scope

Define a traceable uncertainty model for the existing fan/system operating-point solver before adding stochastic computation. The primary measurand is the steady-state total volumetric flow at the intersection of a single-fan pressure/flow curve and a system pressure-drop curve for the existing identical-fans-in-parallel model:

\[
g(Q,\mathbf{x}) = \Delta p_{\mathrm{fan}}(Q/N,\mathbf{x}_{\mathrm{fan}})
                 - \Delta p_{\mathrm{system}}(Q,\mathbf{x}_{\mathrm{system}}) = 0.
\]

Here `Q` is total flow, `N` is the fixed integer number of identical parallel fans, and `x` contains uncertain curve coordinates and their documented shared effects. Derived outputs are total flow, per-fan flow, common pressure, and ideal bulk-air temperature rise. The temperature rise is an air-stream energy balance, not a GPU junction, HBM, VRM, or heatsink temperature prediction.

The proposed M2 v1 scope is deliberately narrow:

- uncertainty in tabulated fan and system curve coordinates only;
- fixed fan count and fixed, documented fan operating conditions;
- fixed heat load, air density, and specific heat for the derived bulk-air calculation;
- existing piecewise-linear interpolation, bisection, physical validation, and no-extrapolation behavior;
- no probabilistic RPM scaling and no uncertain quadratic system-reference model.

The deterministic API and CLI remain unchanged. A stochastic mode is a separate opt-in path. The sidecar format does not change the existing central-value CSV format.

## 2. M1 decision recommendations

The following are the recommended v1 decisions to accept or amend:

| Topic | Recommended v1 decision | Reason / limitation |
|---|---|---|
| Curve validity | Draw from the declared joint input model, then reject physically invalid curve realizations; do not repair them | Preserves the declared pre-constraint input model and makes conditioning visible |
| Trial budget | The requested trial count is the number of attempted input realizations, including failures; never retry invisibly until enough roots succeed | Makes valid fraction and selection conditioning auditable |
| Shared effects | One source ID represents one latent draw reused at every target; distinct source IDs are independent only under an explicit sidecar declaration | Captures common calibrations without silently inventing covariance |
| Unsupported dependence | Reject known correlations that v1 cannot represent | Independence must not be substituted for known dependence |
| Distribution families | Normal, Student-t, uniform, and triangular; defer empirical resampling | Covers common documented uncertainty models while keeping the first sampler testable |
| Hard bounds | Record as bounds, not PDFs; do not sample them without an evidence-based distribution | A tolerance is not automatically a probability distribution |
| Endpoints | Preserve model-defined anchors exactly; uncertainty in inferred endpoint coordinates remains explicit | Avoids post-sampling clamping and hidden distribution changes |
| M2 inputs | Tabulated curves only; fixed fan count, RPM, voltage/PWM, heat load, density, and heat capacity | Keeps v1 limited to the currently implemented solver model |
| Outputs | Retain one joint trial record for the output vector; report marginal coverage intervals and output covariance/correlation | Outputs share the same sampled inputs and are not independent |

These are proposals for owner review. Do not treat the table as approval to implement M2.

## 3. Metrology vocabulary

Uncertainty evaluation method, uncertainty metric, and probability distribution are separate concepts.

| Term | Required interpretation | Treatment in the data contract |
|---|---|---|
| Standard uncertainty, `u` | Standard-deviation measure associated with an input estimate | Store only when its derivation and PDF interpretation are documented; do not treat every `±` value as `u` |
| Expanded uncertainty, `U` | `U = k u_c`, with coverage factor `k` and a stated coverage basis | Preserve `U`, `k`, coverage probability/basis, and degrees of freedom; convert to a PDF only when justified |
| Type A evaluation | Evaluation using statistical analysis of observations | Record observations or summary statistics, sample count, estimator, repeatability conditions, and degrees of freedom where applicable |
| Type B evaluation | Evaluation using other information, such as calibration certificates, specifications, resolution, or prior data | Record the source, stated bound/specification, interpretation, and rationale for the assigned PDF |
| Accuracy limit / tolerance | A stated permissible bound, not automatically a standard uncertainty or PDF | Keep as a hard bound unless a justified PDF is explicitly assigned |
| Repeatability | Variation under stated repeatability conditions | State whether the uncertainty describes an individual reading or a mean of `n` readings; do not confuse sample standard deviation with standard uncertainty of the mean |
| Digitization uncertainty | Uncertainty from reading a plotted curve, including pixel location, line thickness, and axis calibration | Separate point-local line-picking uncertainty from shared axis calibration/scale uncertainty |
| Coverage interval | An interval intended to contain the measurand with a stated probability, conditional on the model and available information | Report as a coverage interval, not a confidence interval; state whether it is marginal or joint |

A normal distribution must not be inferred merely because an instrument specification uses `±`. A coverage factor such as `k = 2` must not be assumed to guarantee 95% coverage without a justified distribution and degrees-of-freedom basis. A known measurement bias is corrected in the central value (with the correction and its uncertainty documented); it is not hidden as an unexplained non-zero-mean residual source.

## 4. Input provenance and measurement compatibility

Each curve remains a central-value CSV with columns:

```csv
flow_cfm,static_pressure_mmh2o
```

Each curve uncertainty sidecar must be linked to the exact central-value file by SHA-256 of its exact bytes. The sidecar must also record:

- curve type (`fan` or `system`);
- source classification and description (manufacturer numeric data, calibrated measurement, chart digitization, estimate, or synthetic fixture);
- flow basis (actual or standard volumetric flow, including reference conditions when normalized);
- pressure basis (static or total pressure), pressure measurement/reference planes, and any velocity-pressure correction;
- pressure-column convention and the reference basis for `mmH2O` where material to the source;
- fan model, RPM, voltage/PWM, and test configuration for a fan curve;
- test rig, installation/configuration, and measurement-plane identity for a system curve;
- raw source-document/image reference and digitization or measurement procedure where applicable.

The fan and system curves may only be intersected when their flow and pressure definitions are compatible. A static-pressure fan curve must not be compared to a total-pressure system loss without an explicit, documented conversion. Inlet/outlet velocity-pressure terms and test measurement planes must not be silently ignored.

The ARCTIC P9 Max 4300 RPM curve currently in the repository is an approximate manual chart digitization. Its source image, axis calibration, line-picking procedure, and defensible uncertainty bounds are not present in the repository. It therefore has no quantified probabilistic uncertainty. Do not derive uncertainty from CSV decimal places or invent pixel tolerances.

The MI50 system-curve template is header-only. No measured MI50 system curve currently exists in the repository. A real MI50 uncertainty result cannot be produced until compatible fan/system inputs and their uncertainty evidence are supplied. Synthetic curves are suitable for software verification only.

## 5. Proposed sidecar contract (v1 proposal)

### 5.1 Location and identity

Use a sibling JSON file for each curve, named `<curve-stem>.uncertainty.json`. The sidecar contains:

- `schema_version`, proposed value `1.0` after acceptance;
- `curve_type`;
- `central_values.path`, relative to the repository root;
- `central_values.sha256`, over the exact CSV bytes;
- `provenance`, `measurement_basis`, and `operating_condition` metadata;
- an explicit `distinct_source_ids_independent: true` declaration for v1;
- `uncertainty_sources`, including source definitions and target mappings.

Unknown schema versions, extra unsupported semantics, malformed units, duplicate IDs, invalid row references, or CSV hash mismatches must fail closed. Do not silently ignore unknown fields that could change the probability model.

Every coordinate in the central-value CSV must also have an explicit coverage state in `coordinate_coverage`, with exactly one entry per data row and a state for both `flow_cfm` and `static_pressure_mmh2o`:

- `sampled`: one or more uncertainty-source targets must cover this coordinate;
- `fixed_by_definition`: allowed only for a solver/model anchor (fan first-row flow, fan last-row pressure, and system first-row flow and pressure);
- `held_fixed_assumption`: the coordinate has no propagated uncertainty by an explicit assumption, with a recorded reason. This makes omitted uncertainty visible in every report.

A sampled coordinate with no source target, a target attached to a non-sampled coordinate, an anchor marked `sampled`, or a non-anchor marked `fixed_by_definition` is a schema error. A hard-bound-only coordinate cannot be marked `sampled` unless a defensible PDF is assigned; it must be explicitly marked held-fixed (and the output is incomplete) or the probabilistic run must stop.

The following is an illustrative shape only. The values and source record are synthetic examples, not MI50 measurements or recommended uncertainty magnitudes. A real sidecar must include the complete `coordinate_coverage` array for every CSV row.

```json
{
  "schema_version": "1.0-proposal",
  "curve_type": "fan",
  "central_values": {
    "path": "data/fan_curves/example.csv",
    "sha256": "<sha256-of-exact-csv-bytes>"
  },
  "provenance": {
    "classification": "synthetic_test_fixture",
    "description": "SYNTHETIC EXAMPLE ONLY; not a measured fan curve"
  },
  "measurement_basis": {
    "flow_basis": "actual_volumetric_flow",
    "pressure_basis": "static",
    "pressure_reference": "synthetic test convention"
  },
  "operating_condition": {
    "fan_model": "synthetic fan",
    "rpm": 4300
  },
  "distinct_source_ids_independent": true,
  "coordinate_coverage": [
    {"row_index": 1, "flow_cfm": "fixed_by_definition", "static_pressure_mmh2o": "sampled"},
    {"row_index": 2, "flow_cfm": "sampled", "static_pressure_mmh2o": "sampled"},
    {"row_index": 3, "flow_cfm": "sampled", "static_pressure_mmh2o": "fixed_by_definition"}
  ],
  "uncertainty_sources": [
    {
      "id": "synthetic_shared_flow_scale",
      "evaluation_method": "type_b",
      "source_record": "SYNTHETIC EXAMPLE ONLY",
      "distribution": {
        "family": "normal",
        "parameters": {"mean": 0.0, "standard_deviation": 0.01}
      },
      "targets": [
        {"rows": [2, 3], "quantity": "flow_cfm", "effect": "relative_scale", "coefficient": 1.0}
      ]
    },
    {
      "id": "synthetic_point_pressure_reading_row1",
      "evaluation_method": "type_a",
      "source_record": "SYNTHETIC EXAMPLE ONLY; one independent point-local residual",
      "distribution": {
        "family": "normal",
        "parameters": {"mean": 0.0, "standard_deviation": 0.02}
      },
      "targets": [
        {"rows": [1], "quantity": "static_pressure_mmh2o", "effect": "additive", "coefficient": 1.0}
      ]
    },
    {
      "id": "synthetic_point_pressure_reading_row2",
      "evaluation_method": "type_a",
      "source_record": "SYNTHETIC EXAMPLE ONLY; independent of row 1",
      "distribution": {
        "family": "normal",
        "parameters": {"mean": 0.0, "standard_deviation": 0.02}
      },
      "targets": [
        {"rows": [2], "quantity": "static_pressure_mmh2o", "effect": "additive", "coefficient": 1.0}
      ]
    }
  ]
}
```

The `coordinate_coverage` entries in this abbreviated example are illustrative; real row counts and anchors must agree exactly with the validated CSV.

### 5.2 Source identity and target mapping

A source ID identifies one scalar latent random variable, not merely a reusable uncertainty category. The sampler draws it once per attempted trial and reuses that exact draw at every target listed by the source. Therefore:

- a shared calibration/axis effect is one source ID targeting multiple rows;
- independent point-local residuals use distinct source IDs, even when their distributions and provenance descriptions are otherwise identical;
- one source ID may target both flow and pressure to represent a documented common-mode effect, but this creates the dependence implied by that same latent draw;
- the same source ID may appear in the fan and system sidecars to model a shared instrument/calibration effect across both curves. The distribution, evaluation method, and source-record identity must match exactly across sidecars; targets are combined for that run;
- conflicting definitions for the same source ID are an error.

Each target identifies one or more one-based CSV data-row indices (header excluded), a quantity (`flow_cfm` or `static_pressure_mmh2o`), an effect (`additive` or `relative_scale`), and a finite coefficient. `rows: "all"` is allowed where every row is affected. Row indices must be unique and within the exact CSV row count. The target list and `coordinate_coverage` must agree exactly: every `sampled` coordinate has at least one target, and no `fixed_by_definition` or `held_fixed_assumption` coordinate may be targeted.

For source draw `z`, coefficient `a`, and central coordinate `x0`, the target contribution is:

- additive: `a*z`;
- relative scale: multiplicative factor `1 + a*z`.

When multiple sources target one coordinate, apply all relative-scale factors first and then sum additive corrections:

\[
x_{sample}=x_0\prod_j(1+a_j z_j)+\sum_k a_k z_k.
\]

For additive effects, `z` and the target quantity have compatible units and `a` is dimensionless. For relative-scale effects, `z` and `a` are dimensionless. Every relative-scale factor must be strictly positive. A non-positive factor makes that attempted realization invalid; do not reflect it, take its absolute value, or clip it.

The same source ID reused across different quantities must be dimensionless (for example, a common relative-scale source) unless the target quantities genuinely share compatible units. Known dependence between distinct source IDs is not supported by v1. If that dependence is material, v1 must reject the analysis rather than treat the sources as independent. Do not approximate a known covariance matrix by ad hoc shared sources unless the decomposition has a documented physical/statistical basis.

### 5.3 Distribution definitions

Each sampleable source defines a correction random variable whose expected value is zero. Any known bias is applied to the central value before this residual uncertainty is described.

The recommended initial families and parameters are:

| Family | Parameters | Constraints |
|---|---|---|
| `normal` | `mean`, `standard_deviation` | `mean = 0`; standard deviation finite and positive |
| `student_t` | `location`, `scale`, `degrees_of_freedom` | `location = 0`; scale positive; degrees of freedom greater than 2 for finite variance |
| `uniform` | `lower`, `upper` | `lower < upper`; expected value `(lower + upper)/2 = 0` |
| `triangular` | `lower`, `mode`, `upper` | `lower < upper`, `lower <= mode <= upper`; expected value `(lower + mode + upper)/3 = 0` |

For Student-t, `scale` is the distribution scale parameter, not its standard deviation. With `nu` degrees of freedom, its variance is `scale^2 * nu/(nu - 2)`. If a documented standard uncertainty `u` is used to parameterize this distribution, the corresponding scale is `u * sqrt((nu - 2)/nu)`.

The source record must preserve the original uncertainty statement and document all conversions from `U`, `k`, coverage probability, sample statistics, resolution, or calibration limits to the PDF parameters. Finite degrees of freedom must be retained where material. Empirical resampling is deferred until raw observations, dependence structure, and resampling method can be retained and specified. A positive-only family such as lognormal may be added later when the source evidence supports it; it must not be chosen merely to avoid invalid draws.

A hard-bound-only source is not sampleable. M2 must refuse a probabilistic run if a target has only a hard bound and no justified PDF, unless a later explicitly designed interval-analysis mode is used. An explicit exclusion/held-fixed assumption must be reported as omitted uncertainty; it must never be silent.

### 5.4 Dependence model

The v1 dependence rule is:

1. one source ID = one latent draw reused at every target for that ID;
2. distinct source IDs are independent only when every participating sidecar explicitly declares this v1 assumption;
3. any known material dependence between distinct IDs that cannot be represented by a shared latent source is unsupported and must stop the run;
4. all sidecars participating in one operating-point run are merged before drawing, so shared source IDs can produce cross-curve dependence.

V1 does not implement arbitrary covariance matrices, copulas, or general joint PDFs. A future schema may add these with positive-semidefinite validation and an explicit mapping from marginal distributions to the joint model.

## 6. Physical curve constraints and endpoint treatment

Every sampled curve must pass the same physical contract as the deterministic solver. Reuse the existing validator rather than implementing a second set of rules. In particular:

- flow coordinates are finite, non-negative, and strictly increasing;
- fan pressure is finite, non-negative, and non-increasing;
- system pressure drop is finite, non-negative, and non-decreasing;
- fan curve first flow coordinate remains zero, shutoff pressure is positive, and the free-air endpoint pressure remains zero;
- system curve starts at `(0 CFM, 0 mmH2O)` and ends at a positive pressure drop;
- the current validator tolerances remain the contract unless changed through a separately reviewed deterministic-solver change;
- no extrapolation is permitted during any trial.

The model-defined anchors are not random samples:

- fan first flow coordinate: exactly zero;
- system first flow and pressure: exactly `(0, 0)`;
- fan free-air endpoint pressure: exactly zero.

The fan shutoff pressure and free-air flow coordinate are not made exact merely because the curve has anchored endpoints. The free-air flow coordinate may carry uncertainty. A system pressure-zero calibration source may target non-origin rows while the physical zero origin remains anchored; its treatment must document how the zero reference was established. Do not perturb an anchor and subsequently clamp it back.

### 6.1 Selected v1 method: conditional rejection sampling

For each attempted trial:

1. draw every unique source ID once;
2. apply source effects to the linked fan and system curve coordinates;
3. reject the realization if any sampled coordinate is non-finite, negative, non-monotone, violates an endpoint constraint, or has a non-positive relative-scale factor;
4. if both curves pass, solve the operating point using the existing no-extrapolation solver;
5. record a structured failure if the root is not positive or cannot be bracketed inside the supplied curve domains.

Do not sort perturbed rows, clip values, apply isotonic regression, project values onto a monotone cone, or silently repair a curve. Those operations change the declared input distribution and can bias the output.

The output distribution is conditional on the declared joint input PDFs, physically valid sampled curves, and the existence of a positive operating-point root inside the supplied ranges. Rejection sampling does not preserve the unconditioned point marginals after the physical constraints are applied. That conditional effect is a model limitation and must be stated explicitly. If the physical-validity or root-validity yield is poor, the report is inconclusive rather than silently replacing failures with valid draws. A monotone parameterization is deferred; it may only replace rejection sampling after its implied point marginals and covariance have been derived and validated.

### 6.2 Trial and failure accounting

The requested trial count is the number of attempted input realizations. It is not the number of successful outputs. Do not retry rejected samples invisibly or run until a target number of successful roots is accumulated.

Every attempt must end in exactly one categorized outcome, such as:

- `invalid_fan_curve`;
- `invalid_system_curve`;
- `invalid_source_effect` (including non-positive relative-scale factor);
- `no_positive_flow_root`;
- `system_curve_range_too_short`;
- `unbracketed_operating_point`;
- `solver_failure`;
- `valid_root`.

The report must include attempted, valid, and failed counts; counts by failure reason; and valid fraction. Summaries use valid roots only and are explicitly conditional on that selection. If no valid roots exist, no output interval is reported. If a minimum valid fraction is used to label a run acceptable/inconclusive, the threshold must be explicit in the run configuration and report; there is no hidden universal threshold.

## 7. M2 v1 operating-condition and input policy

M2 v1 applies only to the tabulated fan curve plus tabulated system curve. It does not propagate uncertainty in the single-point quadratic resistance approximation. It holds fan count, fan RPM, voltage/PWM, fan configuration, heat load, air density, and specific heat fixed. These values and their provenance are still recorded in run metadata.

No affinity-law scaling or probabilistic RPM variation is allowed in M2 v1. Those belong to M3 and require a separate similarity model and validated speed range. A sidecar whose operating condition does not match the run input must be rejected.

Both curves' uncertainty states must be explicit. A missing sidecar must not imply zero uncertainty. A curve with unknown or unquantified uncertainty cannot be treated as exact by default. Any input intentionally held fixed while its uncertainty is unknown must be an explicit run-level exclusion, and the report must state that its uncertainty is omitted. For a complete uncertainty result, the fan and system curve uncertainty sources must both be accounted for.

## 8. Sampling and output reporting requirements for M2

Each run records:

- exact fan/system CSV and sidecar SHA-256 hashes;
- solver, uncertainty-engine, sidecar-schema, and sampler versions;
- Python/runtime version, random-number generator identity, seed, and attempted trial count;
- source IDs, PDFs, dependence declaration, and any explicitly excluded uncertainty sources;
- fixed operating conditions and model inputs;
- requested marginal coverage probability and quantile estimator;
- attempted, valid, failed, and reason-specific trial counts;
- valid fraction and any explicit minimum-valid-fraction criterion;
- output estimates and distributions for total flow, per-fan flow, common pressure, and ideal bulk-air temperature rise.

Preserve each valid trial as one output vector (or an equivalent reproducible summary) so covariance/correlation between outputs can be calculated from the same draws. Do not run separate simulations for each output quantity. M2 v1 should report marginal medians, marginal standard uncertainties where meaningful, central empirical coverage intervals, and the output covariance/correlation matrix. Marginal 95% coverage intervals are not a simultaneous joint 95% coverage region.

Use and record a specified sample-quantile estimator (recommended: Hyndman-Fan type 7 linear interpolation). Do not label a coverage interval a confidence interval. Report the valid sample count alongside every interval. The result is conditional on the input PDFs, source dependence model, reduced-order fan/system model, physical-validity filtering, and existence of an in-range operating point. It is not a guarantee of real-world coverage or physical validation.

The bulk-air temperature rise interval is conditional on fixed heat load, air density, and specific heat in M2 v1. It is not a component-temperature prediction. If those thermal inputs later receive uncertainty models, that is a separately versioned scope change.

## 9. M1 acceptance checklist

M1 is complete only after the project owner explicitly accepts or amends each recommendation:

- [ ] the vocabulary and separation of evaluation method, uncertainty metric, and PDF;
- [ ] the v1 scope: tabulated curves and fixed operating/thermal inputs;
- [ ] the sidecar location, exact CSV SHA-256 binding, measurement-basis metadata, and strict versioning;
- [ ] the source-ID and target semantics, including cross-sidecar shared sources;
- [ ] the four initial distributions and the zero-mean correction convention;
- [ ] the explicit distinct-source independence assumption and fail-closed unsupported-correlation behavior;
- [ ] conditional rejection sampling, exact endpoint treatment, and no-repair policy;
- [ ] fixed attempted-trial accounting and structured failure categories;
- [ ] marginal interval terminology and joint output/covariance reporting;
- [ ] explicit reporting of omitted/unquantified input uncertainty;
- [ ] the boundary between uncertain airflow prediction and GPU component temperatures.

No Monte Carlo implementation should start until this checklist is reviewed and accepted. The final JSON Schema and code must follow the accepted specification, not this proposal automatically.

## 10. References

- [JCGM 100:2008, Guide to the Expression of Uncertainty in Measurement (GUM)](https://doi.org/10.59161/JCGM100-2008E) — uncertainty evaluation, Type A/Type B evaluation, covariance, expanded uncertainty, and degrees of freedom.
- [JCGM 100:2008/Amd.1:2026](https://doi.org/10.59161/PPDI3267) — amendment on nonlinearity in measurement models; relevant to the nonlinear operating-point measurement model.
- [JCGM 101:2008, Propagation of distributions using a Monte Carlo method](https://doi.org/10.59161/JCGM101-2008) — propagation of input distributions through a model with a single output quantity.
- [JCGM 102:2011, Extension to any number of output quantities](https://doi.org/10.59161/JCGM102-2011) — Monte Carlo propagation for a multivariate output and its joint distribution, relevant to flow, pressure, and bulk-air temperature outputs.
- [JCGM publications / GUM suite](https://www.bipm.org/en/committees/jc/jcgm/publications) — official publication listing.
- [VIM 2.36, coverage interval](https://jcgm.bipm.org/vim/en/2.36.html) — distinguishes a coverage interval from a confidence interval.
