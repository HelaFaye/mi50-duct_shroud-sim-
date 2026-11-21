# MI50 Active Cooling Project

Parametric fan shroud, duct, and airflow/thermal analysis for the **AMD Radeon Instinct MI50** (and related MI-series cards where geometry allows).

The project is being built around three related deliverables:

1. **Configurable CAD** — OpenSCAD geometry for fan mounts, angled inlet axes, merging chambers, outlet adapters, and a replaceable GPU-side interface.
2. **Fan/duct sizing** — documented fan performance data, first-order heat/flow calculations, and duct-area calculations.
3. **CFD / thermal validation** — flow simulation using fan performance curves and the actual heatsink flow resistance, followed by thermal validation against measured GPU temperatures.

## Current contents

- `cad/openscad/mi50_120mm_reference.scad` — the first editable reconstruction of the uploaded MI50 shroud STL. It is a **single-120-mm reference baseline**, not yet the multi-fan/tilted-fan generator.
- `models/reference/MI50_120mm_source.stl` — uploaded MI50 reference mesh. Its coordinates are in metres; the source mesh envelope is approximately 120.00 × 132.29 × 78.43 mm after conversion to millimetres.
- `models/reference/MI25_2x40_reference.stl` — related dual-40-mm reference shroud; envelope approximately 100.50 × 57.84 × 40.01 mm.
- `analysis/duct_sizing.py` — reproducible first-order CFM and duct-throat sizing calculator.
- `data/fan_catalog.csv` — fan dimensions, published endpoint ratings, acoustic units/test notes, P–Q curve links, CFD spreadsheet links and provenance labels. Ratings are free-air flow and shutoff pressure, **not** the simultaneous operating point.
- `docs/PUBLIC_SOURCES.md` — public-source research register covering MI50 teardown evidence, existing shroud precedents, fan manufacturer curves, temperature telemetry, licenses and unresolved data gaps.
- `docs/USER_DIMENSION_CLAIM_AUDIT.md` — evidence audit of supplied dimensions and the 16GB/32GB variant caveats.
- `docs/PHYSICAL_MEASUREMENT_GUIDE.md` and `data/mi50_measurement_template.csv` — specimen identification, non-destructive inspection, photo, and caliper measurement workflow.
- `docs/PHOTOGRAMMETRY_WORKFLOW.md` — calibrated photo-capture, scale-control, reconstruction-tool selection, and confidence protocol for 16GB/32GB specimen-specific mechanical models.
- `data/photogrammetry_capture_log_template.csv` and `data/photogrammetry_scale_constraints_template.csv` — capture provenance and independent dimensional scale references.
- `scripts/photogrammetry_scale_fit.py` — weighted uniform scale fit from multiple known 3D distances, with per-reference residuals.
- `data/mi50_envelope.json` — versioned, provenance-tagged common envelope and separate 16GB/32GB identity records.
- `docs/AIRFLOW_DESIGN.md` — thermal flow budget, duct sizing, fan-configuration assessment, and design rules.
- `docs/GEOMETRY_AND_ROADMAP.md` — source-mesh findings and the planned parametric architecture.
- `simulation/README.md` — CFD approach and boundary-condition requirements.
- `site/` — responsive GitHub Pages editor with browser-side OpenSCAD preview/export, source editing, JSON presets, and opt-in cookie persistence. See `docs/WEB_EDITOR.md`.
- `.github/workflows/pages.yml` — deploys the static `site/` directory with GitHub Pages.

## MI50 16GB / 32GB evidence status

AMD independently publishes the same headline external envelope for both MI50 SKUs: 267 mm board length, Full Height, Double Slot, passive cooling, and 300 W peak TDP. This supports a shared nominal packaging profile, not identical internal geometry. The available teardown is a genuine 16GB specimen; its two visible fin fields, cover fasteners, and vapor-chamber details are not yet verified on a 32GB card. Community research reports multiple 32GB PCB variants, but its compute-configuration claims conflict with AMD’s official 32GB specification; treat those reports as unverified identity leads. Identify the exact board/revision before applying the reference geometry. See `docs/MI50_ENVELOPE.md`.

## First-pass engineering conclusion

For a 300 W heat load, the ideal bulk-air requirement is approximately 35 CFM for a 15 °C air-temperature rise, or 53 CFM for a 10 °C rise. Real design flow must include margin for bypass, nonuniform flow, recirculation, and the heatsink pressure drop. The initial target is **45–60 CFM actually passing through the heatsink**, not merely a fan's advertised free-air rating.

