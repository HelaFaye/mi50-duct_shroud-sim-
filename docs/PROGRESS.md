# MI50 cooling project progress

_Last updated: 2026-11-21_

## Current baseline

- Repository: `HelaFaye/mi50-duct_shroud-sim-`
- Stable branch: `main`
- Stable baseline commit: `eca4f4493e4df18843932a3e755299645ef1822f`
- Active engineering branch: `wip/uncertainty-aware-operating-point`
- Current confirmed remote WIP HEAD: `f7f3b1fab65493cfc885befff4bee7c2dfe70a58`
- M1: **v1.0 accepted** on 2026-11-21 by instruction to proceed with the v0.2 recommendations without amendments.
- M2: **v1 prototype committed, locally validated, and CI-verified; implementation remains in progress.**

## Verified baseline

### M0 — repository and deterministic solver

- The repository contains the deterministic fan/system operating-point solver, fan/system curve data and template, photogrammetry scale fitter, documentation, static site, tests, and Python CI workflow.
- Absent CAD/OpenSCAD sources, reference STL meshes, older duct-sizing/acoustic scripts, fan catalog, and CFD-ready assets are documented as absent.
- The solver supports the quadratic screening model and tabulated system curve, identical parallel fans, piecewise-linear interpolation, and no-extrapolation behavior.
- Original suite: 21/21 tests passed locally on Python 3.14 and on the original CI matrix.
- Main CI run [44953907969](https://github.com/HelaFaye/mi50-duct_shroud-sim-/actions/runs/44953907969): Python 3.10, 3.12, and 3.14 passed.

### WIP branch and M1 publication

- WIP branch: `wip/uncertainty-aware-operating-point`.
- Plan/progress tracking commit: `1a870566f3f412c79972589d93e16ca696a97ea8`.
- M1 specification and review commit: `3c300ee02a2fbb7da8ae05094239ec1e7dea341f`.
- Earlier progress-log correction commit: `857e6b91838268250352e44ec0a5ec90d97371b4`.
- M1 review CI run [44976693486](https://github.com/HelaFaye/mi50-duct_shroud-sim-/actions/runs/44976693486): Python 3.10, 3.12, and 3.14 passed.
- M1 v1.0 acceptance and implementation baseline are documented in [`UNCERTAINTY_MODEL_SPEC.md`](UNCERTAINTY_MODEL_SPEC.md).

### M2 v1 prototype committed and verified

- Implementation commit: [`f7f3b1fab65493cfc885befff4bee7c2dfe70a58`](https://github.com/HelaFaye/mi50-duct_shroud-sim-/commit/f7f3b1fab65493cfc885befff4bee7c2dfe70a58).
- The commit adds the opt-in `analysis/operating_point_uncertainty.py` engine, the v1 sidecar JSON Schema, 30 synthetic uncertainty-engine tests, usage/report documentation, and plan/progress updates.
- The deterministic solver `analysis/fan_operating_point.py` was not modified by this implementation commit.
- Local integration verification: `compileall` passed, all 51 tests passed (21 existing + 30 uncertainty tests), `git diff --check` passed, and `python3 -m json.tool` parsed the sidecar schema.
- GitHub Actions run [44986689330](https://github.com/HelaFaye/mi50-duct_shroud-sim-/actions/runs/44986689330): Python 3.10, 3.12, and 3.14 all passed compilation and the full unittest step.
- The GitHub WIP branch head was independently confirmed at `f7f3b1fab65493cfc885befff4bee7c2dfe70a58`.
- M2 remains **in progress**, not complete. Additional implementation review and acceptance work remain; synthetic tests and CI establish software verification, not hardware validation.

## Current engineering truth

- `data/system_curves/mi50_system_curve_template.csv` is header-only. No measured MI50 system curve is available.
- The `2.0 mmH2O at 50 CFM` quadratic reference remains a hypothetical screening input and is not supported by M2 v1, which requires tabulated curves.
- The ARCTIC P9 Max 4300 RPM P–Q data are approximate manual chart digitization, not manufacturer numerical data or a measured fan curve. There are no defensible quantified digitization uncertainties in the repository.
- The previous 60.52 CFM / 2.930 mmH2O operating point is conditional on the hypothetical system reference and digitized fan curve; it is not an installed MI50 performance measurement.
- The previous 8.67 °C value is ideal bulk-air temperature rise at assumed 300 W and calculated airflow, not GPU junction, HBM, VRM, or heatsink temperature.
- No real MI50 probabilistic result is supported by the current inputs. Synthetic test fixtures are software verification only.

## Active milestone: M2 — uncertainty propagation

M1 is complete. Its accepted design baseline is [`UNCERTAINTY_MODEL_SPEC.md`](UNCERTAINTY_MODEL_SPEC.md). The v1 sidecar schema is [`../schemas/curve-uncertainty-v1.schema.json`](../schemas/curve-uncertainty-v1.schema.json), and engine behavior is documented in [`M2_UNCERTAINTY_ENGINE.md`](M2_UNCERTAINTY_ENGINE.md).

The committed M2 prototype provides:

- an opt-in analysis module without modifying the deterministic solver;
- strict sidecar validation and exact central-value CSV SHA-256 binding;
- shared source-ID sampling across fan and system curves;
- normal, Student-t, uniform, and triangular source distributions;
- physical-curve rejection sampling and fixed attempted-trial/failure accounting;
- no extrapolation and no silent curve repair;
- marginal output intervals plus joint covariance/correlation reporting;
- 30 synthetic engine tests, integrated into the 51-test suite.

`--minimum-valid-fraction` is optional and has no hidden default. Without it, the report exposes the valid fraction but does not apply a yield threshold; a run with at least two valid roots can still be marked `conditional_result` even when the valid fraction is small. For runs where yield is an acceptance criterion, supply an explicit threshold and inspect `minimum_valid_fraction_met`. At least two valid roots are required for sample standard uncertainties and covariance; that mathematical minimum is not a guarantee that empirical tail quantiles are statistically stable.

Do not create sidecars with invented uncertainty values or use the engine to claim real MI50 performance. Before real-data use, the fan and system curves need compatible measurement definitions and defensible quantified uncertainty sources. Further M2 code review should consider whether minimum valid sample counts or Monte Carlo quantile-precision diagnostics are needed for the intended reporting use.

## Progress log

| Date | Change | Evidence / result |
|---|---|---|
| 2026-11-21 | Published initial repository snapshot and configured `origin` | `main` initially pointed to `227ced78fa3fe52926d0108a0a40638814dd8c70` |
| 2026-11-21 | Audited repository scope and corrected README inventory | Confirmed absent CAD/STL/duct-sizing/acoustic/CFD assets |
| 2026-11-21 | Added Python CI matrix and repository status audit | Main commit `eca4f4493e4df18843932a3e755299645ef1822f` |
| 2026-11-21 | Verified main CI | Run `44953907969`; Python 3.10, 3.12, and 3.14 passed |
| 2026-11-21 | Added development plan and progress tracking | Commit `1a870566f3f412c79972589d93e16ca696a97ea8` |
| 2026-11-21 | Published and refined M1 uncertainty specification | Review commit `3c300ee02a2fbb7da8ae05094239ec1e7dea341f`; CI run `44976693486` passed |
| 2026-11-21 | Accepted M1 v1.0 recommendations | Owner instruction: proceed with the v0.2 recommendations without amendments |
| 2026-11-21 | Added M2 v1 tabulated-curve uncertainty prototype | Commit `f7f3b1fab65493cfc885befff4bee7c2dfe70a58`; 51 local tests passed; CI run `44986689330` passed all three Python versions |

## Update protocol

Append a dated row for each material change. For completed work, record the resulting commit, local test result, CI run URL/result, and remaining physical-validation limits. Do not mark M2 complete solely because synthetic tests pass.
