# MI50 fan/system uncertainty model specification

_Status: M1 design draft for review. This document does not authorize Monte Carlo implementation yet._

_Last updated: 2026-11-21_

## 1. Purpose and scope

Define a traceable uncertainty model for the existing fan/system operating-point solver before adding stochastic computation. The immediate output is uncertainty in the steady-state intersection of a single-fan pressure/flow curve and a system pressure-drop curve, for the existing identical-fans-in-parallel model.

The measurement model is the root of:

\[
g(Q,\mathbf{x}) = \Delta p_{fan}(Q/N,\mathbf{x}_{fan})
                 - \Delta p_{system}(Q,\mathbf{x}_{system}) = 0
\]

where `Q` is total volumetric flow, `N` is the integer number of identical parallel fans, and `x` contains uncertain curve data and any explicitly enabled operating-condition inputs. Derived outputs include total flow, per-fan flow, common static pressure, and ideal bulk-air temperature rise. The last quantity remains an air-stream energy balance, not a component-temperature prediction.

This specification covers uncertainty provenance, representation, dependence, physical curve constraints, solver failures, and reporting. It does not add uncertainty values to existing CSV files and does not change the deterministic solver.

## 2. Metrology vocabulary

Uncertainty type and probability distribution are separate concepts. A Type A or Type B evaluation describes how an uncertainty component was evaluated; it does not, by itself, prescribe a probability distribution.

| Term | Required interpretation | Treatment in the data contract |
|---|---|---|
| Standard uncertainty, `u` | Standard-deviation measure associated with an input estimate | Store only when its derivation and distribution are documented; do not treat every `±` value as `u` |
| Expanded uncertainty, `U` | `U = k u_c`, with coverage factor `k` and a stated coverage basis | Preserve `U`, `k`, and coverage information as source metadata; convert to a sampling distribution only when the assumptions justify that conversion |
| Type A evaluation | Evaluation using statistical analysis of observations | Record observations or summary statistics, sample count, estimator, and degrees of freedom where applicable |
| Type B evaluation | Evaluation using other information, such as calibration certificates, specifications, resolution, or prior data | Record the source, stated bound/specification, interpretation, and rationale for the assigned distribution |
| Accuracy limit / tolerance | A stated permissible bound, not automatically a standard deviation or probability distribution | Keep as a bound unless a justified PDF is explicitly assigned; a rectangular PDF is an assumption, not an automatic conversion |
| Repeatability | Variation under stated repeatability conditions | Record whether the input describes an individual reading or a mean of `n` readings; do not confuse sample standard deviation with standard uncertainty of the mean |
| Digitization uncertainty | Uncertainty from reading a plotted curve, including pixel location, line thickness, and axis calibration | Separate point-local reading uncertainty from shared axis calibration/scale uncertainty |

A normal distribution must not be inferred merely because an instrument specification uses `±`. Likewise, a coverage factor such as `k = 2` must not be assumed to guarantee 95% coverage without a justified distribution and degrees-of-freedom basis.

## 3. Input provenance and uncertainty sources

Each curve remains a central-value CSV using the existing columns:

```csv
flow_cfm,static_pressure_mmh2o
```

Uncertainty metadata should live in a versioned JSON sidecar, rather than changing the current CSV format. This preserves the existing deterministic CSV reader and makes provenance explicit. The sidecar must identify the exact CSV file and its SHA-256 digest so uncertainty metadata cannot silently be applied to a different curve revision.

Every uncertainty source must record:

- a stable source identifier;
- the affected quantity (`flow_cfm`, `static_pressure_mmh2o`, or an explicitly modelled operating parameter);
- units and whether the effect is additive or multiplicative;
- evaluation basis (`type_a`, `type_b`, or `other`, with explanation);
- the source record (instrument, calibration certificate, manufacturer document, chart image/digitization record, or raw repeat observations);
- the assigned distribution and its parameters, or an explicit statement that only a hard bound is known;
- scope: shared across the curve, shared across a declared group of points, or point-specific;
- any known dependence on another source.

### 3.1 Source classes to represent

1. **Point-specific flow reading:** repeatability or local traverse/readout uncertainty for one flow point.
2. **Point-specific pressure reading:** differential-pressure repeatability and resolution for one point.
3. **Shared flow calibration:** a common flow scale factor or offset affecting many points. A common scale error is correlated across those points; it is not independent noise added separately to each row.
4. **Shared pressure calibration/zero:** common pressure scale and zero-reference effects. A zero correction derived from a common reference must retain the dependence introduced by using that reference for all points.
5. **Fan-chart digitization:** pixel-coordinate/line-location uncertainty may vary by point, while plot-axis calibration and chart scaling are shared across the digitized curve.
6. **Fan operating condition:** RPM, voltage, PWM, and configuration metadata identify the condition of a fan curve. RPM uncertainty is not to be silently folded into point noise.

