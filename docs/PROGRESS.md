# MI50 cooling project progress

_Last updated: 2026-11-22_

## Current baseline

- Repository: `HelaFaye/mi50-duct_shroud-sim-`
- Stable branch: `main`
- Stable baseline commit: `eca4f4493e4df18843932a3e755299645ef1822f`
- Active engineering branch: `wip/uncertainty-aware-operating-point`
- Latest verified M2 implementation commit: `0f8e86976c7053c84b72bf3a4dfdcdf408f52e28`
- M1: **v1.0 accepted** on 2026-11-21 by instruction to proceed with the v0.2 recommendations without amendments.
- M2: **v1.1 DKW quantile-precision refinement committed, locally validated, and CI-verified; the overall M2 milestone remains in progress.**
- M3: **initial deterministic sensitivity implementation committed and CI-verified; scenario-failure-isolation hardening is locally verified and awaiting follow-up CI.**

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
- 35 uncertainty-engine tests (30 M2 v1 + 5 M2 v1.1), integrated into the 56-test repository suite.

`--minimum-valid-fraction` is optional and has no hidden default. Without it, the report exposes the valid fraction but does not apply a yield threshold; a run with at least two valid roots can still be marked `conditional_result` even when the valid fraction is small. For runs where yield is an acceptance criterion, supply an explicit threshold and inspect `minimum_valid_fraction_met`. At least two valid roots are required for sample standard uncertainties and covariance; that mathematical minimum is not a guarantee that empirical tail quantiles are statistically stable. M2 v1.1 adds distribution-free DKW confidence bounds for finite-Monte-Carlo quantile precision, with 95% default familywise confidence across the four marginal outputs. These bounds use accepted valid-root vectors, are distinct from predictive coverage intervals, and do not impose an automatic sample-size acceptance threshold.

Do not create sidecars with invented uncertainty values or use the engine to claim real MI50 performance. Before real-data use, the fan and system curves need compatible measurement definitions and defensible quantified uncertainty sources. The DKW diagnostic addresses finite Monte Carlo sampling error only; it does not validate the input PDFs, quantify measurement uncertainty, or establish physical performance.

### M2 v1.1 — DKW Monte Carlo quantile precision verified

- Implementation commit: [`0f8e86976c7053c84b72bf3a4dfdcdf408f52e28`](https://github.com/HelaFaye/mi50-duct_shroud-sim-/commit/0f8e86976c7053c84b72bf3a4dfdcdf408f52e28).
- Report format incremented to 1.1; each output now includes DKW order-statistic confidence bounds for both central empirical coverage endpoints.
- The default 95% quantile-precision confidence is familywise across all four marginal outputs, using a Bonferroni-adjusted DKW band that is simultaneous over quantile probabilities within each marginal.
- Conservative order-statistic inversion uses Decimal rank arithmetic and explicitly reports unbounded tail limits as JSON `null` with unbounded flags.
- Local verification: `compileall` passed, `git diff --check` passed, and all 56 tests passed (21 original + 30 M2 v1 + 5 M2 v1.1).
- GitHub Actions [run 44999641433](https://github.com/HelaFaye/mi50-duct_shroud-sim-/actions/runs/44999641433) passed compilation and the full unittest step on Python 3.10, 3.12, and 3.14.
- The v1.1 commit did not modify the deterministic solver, accepted M1 specification, or v1 sidecar schema.
- M2 remains in progress pending broader implementation review and eventual evidence-based input data; software tests do not constitute physical validation.

## M3 — deterministic operating-point sensitivity

- Initial implementation commit: [`5919163`](https://github.com/HelaFaye/mi50-duct_shroud-sim-/commit/5919163e348cb757293b92dd0d82eba5dd46c80d).
- The initial implementation added the opt-in deterministic RPM/fan-count/system-resistance sweep without modifying the deterministic solver API or CLI.
- Initial local verification: 85/85 tests passed on Python 3.14.7.
- GitHub Actions run [45011421134](https://github.com/HelaFaye/mi50-duct_shroud-sim-/actions/runs/45011421134): Python 3.10, 3.12, and 3.14 all passed.
- Follow-up hardening retains invalid per-scenario fan and tabulated-system curve transformations as categorized failed rows instead of aborting otherwise valid scenarios. Two new regression tests bring the local suite to 87/87 passing on Python 3.14.7. This follow-up is not yet committed or CI-verified.
- Affinity-law scaling remains explicit opt-in. Geometric, kinematic, and dynamic similarity, density/compressibility, Reynolds number, and tip-speed Mach number are applicability checks.
- The P9 Max CSV remains approximate manual digitization. ARCTIC's official documentation lists a separate `P9 Max - PQ Curve for CFD` workbook, but its contents and equivalence to the chart conditions have not yet been inspected or validated.
- No measured MI50 system curve or physical MI50 performance validation is available. Quadratic reference scenarios remain hypothetical screening only.

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
| 2026-11-21 | Added M2 v1.1 DKW Monte Carlo quantile-precision reporting | Commit [`0f8e869`](https://github.com/HelaFaye/mi50-duct_shroud-sim-/commit/0f8e86976c7053c84b72bf3a4dfdcdf408f52e28); 56/56 local tests passed; [CI run 44999641433](https://github.com/HelaFaye/mi50-duct_shroud-sim-/actions/runs/44999641433) passed compilation and unit tests on Python 3.10, 3.12, and 3.14 |
| 2026-11-22 | Added M3 deterministic sensitivity prototype | Commit [`5919163`](https://github.com/HelaFaye/mi50-duct_shroud-sim-/commit/5919163e348cb757293b92dd0d82eba5dd46c80d); initial 85/85 tests passed locally; [CI run 45011421134](https://github.com/HelaFaye/mi50-duct_shroud-sim-/actions/runs/45011421134) passed all three Python versions; follow-up hardening adds two tests and awaits CI |

## Update protocol

Append a dated row for each material change. For completed work, record the resulting commit, local test result, CI run URL/result, and remaining physical-validation limits. Do not mark M2 complete solely because synthetic tests pass.
