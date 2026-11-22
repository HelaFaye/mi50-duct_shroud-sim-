# MI50 cooling project development plan

_Last updated: 2026-11-21_

## Purpose

This plan defines the evidence-gated engineering work for the MI50 active-cooling project. A model capability is not physically validated merely because its equations execute or its unit tests pass. Hypothetical inputs, chart digitization, measured data, and validated results must remain distinguishable.

The current repository is a solver/photogrammetry snapshot. CAD, reference STL, duct-sizing, acoustic-budget, and CFD assets that are absent are tracked as recovery/development work, not assumed to exist.

## Working agreements

### Branching and integration

- `main` is the stable tested integration baseline.
- Use a focused `wip/<topic>` branch for an active multi-step workstream. The current workstream is `wip/uncertainty-aware-operating-point`.
- Keep one coherent objective per WIP branch. Split CAD/CFD restoration into separate branches.
- Push WIP work and integrate through a pull request only after the acceptance gates pass.
- Do not report a branch as published until `git ls-remote --heads origin <branch>` confirms it.

### Evidence and model discipline

- Every input has units, provenance, operating condition, and quality classification.
- Never invent uncertainty values or present hypothetical system resistance as measured MI50 data.
- Preserve no-extrapolation behavior. An operating point outside either supplied curve domain is unresolved.
- Keep pressure and flow definitions compatible, including measurement planes and velocity-pressure corrections.
- Preserve deterministic API/CLI behavior unless a separately reviewed change is justified.
- Passing tests are software verification, not physical validation.

### Local validation and handoff

For each overlay or focused change, inspect its diff, run `git diff --check`, compile Python modules, run the complete unittest suite, and inspect status before committing. Update [`PROGRESS.md`](PROGRESS.md) with actual commit and CI evidence. Overlay manifests/application helpers are temporary and should be removed after successful checksum verification unless deliberately intended as repository files.

## Milestones

| ID | Milestone | State | Depends on |
|---|---|---|---|
| M0 | Repository baseline, scope audit, and automated Python CI | Complete | — |
| M1 | Specify uncertainty semantics and input-data contract | Complete — v1.0 accepted | M0 |
| M2 | Propagate curve/input uncertainty through operating-point solver | Implementation in progress — v1 prototype | M1 |
| M3 | Fan-RPM and system-resistance sensitivity analysis | Planned | M1; M2 for probabilistic comparisons |
| M4 | Evidence-based thermal model progression | Planned | M2; physical thermal measurements |
| M5 | Recover or develop revision-specific CAD and CFD assets | Separate workstream | Verified physical geometry and provenance |

### M0 — Repository baseline and CI

**Completed at** `eca4f4493e4df18843932a3e755299645ef1822f`.

Acceptance evidence:

- Repository inventory and absent assets documented.
- Python modules compile and the unittest suite runs on Python 3.10, 3.12, and 3.14.
- The original 21-test suite passed locally and on the CI matrix.
- Main CI run `44953907969` passed all three matrix jobs.

### M1 — Uncertainty semantics and input-data contract

**Complete — v1.0 accepted on 2026-11-21.** See [`UNCERTAINTY_MODEL_SPEC.md`](UNCERTAINTY_MODEL_SPEC.md).

Accepted decisions include explicit per-coordinate coverage, SHA-256-bound sidecars, source-ID shared latent draws, declared independence between distinct source IDs, fail-closed unsupported dependence, four zero-mean correction PDFs, conditional rejection sampling, fixed attempted-trial accounting, exact anchors, and joint output statistics. The structural contract is [`schemas/curve-uncertainty-v1.schema.json`](../schemas/curve-uncertainty-v1.schema.json).

### M2 — Propagate uncertainty through the operating point

**Implementation in progress.** The first opt-in engine is in [`operating_point_uncertainty.py`](../analysis/operating_point_uncertainty.py); its usage and report are documented in [`M2_UNCERTAINTY_ENGINE.md`](M2_UNCERTAINTY_ENGINE.md).

V1 is limited to tabulated fan and system curves with fixed fan/thermal inputs. Preserve deterministic API/CLI behavior. Use exact CSV hashes, explicit seed/trial count, one draw per shared source ID, no implicit independence beyond the declared v1 assumption, physical curve validation, no extrapolation, fixed attempted-trial accounting, and categorized failures. Report conditional marginal intervals and joint covariance/correlation from the same valid output vectors.

Acceptance tests include zero-uncertainty recovery, source sharing, seeded reproducibility, strict sidecar validation, anchor handling, unsupported-dependence rejection, invalid-curve accounting, range/root failures, Type 7 quantiles, DKW finite-Monte-Carlo quantile-precision bounds with familywise coverage across outputs, and joint output statistics. Synthetic tests do not constitute MI50 hardware validation. The DKW diagnostic must remain separate from the predictive output interval and must not impose an undocumented automatic sample-size threshold.

### M3 — Fan-RPM and system-resistance sensitivity

Add deterministic scenario sweeps first. Probabilistic sweeps may follow after M2 is validated.

- Report sensitivity to system resistance, fan count, and RPM over an explicit range.
- If affinity laws are used, expose similarity assumptions and Reynolds/regime limitations; do not silently extrapolate the 4300 RPM digitized curve.
- Keep fan speed, electrical input, and system-loss changes distinguishable.

### M4 — Evidence-based thermal model progression

The existing `P/(rho * cp * Q)` result is an ideal bulk-air energy balance, not a GPU junction, HBM, VRM, or heatsink-base temperature.

1. Keep bulk-air rise explicitly named and scoped.
2. Add a thermal-resistance/network model only with defensible heat paths, component loads, and resistance values.
3. Keep die, HBM, VRM, heatsink, inlet, and outlet temperatures distinct where data permit.
4. Validate with sustained-load measurements including board power, fan RPM, inlet/outlet temperature, component telemetry, ambient conditions, workload duration, and sensor calibration.

### M5 — CAD and CFD recovery/development

Treat CAD/CFD restoration as a separate workstream. Recover assets only from an authoritative source or backup with provenance; otherwise measure specimen-specific geometry. Keep MI50 16 GB and 32 GB geometry separate until verified. CFD is not validated without a defined domain, mesh-quality evidence, boundary conditions, fan curves, thermal properties, and convergence evidence.

## Definition of done

A milestone is complete only when its changes are traceable, assumptions and limitations are documented, deterministic and edge-case tests pass, the full local suite passes, GitHub Actions passes on the configured Python matrix, and `docs/PROGRESS.md` records the commit, CI evidence, and remaining physical-validation limits.
