# MI50 cooling project progress

_Last updated: 2026-11-21_

## Current baseline

- Repository: `HelaFaye/mi50-duct_shroud-sim-`
- Stable branch: `main`
- Current stable baseline: `eca4f4493e4df18843932a3e755299645ef1822f`
- Active engineering branch: `wip/uncertainty-aware-operating-point`
- Remote tracking: confirmed at `origin/wip/uncertainty-aware-operating-point`
- Active milestone: **M1 — Specify uncertainty semantics and input-data contract**
- M1 state: review-ready proposal v0.2 prepared; owner acceptance pending; no stochastic implementation authorized

## Verified results

### M0 — Repository baseline and CI complete

- Repository inventory confirmed the operating-point solver, fan/system curve data and template, photogrammetry scale fitter, documentation, static site, tests, and CI workflow.
- Absent CAD/OpenSCAD sources, reference STL meshes, older duct-sizing/acoustic scripts, fan catalog, and CFD-ready assets are explicitly documented as absent.
- Existing deterministic solver supports the quadratic screening model and tabulated system curve, identical parallel fans, piecewise-linear interpolation, and no-extrapolation behavior.
- Local validation: 21/21 unittests passed on Python 3.14.
- Main CI run [44953907969](https://github.com/HelaFaye/mi50-duct_shroud-sim-/actions/runs/44953907969): Python 3.10, 3.12, and 3.14 jobs all passed.
- Baseline commit: `eca4f4493e4df18843932a3e755299645ef1822f`.

### WIP branch, tracking, and specification publication

- Created `wip/uncertainty-aware-operating-point` from the tested `main` baseline.
- Plan/progress tracking commit: `1a870566f3f412c79972589d93e16ca696a97ea8`.
- M1 specification draft commit: `a4571eaa60ee07475aab6da0732280ea05e25139`.
- Progress-log correction commit: `857e6b91838268250352e44ec0a5ec90d97371b4`.
- WIP baseline CI [44954367135](https://github.com/HelaFaye/mi50-duct_shroud-sim-/actions/runs/44954367135): Python 3.10, 3.12, and 3.14 all passed.
- M1 specification CI [44956308326](https://github.com/HelaFaye/mi50-duct_shroud-sim-/actions/runs/44956308326): Python 3.10, 3.12, and 3.14 all passed compilation and the full unittest step.
- Progress-log correction CI [44956622384](https://github.com/HelaFaye/mi50-duct_shroud-sim-/actions/runs/44956622384): Python 3.10, 3.12, and 3.14 all passed compilation and the full unittest step.
- The remote WIP branch was confirmed at `857e6b91838268250352e44ec0a5ec90d97371b4`; the user's latest local status showed a clean tracking branch.

## Current engineering truth

- `data/system_curves/mi50_system_curve_template.csv` is header-only. No measured MI50 system curve is available in this repository.
- The `2.0 mmH2O at 50 CFM` quadratic reference remains a hypothetical screening input.
- The ARCTIC P9 Max 4300 RPM P–Q data are approximate manual chart digitization, not manufacturer numerical data or a measured fan curve. There are no defensible quantified digitization uncertainties in the repository.
- The 60.52 CFM / 2.930 mmH2O operating point previously calculated is conditional on that hypothetical system reference and digitized fan curve. It is not an installed MI50 performance measurement.
- The 8.67 °C value is ideal bulk-air temperature rise at the assumed 300 W and calculated airflow. It is not GPU junction, HBM, VRM, or heatsink temperature.
- No defensible probabilistic interval exists yet because uncertainty inputs, distributions, dependence, measurement compatibility, and sampled-curve validity treatment have not been accepted or quantified.

## Active milestone: M1 — uncertainty specification

Review-ready proposal: [`UNCERTAINTY_MODEL_SPEC.md`](UNCERTAINTY_MODEL_SPEC.md).

The v0.2 review draft recommends:

- conditional rejection sampling of invalid curve realizations, with no silent repair;
- fixed attempted-trial accounting and explicit failures;
- one shared latent draw per source ID, explicit independence between distinct IDs, and fail-closed handling of unsupported correlation;
- normal, Student-t, uniform, and triangular residual PDFs, while hard bounds remain non-probabilistic unless justified otherwise;
- exact physical anchors and explicit free-air-flow uncertainty;
- tabulated fan/system curves and fixed operating conditions for M2 v1;
- joint output samples with marginal coverage intervals and covariance/correlation reporting.

These are review recommendations, not owner-approved policy. The checklist in `UNCERTAINTY_MODEL_SPEC.md` remains open. M2 Monte Carlo implementation is blocked pending owner acceptance.

No uncertainty values are to be invented to populate existing data files. Synthetic examples used for tests must be clearly labelled synthetic. The current P9 digitization and empty system-curve template do not support a real MI50 uncertainty result.

## Progress log

| Date | Change | Evidence / result |
|---|---|---|
| 2026-11-21 | Published initial repository snapshot and configured `origin` | `main` initially pointed to `227ced78fa3fe52926d0108a0a40638814dd8c70` |
| 2026-11-21 | Audited repository scope and corrected README inventory | Confirmed absent CAD/STL/duct-sizing/acoustic/CFD assets; no hidden source files found |
| 2026-11-21 | Added Python CI matrix and repository status audit | Main commit `eca4f4493e4df18843932a3e755299645ef1822f` |
| 2026-11-21 | Verified main CI | Run `44953907969`; Python 3.10, 3.12, and 3.14 all successful |
| 2026-11-21 | Added development plan and progress tracking on WIP branch | Commit `1a870566f3f412c79972589d93e16ca696a97ea8` |
| 2026-11-21 | Verified WIP baseline CI | Run `44954367135`; Python 3.10, 3.12, and 3.14 all successful |
| 2026-11-21 | Published M1 uncertainty specification draft | Commit `a4571eaa60ee07475aab6da0732280ea05e25139`; awaiting owner review; M2 blocked |
| 2026-11-21 | Verified M1 specification commit CI | Run `44956308326`; Python 3.10, 3.12, and 3.14 all successful |
| 2026-11-21 | Corrected progress log with M1 commit/CI evidence | Commit `857e6b91838268250352e44ec0a5ec90d97371b4`; CI run `44956622384` passed all three Python versions |
| 2026-11-21 | Refined M1 review draft with explicit v1 recommendations | Proposal v0.2; awaiting owner acceptance; no stochastic code authorized |

## Update protocol

Append a dated row when a material change is completed. For each completed milestone record the resulting commit, local test result, CI run URL/result, and remaining physical-validation limits. Update milestone states in [`DEVELOPMENT_PLAN.md`](DEVELOPMENT_PLAN.md) only when their acceptance gates have been met.