At 50–55 CFM and a nominal 10 m/s duct velocity, the area is approximately 2,360–2,596 mm². With a 96 mm wide rectangular throat, that corresponds to about 24.6–27.0 mm of internal height. The initial preferred target is **at least 2,600–2,800 mm²**, subject to the measured free-flow area of the card heatsink.

The 2 × 40 mm reference layout is useful as a geometric precedent, but two ordinary 40 × 20 mm fans (using the Noctua NF-A4x20 as a concrete published example) total only about 11 CFM at zero static pressure. That is not a credible 300 W cooling solution. See `docs/AIRFLOW_DESIGN.md`.

## Units and conventions

- CAD dimensions: millimetres.
- Airflow: CFM (with SI conversions in calculations).
- Static pressure: mm H₂O or Pa.
- Temperatures: °C.
- Thermal design input: 300 W card-level heat load, pending confirmation of actual power telemetry and heat distribution.

## Important validation boundary

This project does not yet claim a safe thermal design. A fan's maximum CFM occurs at approximately zero static pressure; its maximum static pressure occurs at zero flow. Neither rating tells us the installed flow through this card. Before treating a design as complete, we need the fan's complete P–Q curve, the duct and heatsink pressure-loss curve, adequate sealing, and temperature testing under sustained workload.

## Suggested workflow

1. Identify each physical MI50 specimen and capture separate assembled/deshrouded photogrammetry datasets.
2. Calibrate the camera, scale each reconstruction from multiple independent dimensions, and physically validate fit-critical features.
3. Rebuild the measured PCB/heatsink/cover as separate parametric solids; keep 16GB and 32GB profiles independent until verified.
4. Finish the multi-fan/variable-angle CAD generator and preserve this single-120-mm model as a reference.
5. Validate CAD geometry and export a watertight fluid volume for CFD.
6. Compare fan curves with the simulated/system pressure curve to find the operating point.
7. Run thermal CFD only after the heatsink geometry or a defensible porous-media model is available.
8. Print a low-cost prototype, check fit and leakage, then test GPU temperatures, clocks, fan speed, and inlet/outlet air temperature.

## Reproducible sizing calculation

```bash
python3 analysis/duct_sizing.py
```

The calculator intentionally reports free-air capacity and first-order throat area separately. It does not predict installed airflow or GPU junction temperature.

## Acoustic design targets

The browser editor includes an initial dBA budget calculator. Set the fan count, one fan's sound-pressure level and measurement distance, the listening distance, ambient noise, any separately measured system-noise contribution, and the maximum target level. The calculator estimates the combined SPL and derives the maximum allowed one-fan SPL at its reference distance. Its free-field and uncorrelated-source assumptions are documented in `simulation/README.md`; this is not yet a validated acoustic propagation or CFD-noise model.

A reproducible command-line implementation is available:

```bash
python3 analysis/noise_budget.py --fan-count 2 --fan-spl 38 \\
  --reference-distance 1.0 --listener-distance 0.5 \\
  --target 35 --ambient 25
python3 -m unittest discover -s tests -v
```

## Fan/system operating-point solver (new)

`analysis/fan_operating_point.py` now solves a fan/system intersection using a
single-fan P–Q curve, a quadratic system-resistance model, and an optional
identical-fan parallel array. This replaces the invalid shortcut of summing
free-air CFM ratings when estimating installed flow. The solver uses
piecewise-linear curve interpolation and does not extrapolate beyond supplied
curve data.

A sample ARCTIC P9 Max 4300 RPM curve is provided at
`data/fan_curves/arctic_p9_max_4300rpm_digitized.csv`. Its intermediate points
are approximate manual readings from the manufacturer's chart; use the
manufacturer's numeric CFD spreadsheet or measured data for final analysis.

Example (the **2.0 mmH2O at 50 CFM** system reference is hypothetical, not a
measured MI50 pressure-drop value):

```bash
python3 analysis/fan_operating_point.py \\
  --curve data/fan_curves/arctic_p9_max_4300rpm_digitized.csv \\
  --fan-count 2 \\
  --system-pressure-mmh2o 2.0 \\
  --system-reference-flow-cfm 50 \\
  --heat-load-w 300
```

This illustrative case returns approximately 60.5 CFM total for two identical
parallel fans and an ideal bulk-air temperature rise of approximately 8.7 °C.
Those numbers are conditional on the hypothetical system curve, not a claim
about an installed MI50 assembly. The single-fan case under the same assumed
system curve is approximately 45.4 CFM and 11.6 °C ideal bulk-air rise.

See `docs/FAN_OPERATING_POINT_MODEL.md` for equations, data provenance,
assumptions, limitations and calibration requirements. Run the tests with:

```bash
python3 -m unittest discover -s tests -v
```
