# MI50 cooling project progress

_Last updated: 2026-11-21_

## Current baseline

- Repository: `HelaFaye/mi50-duct_shroud-sim-`
- Stable branch: `main`
- Current stable baseline: `eca4f4493e4df18843932a3e755299645ef1822f`
- Active engineering branch: `wip/uncertainty-aware-operating-point`
- Current WIP HEAD: `1a870566f3f412c79972589d93e16ca696a97ea8`
- Remote tracking: confirmed at `origin/wip/uncertainty-aware-operating-point`
- Active milestone: **M1 — Specify uncertainty semantics and input-data contract**
- M1 state: design draft prepared for owner review; no stochastic implementation authorized

## Verified results

### M0 — Repository baseline and CI complete

- Repository inventory confirmed the operating-point solver, fan/system curve data and template, photogrammetry scale fitter, documentation, static site, tests, and CI workflow.
- Absent CAD/OpenSCAD sources, reference STL meshes, older duct-sizing/acoustic scripts, fan catalog, and CFD-ready assets are explicitly documented as absent.
- Existing deterministic solver supports the quadratic screening model and tabulated system curve, identical parallel fans, piecewise-linear interpolation, and no-extrapolation behavior.
- Local validation after applying the tracking overlay: 21/21 unittests passed on Python 3.14.
- Main CI run [44953907969](https://github.com/HelaFaye/mi50-duct_shroud-sim-/actions/runs/44953907969): Python 3.10, 3.12, and 3.14 jobs all passed.
- Baseline commit: `eca4f4493e4df18843932a3e755299645ef1822f`.

### WIP branch and tracking documentation published

- Created `wip/uncertainty-aware-operating-point` from the tested `main` baseline.
- Committed plan/progress tracking at `1a870566f3f412c79972589d93e16ca696a97ea8`.
- Confirmed the remote branch points to the same commit with `git ls-remote --heads origin wip/uncertainty-aware-operating-point`.
- WIP CI run [44954367135](https://github.com/HelaFaye/mi50-duct_shroud-sim-/actions/runs/44954367135): Python 3.10, 3.12, and 3.14 jobs all passed compilation and the full unittest suite.
- Local branch status after push: clean and tracking `origin/wip/uncertainty-aware-operating-point`.

## Current engineering truth

- `data/system_curves/mi50_system_curve_template.csv` is header-only. No measured MI50 system curve is available in this repository.
- The `2.0 mmH2O at 50 CFM` quadratic reference remains a hypothetical screening input.
- The ARCTIC P9 Max 4300 RPM P–Q data are approximate manual chart digitization, not manufacturer numerical data or a measured fan curve.
- The 60.52 CFM / 2.930 mmH2O operating point previously calculated is conditional on that hypothetical system reference and digitized fan curve. It is not an installed MI50 performance measurement.
- The 8.67 °C value is ideal bulk-air temperature rise at the assumed 300 W and calculated airflow. It is not GPU junction, HBM, VRM, or heatsink temperature.
- No defensible probabilistic interval exists yet because uncertainty inputs, distributions, dependence, and sampled-curve validity treatment have not been accepted.

## Active milestone: M1 — uncertainty specification

Draft specification: [`UNCERTAINTY_MODEL_SPEC.md`](UNCERTAINTY_MODEL_SPEC.md).

The draft proposes a versioned JSON sidecar bound to the exact central-value CSV by SHA-256, separates point-specific residuals from shared calibration/digitization effects, and defines fail-closed handling for unsupported uncertainty semantics or correlations. It does not yet select the final monotone-curve sampling algorithm.

Next actions:

1. Review the uncertainty vocabulary and the distinction between evaluation method, uncertainty metric, and probability distribution.
2. Review the sidecar structure, CSV hash binding, source scopes, and additive/multiplicative effects.
3. Decide the v1 correlation capabilities and fail-closed behavior for unsupported dependence.
4. Select and justify the physical monotonicity/endpoint sampling method; account for selection effects if invalid draws are rejected.
5. Accept or revise the M1 checklist in `docs/UNCERTAINTY_MODEL_SPEC.md` before Monte Carlo code is written.

No uncertainty values are to be invented to populate existing data files. Synthetic examples used for tests must be clearly labelled synthetic.

## Progress log

| Date | Change | Evidence / result |
|---|---|---|
| 2026-11-21 | Published initial repository snapshot and configured `origin` | `main` initially pointed to `227ced78fa3fe52926d0108a0a40638814dd8c70` |
| 2026-11-21 | Audited repository scope and corrected README inventory | Confirmed absent CAD/STL/duct-sizing/acoustic/CFD assets; no hidden source files found |
| 2026-11-21 | Added Python CI matrix and repository status audit | Main commit `eca4f4493e4df18843932a3e755299645ef1822f` |
| 2026-11-21 | Verified main CI | Run `44953907969`; Python 3.10, 3.12, and 3.14 all successful |
| 2026-11-21 | Added development plan and progress tracking on WIP branch | Commit `1a870566f3f412c79972589d93e16ca696a97ea8`; remote branch confirmed |
| 2026-11-21 | Verified WIP CI | Run `44954367135`; Python 3.10, 3.12, and 3.14 all successful |
| 2026-11-21 | Drafted M1 uncertainty specification | `docs/UNCERTAINTY_MODEL_SPEC.md`; awaiting owner review; M2 remains blocked |

## Update protocol

Append a dated row when a material change is completed. For each completed milestone record the resulting commit, local test result, CI run URL/result, and remaining physical-validation limits. Update milestone states in [`DEVELOPMENT_PLAN.md`](DEVELOPMENT_PLAN.md) only when their acceptance gates have been met.