The P9 Max curve currently in the repository is an approximate manual digitization. Until an actual axis calibration, source image, and line-picking procedure with defensible error bounds are recorded, it has no quantified probabilistic uncertainty. Its provenance label must remain `approximate_manual_digitization`; the software must not invent an uncertainty from the number of decimal places in the CSV.

## 4. Proposed sidecar data contract (draft)

The proposed sidecar has a top-level schema version, a strict link to its central-value CSV, curve type, provenance, operating condition, named uncertainty sources, and one point record per CSV data row. Point references use one-based CSV data-row indices (header excluded) and must match the CSV row count exactly.

Illustrative structure only; values below are placeholders showing field shape, not MI50 measurements or recommended uncertainty magnitudes:

```json
{
  "schema_version": "0.1-draft",
  "curve_type": "system",
  "central_values": {
    "file": "mi50_system_curve.csv",
    "sha256": "<sha256-of-exact-csv-bytes>"
  },
  "provenance": {
    "classification": "calibrated_measurement",
    "description": "Replace with test-rig, instrument, and measurement-plane record"
  },
  "operating_condition": {
    "fan_configuration_id": "<configuration-id>",
    "ambient_temperature_c": null
  },
  "uncertainty_sources": [
    {
      "id": "flow_scale_calibration",
      "evaluation": "type_b",
      "scope": "curve_shared",
      "quantity": "flow_cfm",
      "effect": "relative_scale",
      "distribution": {
        "family": "normal",
        "parameters": {"mean": 0.0, "standard_deviation": "<documented-value>"}
      },
      "source": "<calibration-certificate-reference>"
    }
  ],
  "points": [
    {
      "row_index": 1,
      "uncertainty_source_ids": ["flow_scale_calibration"]
    }
  ]
}
```

The final schema must define exact field types, allowed distributions, parameterization, units, missing-value behavior, and validation rules before the version advances beyond `0.1-draft`. It must reject unknown schema versions and unsupported source/effect combinations rather than ignore them.

The `central_values.sha256` is over the exact CSV bytes. Row indices are one-based among data rows, not physical file line numbers if comments or blank lines are ever permitted. The preferred CSV remains comment-free so this mapping is unambiguous.

## 5. Distribution policy

A PDF is assigned only when supported by observations, calibration information, instrument documentation, chart geometry, or a documented engineering rationale. Candidate families for a first implementation are:

- **Normal:** for an uncertainty component appropriately represented by a standard deviation and with no material truncation/asymmetry over the relevant range.
- **Uniform (rectangular):** only when the evidence supports an equally plausible bounded interval and the bound is explicitly stated.
- **Triangular:** only when a bounded interval and a defensible most-likely value are available.
- **Empirical:** only when the underlying observations or calibration residuals are retained and the resampling method is specified.

A bounded accuracy specification without a defensible probability model remains a hard bound; it cannot be silently converted to a uniform distribution. Lognormal or other positive-only distributions may be considered for positive scale factors if there is evidence for that model, but must not be selected just to avoid negative samples.

The sidecar should retain the source's original uncertainty statement as well as the normalized distribution used by the computation. Normalization must state all conversions, assumptions, and coverage information. Degrees of freedom are required when the estimated uncertainty depends materially on a finite sample.

## 6. Dependence and correlation

Independent point noise is not an adequate general model for an entire curve. At minimum, the design must distinguish:

- point-local residual components;
- a source effect shared across all points in one curve;
- a source effect shared across a declared subset of points;
- cross-quantity effects, where one physical cause affects both flow and pressure.

A shared source identifier applied to multiple targets represents one sampled latent effect reused at those targets. This captures common calibration and axis-scale effects without pretending that each row has an independent calibration error.

The v1 sidecar proposal should explicitly declare whether source terms are independent. If a material cross-correlation is known but the selected schema/version cannot represent it, analysis must fail with an unsupported-correlation error or require a documented conservative treatment. It must never silently replace known correlation with independence. A future schema may add covariance matrices or joint distributions, with positive-semidefinite validation and a clearly specified mapping from marginal distributions to the joint model.

## 7. Physical curve constraints and endpoint treatment

The deterministic solver currently requires:

- strictly increasing flow coordinates;
- non-increasing fan static pressure;
- non-decreasing system pressure drop;
- the existing zero-flow and endpoint conventions;
- no extrapolation beyond either curve.

