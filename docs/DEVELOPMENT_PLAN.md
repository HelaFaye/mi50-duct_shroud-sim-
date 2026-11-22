# MI50 cooling project development plan

_Last updated: 2026-11-21_

## Purpose

This plan defines the next engineering work for the MI50 active-cooling project. It is deliberately evidence-gated: a model capability is not considered validated merely because its equations execute or its unit tests pass. Hypothetical inputs, digitized manufacturer plots, measured data, and validated results must remain distinguishable.

The current repository is a solver/photogrammetry snapshot. The absent CAD, reference STL, duct-sizing, acoustic-budget, and CFD assets are tracked as recovery/development work, not assumed to exist.

## Working agreements

### Branching and integration

- `main` is the stable, tested integration baseline. Avoid committing work-in-progress directly to `main`.
- Use a focused branch named `wip/<topic>` for an active multi-step workstream. The current workstream is `wip/uncertainty-aware-operating-point`.
- Keep one coherent engineering objective per WIP branch. Split unrelated CAD/CFD restoration into separate branches rather than mixing it into solver changes.
- Push the WIP branch and use a pull request to review and merge it after the acceptance gates below pass.
- Do not report a branch as published until `git ls-remote --heads origin <branch>` confirms it.

### Evidence and model discipline

- Every input must have a unit, provenance, operating condition, and quality classification (manufacturer numeric data, chart digitization, calibrated measurement, estimate, or hypothetical screening input).
- Never insert guessed uncertainty values or present hypothetical system resistance as measured MI50 data.
- Preserve the current no-extrapolation behavior. An operating point outside either supplied curve's measured/digitized range is unresolved, not an invitation to extrapolate.
- Keep fan pressure and system pressure definitions consistent, including measurement planes and velocity-pressure corrections.
- Preserve backwards compatibility for the deterministic solver unless a separately reviewed interface change is justified.
- Treat a passing test suite as software verification, not physical validation of the cooling design.

### Local validation and handoff

For each overlay or focused change, review the diff, run `git diff --check`, compile the Python modules, run the full unittest suite, and inspect the resulting status before committing. Update [`PROGRESS.md`](PROGRESS.md) when the milestone state or a material engineering decision changes. Record the tested commit and CI run, not just a claim that tests passed.

## Milestones

| ID | Milestone | State | Depends on |
|---|---|---|---|
| M0 | Repository baseline, scope audit, and automated Python CI | Complete | — |
| M1 | Specify uncertainty semantics and input-data contract | Review-ready proposal; owner acceptance pending | M0 |
| M2 | Propagate curve/input uncertainty through the operating-point solver | Blocked pending M1 acceptance | M1 |
| M3 | Fan-RPM and system-resistance sensitivity analysis | Planned | M1; M2 for probabilistic comparisons |
| M4 | Evidence-based thermal model progression | Planned | M2; physical thermal measurements |
| M5 | Recover or develop revision-specific CAD and CFD assets | Separate workstream | Verified physical geometry and provenance |

### M0 — Repository baseline and CI

**Completed at** `eca4f4493e4df18843932a3e755299645ef1822f`.

Acceptance evidence:

- Repository inventory and limitations documented.
- README no longer presents absent CAD/CFD files as implemented.
- GitHub Actions compiles Python modules and runs the unittest suite on Python 3.10, 3.12, and 3.14.
- Local suite: 21/21 passing on Python 3.14.
- Main GitHub Actions run 44953907969: all three matrix jobs completed successfully.

### M1 — Specify uncertainty semantics and input-data contract

**Review-ready proposal v0.2 prepared; owner acceptance required.** See [`UNCERTAINTY_MODEL_SPEC.md`](UNCERTAINTY_MODEL_SPEC.md).

The review draft proposes decisions for:

1. Metrology vocabulary and separation of evaluation method, uncertainty metric, and probability distribution.
2. A versioned per-curve JSON sidecar bound to exact CSV bytes by SHA-256, with pressure/flow basis and operating-condition provenance.
3. Shared source IDs as shared latent draws, explicit independence between distinct IDs, and fail-closed handling of unsupported correlation.
4. Normal, Student-t, uniform, and triangular correction distributions; empirical resampling deferred; hard bounds not automatically sampled.
5. Conditional rejection sampling for physical curve constraints, preserving exact anchors and recording every invalid or unbracketed attempt.
6. Fixed tabulated curves and fixed operating conditions for M2 v1; RPM scaling and uncertain quadratic-reference inputs deferred.
7. Joint output samples, marginal coverage intervals, and output covariance/correlation reporting.

