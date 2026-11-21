# MI50 cooling project progress

_Last updated: 2026-11-21_

## Current baseline

- Repository: `HelaFaye/mi50-duct_shroud-sim-`
- Stable branch: `main`
- Current main commit: `eca4f4493e4df18843932a3e755299645ef1822f`
- Current engineering workstream: `wip/uncertainty-aware-operating-point` (create locally from the baseline before applying this tracking update; remote creation is not assumed until verified)
- Current active milestone: **M1 — Specify uncertainty semantics and input-data contract**

## Verified results

### Repository and CI baseline — M0 complete

- Repository inventory confirmed that the checkout contains the operating-point solver, fan/system curve data and template, photogrammetry scale fitter, documentation, static site, tests, and the new CI workflow.
- Absent CAD/OpenSCAD sources, reference STL meshes, the older duct-sizing/acoustic scripts, fan catalog, and CFD-ready assets are explicitly documented as absent rather than silently assumed to be present.
- Existing deterministic solver supports the quadratic screening model and tabulated system curve, identical parallel fans, piecewise-linear interpolation, and no-extrapolation behavior.
- Local validation reported 21/21 unittests passing on Python 3.14.
- GitHub Actions run [44953907969](https://github.com/HelaFaye/mi50-duct_shroud-sim-/actions/runs/44953907969) completed successfully. The Python 3.10, 3.12, and 3.14 jobs all passed compilation and the full unittest suite.
- Baseline commit: `eca4f4493e4df18843932a3e755299645ef1822f`.

## Current engineering truth

- `data/system_curves/mi50_system_curve_template.csv` is header-only. No measured MI50 system curve is available in this repository.
- The `2.0 mmH2O at 50 CFM` quadratic reference remains a hypothetical screening input.
- The ARCTIC P9 Max 4300 RPM P–Q data are approximate manual chart digitization, not manufacturer numerical data or a measured fan curve.
- The 60.52 CFM / 2.930 mmH2O operating point previously calculated is conditional on that hypothetical system reference and the digitized fan curve. It is not an installed MI50 performance measurement.
- The 8.67 °C value is ideal bulk-air temperature rise at the assumed 300 W and calculated airflow. It is not GPU junction, HBM, VRM, or heatsink temperature.
- No defensible probabilistic interval exists yet because measurement and curve uncertainty inputs, distributions, and correlations have not been specified.

## Active milestone: M1 — uncertainty specification

Next actions, in order:

1. Specify uncertainty vocabulary and units (standard uncertainty, expanded uncertainty, accuracy bounds, repeatability, and digitization tolerance).
2. Define the schema for per-point and curve-wide uncertainties for fan and system curves.
3. Define correlation handling, especially shared flow calibration, pressure zero/calibration, and fan-chart axis/digitization errors.
4. Define a physically valid sampling method that preserves curve monotonicity and does not extrapolate.
5. Review the specification before implementing Monte Carlo propagation.

No uncertainty values are to be invented to populate existing data files. Synthetic examples used for tests must be clearly labelled synthetic.

## Branch and local checkout notes

The intended branch name is `wip/uncertainty-aware-operating-point`. Create it from the latest `origin/main` using the command sequence in the handoff. Verify the remote branch with `git ls-remote --heads origin wip/uncertainty-aware-operating-point` after pushing.

The repository-integrity overlay was applied before commit `eca4f44`, but the transcript shows its `APPLY.txt` update and temporary `OVERLAY_SHA256SUMS` were not included in that commit. Inspect `git status --short` and `git diff -- APPLY.txt` before creating the WIP commit. Keep the useful application note if desired; the temporary overlay checksum manifest can be removed after its successful verification.

## Progress log

| Date | Change | Evidence / result |
|---|---|---|
| 2026-11-21 | Published initial repository snapshot and configured `origin` | `main` points to `227ced78fa3fe52926d0108a0a40638814dd8c70` |
| 2026-11-21 | Audited repository scope and corrected README inventory | Confirmed absent CAD/STL/duct-sizing/acoustic/CFD assets; no hidden source files found |
| 2026-11-21 | Added Python CI matrix and repository status audit | Commit `eca4f4493e4df18843932a3e755299645ef1822f`; 21 local tests passed |
| 2026-11-21 | Verified GitHub Actions | Run `44953907969`; Python 3.10, 3.12, and 3.14 all successful |
| 2026-11-21 | Opened uncertainty-aware workstream plan | M1 is next; WIP branch creation/push must be confirmed from local Git |

## Update protocol

Append a dated row when a material change is completed. For each completed milestone record the commit SHA, local test result, CI run URL/result, and remaining physical-validation limits. Update the milestone state in [`DEVELOPMENT_PLAN.md`](DEVELOPMENT_PLAN.md) only when its acceptance gate has been met.
