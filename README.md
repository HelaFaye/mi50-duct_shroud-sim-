# MI50 Active Cooling Project

Engineering research for a configurable cooling system for the AMD Radeon Instinct MI50, including fan/system operating-point analysis, physical inspection, photogrammetry, and a longer-term path toward parametric CAD and CFD validation.

## Repository scope at this revision

**This repository revision is a solver and photogrammetry snapshot, not the complete CAD/CFD project.** The README in the initial snapshot described several components that are not present in the checked-in tree. This version distinguishes implemented files from planned work so that users do not mistake roadmap items for available tools.

The main implemented capabilities are:

- Fan/system operating-point calculation in `analysis/fan_operating_point.py`.
- Manufacturer-workbook-derived ARCTIC P9 Max 4300 RPM numerical P–Q curve, with the prior manual digitization retained for comparison.
- A header-only measured MI50 system-curve template in `data/system_curves/`.
- Weighted photogrammetry scale fitting in `scripts/photogrammetry_scale_fit.py`.
- MI50 envelope, public-source, physical-measurement, and photogrammetry documentation under `docs/` and at the repository root.
- A parametric shroud editor and in-browser operating-point/acoustic simulation under `site/`, with watertight STL and OpenSCAD export (see [`docs/SHROUD_EDITOR.md`](docs/SHROUD_EDITOR.md)).
- Automated unit tests under `tests/` and GitHub Actions under `.github/workflows/`.

The following deliverables are **not present in this checkout**: the original OpenSCAD reference models and reference STL meshes, the earlier duct-sizing script, fan-catalog CSV, and a CFD-ready geometry/boundary-condition package. (The parametric editor generates new shroud STL/OpenSCAD files; it is not a restoration of the original models.) They must be restored from their authoritative source or developed in separate changes before the repository can be described as containing them.

See [`docs/REPOSITORY_STATUS.md`](docs/REPOSITORY_STATUS.md) for the audited inventory and continuation boundaries. Fan-data provenance and extraction are recorded in [`docs/ARCTIC_P9_MAX_CURVE_PROVENANCE.md`](docs/ARCTIC_P9_MAX_CURVE_PROVENANCE.md).

## Development plan and progress

The engineering roadmap, milestone acceptance criteria, branching policy, and current completion state are maintained in:

- [`docs/DEVELOPMENT_PLAN.md`](docs/DEVELOPMENT_PLAN.md) — milestone plan and engineering gates.
- [`docs/PROGRESS.md`](docs/PROGRESS.md) — current baseline, completed work, active milestone, and dated progress log.
- [`docs/UNCERTAINTY_MODEL_SPEC.md`](docs/UNCERTAINTY_MODEL_SPEC.md) — accepted M1 v1.0 uncertainty-data and propagation contract.
- [`docs/M2_UNCERTAINTY_ENGINE.md`](docs/M2_UNCERTAINTY_ENGINE.md) — M2 v1 uncertainty-engine operation, report semantics, and limitations.
- [`schemas/curve-uncertainty-v1.schema.json`](schemas/curve-uncertainty-v1.schema.json) — structural schema for curve uncertainty sidecars.

Keep `main` as the validated integration baseline. Perform ongoing engineering work on focused `wip/<topic>` branches and merge through pull requests after local validation and CI pass. Update the progress log when a milestone changes state or an engineering decision changes.

## Run the editor

```bash
python3 -m http.server 8000
```

Then open <http://localhost:8000/site/>. Every geometry change rebuilds a watertight mesh and an equivalent OpenSCAD model, and re-solves the operating point with a port of the Python solver. Cooler inlet dimensions and system resistance defaults are placeholders until you measure your card; see [`docs/SHROUD_EDITOR.md`](docs/SHROUD_EDITOR.md).

## Run the tests

The project uses Python's standard library for its analysis and tests; no third-party Python packages are required by the checked-in test suite.

```bash
python3 -m unittest discover -s tests -v
```

The combined Python suite currently contains 163 tests covering the deterministic solver, measured-curve solver, sensitivity and uncertainty engines, electrical model, fan datasets, and photogrammetry scale fitting. The browser modules have their own Node test suite (`node --test site/tests/*.test.mjs`). GitHub Actions runs both on Python 3.10, 3.12, and 3.14 for pushes and pull requests.

## Fan/system operating-point solver

`analysis/fan_operating_point.py` finds the intersection of a single-fan pressure/flow curve and a system pressure-drop curve. It supports identical fans in parallel, piecewise-linear interpolation, and bisection without extrapolating outside the supplied curve ranges.

Two system models are supported by the deterministic solver:

