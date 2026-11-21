# Fan/system operating-point model

## What this module does

`analysis/fan_operating_point.py` solves the intersection between a fan
static-pressure/flow curve and a system pressure-drop curve. It supports an
array of **identical fans in parallel**, assumes equal flow sharing, and uses
piecewise-linear interpolation. A bisection solver finds the operating point
without extrapolating outside either supplied curve.

Two system-curve modes are available:

1. **Quadratic screening approximation:** `dp = K * Q_total^2`, with `K`
   fitted from one user-supplied pressure/flow reference point. This is the
   existing mode and remains useful for parameter sweeps.
2. **Tabulated system curve:** measured or otherwise justified points in a
   CSV file. This is the preferred mode once pressure-drop measurements exist.

For `N` identical parallel fans, each fan operates at `Q_total/N`, each fan
sees the common pressure rise, and the system curve is evaluated at total flow.

## Run it with a quadratic approximation

```bash
python3 analysis/fan_operating_point.py \
  --curve data/fan_curves/arctic_p9_max_4300rpm_digitized.csv \
  --fan-count 2 \
  --system-pressure-mmh2o 2.0 \
  --system-reference-flow-cfm 50 \
  --heat-load-w 300
```

The `2.0 mmH2O at 50 CFM` reference is an arbitrary screening assumption, not
measured MI50 heatsink resistance.

## Run it with a measured system curve

```bash
python3 analysis/fan_operating_point.py \
  --curve data/fan_curves/arctic_p9_max_4300rpm_digitized.csv \
  --system-curve data/system_curves/mi50_system_curve_template.csv \
  --fan-count 2 \
  --heat-load-w 300
```

Replace the template with actual measurement rows before interpreting its
output. The included template is header-only and intentionally cannot be
solved until measured data are added. Both modes accept `--json` for browser
editor or downstream integration.

## CSV format and validation

Both curve files use these columns:

```csv
flow_cfm,static_pressure_mmh2o
```

Fan curves must start at 0 CFM with positive shutoff pressure, have strictly
increasing flow and non-increasing pressure, and end at 0 mmH2O at free-air
flow. System curves must start at (0 CFM, 0 mmH2O), have strictly increasing
flow and non-decreasing pressure, and include at least one positive pressure
drop. The solver refuses extrapolation beyond either curve. If the measured
system curve ends before the fan/system intersection, collect more high-flow
points rather than extrapolating.

The fan curve at
`data/fan_curves/arctic_p9_max_4300rpm_digitized.csv` is an approximate manual
digitization of ARCTIC's official P9 Max 4300 RPM P–Q chart. Its intermediate
points are not manufacturer numerical data. The chart and specification links
are listed in `data/fan_curves/README.md`; replace the digitization with the
manufacturer numeric data or a measured fan curve when available.

## Measurement protocol for an MI50 system curve

A system curve is the pressure drop across the complete installed air path as
a function of **total measured volumetric flow**. It must describe the same
configuration being evaluated: fan placement and RPM, inlet, shroud, seals,
heatsink, outlet, and measurement planes. Do not combine a fan curve using
one static-pressure convention with system measurements using another.

For each point, record at minimum:

- total flow (CFM), measured with a suitable calibrated flow instrument or a
  documented duct traverse;
- differential static pressure (mmH2O or Pa), with pressure-tap locations
  and tubing arrangement documented;
- fan model, count, RPM/PWM, orientation, and electrical operating condition;
- shroud/duct configuration, leakage/sealing state, heatsink/card identity;
- ambient air temperature and test repeatability / instrument uncertainty.

Take several stable points across the intended flow range. Change flow using
an appropriate controllable restriction or fan speed while keeping the
measurement setup documented. Avoid placing a probe directly in a high-velocity
jet and calling its reading static pressure. A practical test should establish
repeatability and instrument zero before/after the sweep. Do not operate the
GPU at a power/temperature combination outside its safe limits merely to
obtain a point; an external flow bench with the heatsink/duct assembly can
characterize pressure drop without a powered GPU.

The template CSV contains no sample values by design. Do not put the earlier
2 mmH2O-at-50-CFM placeholder into it and label that measured data.

## Thermal interpretation and limitations

The output's ideal bulk-air temperature rise follows:

\[
\Delta T = \frac{P}{\rho c_p Q}
\]

It estimates the average air-stream energy balance only. It is not GPU
junction, HBM, VRM, heatsink-base, or local outlet temperature. The model does
not resolve maldistribution, bypass leakage, recirculation, fan interaction,
nonuniform pressure fields, or heat-transfer coefficients. Parallel fan flow
sharing is assumed equal; series arrangements and unequal fans are not
implemented. Fan curves are fixed-speed steady-state curves; PWM control,
stall, transients, and temperature-dependent properties are not solved.

A tabulated system curve is a major step beyond choosing an arbitrary single
pressure/flow point, but the resulting model remains reduced-order screening,
not CFD or a thermal validation of 185 W, 250 W, or 300 W operation.