**Acceptance gate:** owner review and acceptance of the checklist in `UNCERTAINTY_MODEL_SPEC.md`. The review draft is not an approved implementation contract. No Monte Carlo or stochastic solver code is authorized before acceptance.

### M2 — Propagate uncertainty through the operating point

**Blocked until M1 is reviewed and accepted.**

The proposed v1 scope is limited to tabulated fan and system curves. It holds fan count, RPM, voltage/PWM, heat load, air density, and specific heat fixed. The quadratic system-reference model and RPM scaling are out of scope.

Expected behavior after M1 acceptance:

- Preserve deterministic API and CLI behavior when uncertainty mode is not requested.
- Bind sidecars to exact central-value CSV hashes and reject mismatched or unknown schema versions.
- Draw each unique source ID once per attempted trial and apply that draw to all linked targets, including cross-curve targets.
- Use a fixed attempted-trial budget; never silently retry invalid samples until a target number of successful roots is reached.
- Apply the existing curve validators and no-extrapolation solver; never repair or sort sampled curves.
- Record invalid-curve, no-positive-root, unbracketed, range, and solver failures by category.
- Report valid fraction, marginal coverage intervals, and covariance/correlation from the same joint output samples.
- Explicitly label all summaries as conditional on the declared PDFs, dependence assumptions, physically valid curves, and in-range roots.
- Reject missing/unquantified uncertainty by default; any held-fixed exclusion must be explicit and reported.

Acceptance tests should cover zero-uncertainty recovery, source sharing, cross-sidecar dependence, seeded reproducibility, unsupported-correlation rejection, endpoint invariance, invalid-curve accounting, no extrapolation, root failures, joint output covariance, and quantile calculations on analytically tractable synthetic cases.

### M3 — Fan-RPM and system-resistance sensitivity

Add deterministic scenario sweeps first. Probabilistic sweeps may follow once M2 is validated.

- Report sensitivity to system resistance, fan count, and fan RPM over an explicitly specified operating range.
- If fan affinity laws are used, expose the assumptions and scaling equations. For geometrically unchanged fans in comparable flow regimes, the usual similarity relationships are approximately flow proportional to speed, pressure proportional to speed squared, and shaft power proportional to speed cubed. Do not treat these relationships as a substitute for manufacturer curves or measured curves outside the validated range.
- Keep fan speed, fan electrical input, and system pressure-loss changes distinguishable.
- Do not silently extrapolate the 4300 RPM digitized P–Q curve to arbitrary speeds.

Acceptance tests should check expected limiting behavior and ensure RPM scaling preserves curve endpoints/monotonicity under its documented assumptions.

### M4 — Evidence-based thermal model progression

The existing `P/(rho * cp * Q)` result is an ideal bulk-air energy balance. It is not a GPU junction, HBM, VRM, or heatsink-base temperature.

Progression:

1. Keep bulk-air rise explicitly named and scoped.
2. Add a thermal-resistance/network model only when heat paths, component heat loads, and resistance values have defensible provenance.
3. Keep GPU die, HBM, VRM, heatsink, inlet, and outlet temperatures distinct where data permit.
4. Validate against sustained-load measurements that include board power, fan RPM, inlet/outlet air temperature, component telemetry, ambient conditions, workload duration, and sensor calibration.

No safe operating limit or component-temperature prediction should be claimed from airflow alone.

### M5 — CAD and CFD recovery/development

Treat CAD/CFD restoration as a separate workstream. Recover absent models only from an authoritative source or backup, preserving license and provenance. Otherwise develop new geometry from specimen-specific measurements. Keep MI50 16GB and 32GB geometry separate until verified. CFD should not be presented as validated until the fluid domain, mesh quality, boundary conditions, fan curves, heatsink resistance, and convergence evidence are recorded.

## Definition of done for an engineering milestone

A milestone is complete only when:

- its source/data/doc changes are committed and traceable;
- units, provenance, assumptions, and limitations are documented;
- deterministic and edge-case tests cover the new behavior;
- the complete local test suite passes;
- GitHub Actions passes on the configured Python matrix;
- `docs/PROGRESS.md` records the resulting commit, evidence, and any remaining physical-validation limits.