Every sampled curve must satisfy the same physical and endpoint contract before solving. Do not sort perturbed points, clip pressure values, apply isotonic regression, or silently repair a sampled curve: those operations change the input distribution and can bias the result.

The uncertainty design must explicitly decide how to sample while preserving monotonicity. Candidate approaches to compare during M1 are:

1. draw correlated measurement/source effects and reject invalid curve realizations, reporting every rejection and the resulting conditional distribution; or
2. model non-negative segment increments/decrements or another monotone parameterization, with a documented transformation from the measured point uncertainties to that parameterization.

Neither approach is approved yet. Rejection sampling can condition the result on curve validity and become biased or inefficient when many draws fail. A monotone parameterization can alter the implied point marginals and covariance unless carefully derived. The chosen method must be justified, tested on known synthetic cases, and reported transparently.

Boundary values that are exact by definition may remain anchored (for example, zero pressure drop at zero system flow and zero fan pressure at the ideal free-air endpoint). That does not make the other endpoint coordinate or the measurements used to infer the anchor exact. The treatment of instrument zero correction and uncertainty in an inferred free-air flow must be explicit. The uncertainty algorithm must not perturb a fixed endpoint away from a solver-required boundary merely to later clamp it back.

## 8. RPM and operating-condition policy

A fan curve is valid for its documented fan model, physical installation, voltage/PWM condition, and RPM. The P9 Max CSV is labelled for 4300 RPM and is an approximate chart digitization.

M2 must not silently scale this curve to other speeds. RPM uncertainty may be represented as an operating-condition input only after its measurement model is specified. Deterministic affinity-law scenario sweeps belong to M3, where the similarity assumptions, Reynolds/regime limitations, endpoint handling, and permitted RPM interval will be documented and tested separately.

## 9. Sampling and result reporting requirements for M2

When M2 is authorized, every run must record:

- exact input CSV and sidecar hashes;
- solver/model version;
- requested trial count and random seed;
- distribution and correlation-model identifiers;
- requested output quantiles/coverage probability;
- attempted, valid, and failed trial counts;
- failures by reason (invalid sampled curve, fan range failure, system range failure, no bracketed intersection, or solver failure);
- valid-sample fraction and whether the run met its configured acceptance threshold;
- output summaries for total flow, per-fan flow, common pressure, and ideal bulk-air temperature rise.

Report medians and empirical quantiles, with means/standard deviations when meaningful. A central 95% empirical interval, if requested, is the selected lower and upper quantiles of the simulated output distribution; it is not automatically an expanded uncertainty `U = k u_c` and is not a guarantee of real-world coverage.

The output distribution is conditional on the input PDFs, the reduced-order model, physical-validity filtering, and the event that the operating point is bracketed within supplied curves. State this explicitly. Failed or out-of-range samples must remain visible in the report; do not silently replace them with extrapolated operating points. The run must fail or be marked inconclusive when its configured validity/acceptance requirement is not met.

## 10. M1 acceptance checklist

M1 is complete only after the project owner reviews and accepts:

- [ ] the vocabulary and separation of evaluation method, uncertainty metric, and PDF;
- [ ] the sidecar location, schema versioning, and central CSV hash binding;
- [ ] the supported uncertainty-source scopes and shared-effect semantics;
- [ ] the initial distribution families and conversion rules;
- [ ] the policy for finite degrees of freedom and expanded uncertainty;
- [ ] the v1 correlation capabilities and fail-closed behavior for unsupported dependence;
- [ ] the sampled-curve monotonicity and endpoint strategy;
- [ ] the failed/out-of-range sample accounting and result-interval terminology;
- [ ] the explicit boundary between uncertain airflow prediction and GPU component temperatures.

No Monte Carlo implementation should start until this checklist is reviewed. A review may revise this document; the versioned schema and code should follow the accepted revision, not this draft automatically.

## 11. References

- [JCGM 100:2008, Guide to the Expression of Uncertainty in Measurement (GUM)](https://doi.org/10.59161/JCGM100-2008E) — standard uncertainty, Type A/Type B evaluation, covariance, and expanded uncertainty.
- [JCGM 100:2008/Amd.1:2026](https://doi.org/10.59161/PPDI3267) — 2026 amendment specifically addressing nonlinearity in measurement models; relevant to the nonlinear fan/system intersection.
- [JCGM 101:2008, Propagation of distributions using a Monte Carlo method](https://doi.org/10.59161/JCGM101-2008) — propagation of input distributions through a measurement model.
- [JCGM publications / GUM suite](https://www.bipm.org/en/committees/jc/jcgm/publications) — current official publication listing.