1. **Quadratic screening approximation:** `Δp = K Q²`, with `K` fitted from one user-supplied pressure/flow reference point.
2. **Tabulated system curve:** measured or otherwise justified total-flow/pressure-drop pairs supplied as CSV. This is the preferred mode once physical measurements exist.

The preferred P9 Max 4300 RPM input is the ten-point numerical table extracted from ARCTIC's `P9 Max - PQ Curve for CFD` workbook. The 19-point manual chart digitization remains in the repository as a historical comparison artifact. The workbook-derived curve is more traceable, not higher-resolution, and has no published pointwise uncertainty; see [the curve provenance record](docs/ARCTIC_P9_MAX_CURVE_PROVENANCE.md). It supports solver and preliminary sensitivity work, not final design sign-off.

### Quadratic example

The following reference point is hypothetical. It is not a measured MI50 heatsink/system resistance value.

```bash
python3 analysis/fan_operating_point.py \
  --curve data/fan_curves/arctic_p9_max_4300rpm_manufacturer_cfd.csv \
  --fan-count 2 \
  --system-pressure-mmh2o 2.0 \
  --system-reference-flow-cfm 50 \
  --heat-load-w 300
```

### Tabulated system-curve example

Copy the template before entering measurements:

```bash
cp data/system_curves/mi50_system_curve_template.csv \
  data/system_curves/mi50_system_curve.csv
```

Then populate it with measured total airflow and differential pressure pairs and run:

```bash
python3 analysis/fan_operating_point.py \
  --curve data/fan_curves/arctic_p9_max_4300rpm_manufacturer_cfd.csv \
  --system-curve data/system_curves/mi50_system_curve.csv \
  --fan-count 2 \
  --heat-load-w 300
```

The CSV columns are `flow_cfm,static_pressure_mmh2o`. The template is intentionally header-only. Do not enter the hypothetical 2 mmH₂O at 50 CFM point and label it as measured data. The solver rejects insufficient system-curve range rather than extrapolating.

The model assumes identical fans with equal flow sharing, a steady-state fan curve at one speed, and a consistent static-pressure convention between fan and system data. Series fans, unequal fan sharing, PWM control, transients, flow maldistribution, leakage, and recirculation are not modelled.

## M2 v1 uncertainty propagation

`analysis/operating_point_uncertainty.py` is a separate, opt-in path for Monte Carlo propagation through **tabulated** fan and system curves. It does not modify the deterministic solver or its CLI. It requires one SHA-256-bound v1 JSON sidecar per curve, explicit fan/configuration operating conditions, an RNG seed, and an attempted-trial count.

The sidecars identify uncertainty for every coordinate, shared source effects, and the original uncertainty statement/conversion notes. The engine rejects unsupported dependencies, invalid sampled curves, and out-of-range roots without repairing curves or retrying invisibly. Reports include trial failures, marginal empirical intervals, and joint output covariance/correlation.

See [`docs/M2_UNCERTAINTY_ENGINE.md`](docs/M2_UNCERTAINTY_ENGINE.md) for the invocation and report contract. The manufacturer-workbook P9 curve has no defensible pointwise uncertainty in the source workbook, and the MI50 system-curve template remains unmeasured. **Do not create real-data sidecars by guessing; no real MI50 probabilistic result can be produced from the current inputs.** Synthetic uncertainty fixtures in the tests are for software verification only.

## Thermal interpretation

The reported ideal bulk-air temperature rise is an energy-balance estimate:

\[
\Delta T_{air} = \frac{P}{\rho c_p Q}
\]

It is the average air-stream temperature rise for the assumed heat load and volume flow. It is **not** a GPU junction, HBM, VRM, heatsink-base, or local outlet temperature prediction. A thermal-resistance or validated heat-transfer model and measured temperatures are needed before making component-temperature or safe-operating claims.

## Measurement priorities

For a defensible installed operating point, characterize the complete intended air path: fan model/count/speed/orientation, inlet, shroud, seals, heatsink, outlet, and pressure measurement planes. Record total volumetric flow, differential static pressure, fan RPM, electrical operating condition, ambient conditions, instrument calibration/uncertainty, and repeatability. Keep the system pressure definition consistent with the fan-curve convention; document velocity-pressure corrections where applicable.

The external-flow-bench approach described in [`docs/FAN_OPERATING_POINT_MODEL.md`](docs/FAN_OPERATING_POINT_MODEL.md) can characterize the passive duct/heatsink resistance without operating a GPU at an unvalidated thermal load.

A CAD/CFD roadmap item is not considered implemented until its source files, provenance, validation procedure, and tests are committed to this repository.
