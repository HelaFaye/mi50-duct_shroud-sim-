# MI50 cooling project progress

_Last updated: 2026-11-21_

## Current baseline

- Repository: `HelaFaye/mi50-duct_shroud-sim-`
- Stable branch: `main`
- Stable baseline commit: `eca4f4493e4df18843932a3e755299645ef1822f`
- Active engineering branch: `wip/uncertainty-aware-operating-point`
- Last confirmed remote WIP commit before this overlay: `3c300ee02a2fbb7da8ae05094239ec1e7dea341f`
- M1: **v1.0 accepted** on 2026-11-21 by instruction to proceed with the v0.2 recommendations without amendments.
- M2: **v1 implementation overlay prepared; repository integration validation and CI pending**.

## Verified baseline

### M0 — repository and deterministic solver

- The repository contains the deterministic fan/system operating-point solver, fan/system curve data and template, photogrammetry scale fitter, documentation, static site, tests, and Python CI workflow.
- Absent CAD/OpenSCAD sources, reference STL meshes, older duct-sizing/acoustic scripts, fan catalog, and CFD-ready assets are documented as absent.
- The solver supports the quadratic screening model and tabulated system curve, identical parallel fans, piecewise-linear interpolation, and no-extrapolation behavior.
- Original local suite: 21/21 tests passed on Python 3.14.
- Main CI run [44953907969](https://github.com/HelaFaye/mi50-duct_shroud-sim-/actions/runs/44953907969): Python 3.10, 3.12, and 3.14 passed.

### WIP branch and M1 publication

- WIP branch: `wip/uncertainty-aware-operating-point`.
- Plan/progress tracking commit: `1a870566f3f412c79972589d93e16ca696a97ea8`.
- M1 review specification commit: `3c300ee02a2fbb7da8ae05094239ec1e7dea341f`.
- Progress-log correction commit: `857e6b91838268250352e44ec0a5ec90d97371b4`.
- CI run [44954367135](https://github.com/HelaFaye/mi50-duct_shroud-sim-/actions/runs/44954367135), run [44956308326](https://github.com/HelaFaye/mi50-duct_shroud-sim-/actions/runs/44956308326), run [44956622384](https://github.com/HelaFaye/mi50-duct_shroud-sim-/actions/runs/44956622384), and run [44976693486](https://github.com/HelaFaye/mi50-duct_shroud-sim-/actions/runs/44976693486) passed their Python 3.10, 3.12, and 3.14 jobs.
- The latest confirmed remote WIP commit before this overlay was `3c300ee02a2fbb7da8ae05094239ec1e7dea341f`, with CI run `44976693486` successful.

## Current engineering truth

- `data/system_curves/mi50_system_curve_template.csv` is header-only. No measured MI50 system curve is available.
- The `2.0 mmH2O at 50 CFM` quadratic reference remains a hypothetical screening input.
- The ARCTIC P9 Max 4300 RPM P–Q data are approximate manual chart digitization, not manufacturer numerical data or a measured fan curve. There are no defensible quantified digitization uncertainties in the repository.
- The previous 60.52 CFM / 2.930 mmH2O operating point is conditional on the hypothetical system reference and digitized fan curve; it is not an installed MI50 performance measurement.
- The previous 8.67 °C value is ideal bulk-air temperature rise at assumed 300 W and calculated airflow, not GPU junction, HBM, VRM, or heatsink temperature.
- No real MI50 probabilistic result is supported by the current inputs. Synthetic test fixtures are software verification only.

## Active milestone: M2 — uncertainty propagation

M1 is complete. The approved decisions are recorded in [`UNCERTAINTY_MODEL_SPEC.md`](UNCERTAINTY_MODEL_SPEC.md). The v1 sidecar schema is [`../schemas/curve-uncertainty-v1.schema.json`](../schemas/curve-uncertainty-v1.schema.json).

The first M2 overlay adds:

- opt-in `analysis/operating_point_uncertainty.py` without modifying the deterministic solver;
- strict sidecar validation and exact CSV SHA-256 binding;
- shared source-ID sampling across fan and system curves;
- normal, Student-t, uniform, and triangular source distributions;
- physical-curve rejection sampling and exact trial/failure accounting;
- marginal output intervals plus joint covariance/correlation reporting;
- synthetic tests and engine documentation.

The prototype currently has 30 synthetic uncertainty-engine tests. In an isolated test harness using a compatibility shim for the existing solver interface, all 30 pass; this is not yet full-checkout integration evidence. The overlay is not yet part of a repository commit. Local checkout integration, the complete combined test suite, and GitHub CI remain pending. Do not create sidecars with invented uncertainty values or use the engine to claim real MI50 performance.

## Progress log

| Date | Change | Evidence / result |
|---|---|---|
| 2026-11-21 | Published initial repository snapshot and configured `origin` | `main` initially pointed to `227ced78fa3fe52926d0108a0a40638814dd8c70` |
| 2026-11-21 | Audited repository scope and corrected README inventory | Confirmed absent CAD/STL/duct-sizing/acoustic/CFD assets |
| 2026-11-21 | Added Python CI matrix and repository status audit | Main commit `eca4f4493e4df18843932a3e755299645ef1822f` |
| 2026-11-21 | Verified main CI | Run `44953907969`; Python 3.10, 3.12, and 3.14 passed |
| 2026-11-21 | Added development plan and progress tracking | Commit `1a870566f3f412c79972589d93e16ca696a97ea8` |
| 2026-11-21 | Published M1 uncertainty specification review draft | Commit `a4571eaa60ee07475aab6da0732280ea05e25139` |
| 2026-11-21 | Corrected M1 publication/CI progress evidence | Commit `857e6b91838268250352e44ec0a5ec90d97371b4`; CI run `44956622384` passed |
| 2026-11-21 | Refined M1 v0.2 review proposal | Commit `3c300ee02a2fbb7da8ae05094239ec1e7dea341f`; CI run `44976693486` passed |
| 2026-11-21 | Accepted M1 v1.0 recommendations and prepared first M2 engine overlay | Owner instruction: proceed without amendments; repository integration and CI pending |

## Update protocol

Append a dated row for each material change. For completed work, record the resulting commit, local test result, CI run URL/result, and remaining physical-validation limits. Do not mark M2 complete solely because synthetic tests pass.
