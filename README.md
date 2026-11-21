# MI50 Active Cooling Project

Engineering research for a configurable cooling system for the AMD Radeon Instinct MI50, including fan/system operating-point analysis, physical inspection, photogrammetry, and a longer-term path toward parametric CAD and CFD validation.

## Repository scope at this revision

**This repository revision is a solver and photogrammetry snapshot, not the complete CAD/CFD project.** The README in the initial snapshot described several components that are not present in the checked-in tree. This version distinguishes implemented files from planned work so that users do not mistake roadmap items for available tools.

The main implemented capabilities are:

- Fan/system operating-point calculation in `analysis/fan_operating_point.py`.
- Manual ARCTIC P9 Max 4300 RPM fan-curve digitization in `data/fan_curves/`.
- A header-only measured MI50 system-curve template in `data/system_curves/`.
- Weighted photogrammetry scale fitting in `scripts/photogrammetry_scale_fit.py`.
- MI50 envelope, public-source, physical-measurement, and photogrammetry documentation under `docs/` and at the repository root.
- A static browser interface under `site/`.
- Automated unit tests under `tests/` and GitHub Actions under `.github/workflows/`.

The following deliverables are **not present in this checkout**: OpenSCAD source models, reference STL meshes, the earlier duct-sizing and acoustic-budget scripts, fan-catalog CSV, and a CFD-ready geometry/boundary-condition package. They must be restored from their authoritative source or developed in separate changes before the repository can be described as containing them.

See [`docs/REPOSITORY_STATUS.md`](docs/REPOSITORY_STATUS.md) for the audited inventory and continuation boundaries.

## Development plan and progress

The engineering roadmap, milestone acceptance criteria, branching policy, and current completion state are maintained in:

- [`docs/DEVELOPMENT_PLAN.md`](docs/DEVELOPMENT_PLAN.md) — milestone plan and engineering gates.
- [`docs/PROGRESS.md`](docs/PROGRESS.md) — current baseline, completed work, active milestone, and dated progress log.
- [`docs/UNCERTAINTY_MODEL_SPEC.md`](docs/UNCERTAINTY_MODEL_SPEC.md) — M1 uncertainty-data and propagation design draft; review required before stochastic implementation.

Keep `main` as the validated integration baseline. Perform ongoing engineering work on focused `wip/<topic>` branches and merge through pull requests after local validation and CI pass. Update the progress log when a milestone changes state or an engineering decision changes.

## Run the tests

The project currently uses Python's standard library for its analysis and tests; no third-party Python packages are required for the checked-in test suite.

```bash
python3 -m unittest discover -s tests -v
```

The current suite contains 21 tests: 17 fan/system operating-point tests and 4 photogrammetry scale-fit tests. GitHub Actions runs the suite on Python 3.10, 3.12, and 3.14 for pushes and pull requests.

## Fan/system operating-point solver

`analysis/fan_operating_point.py` finds the intersection of a single-fan pressure/flow curve and a system pressure-drop curve. It supports identical fans in parallel, piecewise-linear interpolation, and bisection without extrapolating outside the supplied curve ranges.

Two system models are supported:

1. **Quadratic screening approximation:** `Δp = K Q²`, with `K` fitted from one user-supplied pressure/flow reference point.
2. **Tabulated system curve:** measured or otherwise justified total-flow/pressure-drop pairs supplied as CSV. This is the preferred mode once physical measurements exist.

The included P9 Max curve is an approximate manual digitization of the manufacturer's published P–Q chart. Its intermediate values are not manufacturer numerical data. It is suitable for exercising the solver and preliminary screening, not final design sign-off.

### Quadratic example

The following reference point is hypothetical. It is not a measured MI50 heatsink/system resistance value.

```bash
python3 analysis/fan_operating_point.py \
  --curve data/fan_curves/arctic_p9_max_4300rpm_digitized.csv \
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
  --curve data/fan_curves/arctic_p9_max_4300rpm_digitized.csv \
  --system-curve data/system_curves/mi50_system_curve.csv \
  --fan-count 2 \
  --heat-load-w 300
```

The CSV columns are `flow_cfm,static_pressure_mmh2o`. The template is intentionally header-only. Do not enter the hypothetical 2 mmH₂O at 50 CFM point and label it as measured data. The solver rejects insufficient system-curve range rather than extrapolating.

The model assumes identical fans with equal flow sharing, a steady-state fan curve at one speed, and a consistent static-pressure convention between fan and system data. Series fans, unequal fan sharing, PWM control, transients, flow maldistribution, leakage, and recirculation are not modelled.

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
