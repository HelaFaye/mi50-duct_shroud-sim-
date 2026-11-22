# Fan P–Q curve data

CSV schema for solver-ready curves:

```csv
flow_cfm,static_pressure_mmh2o
0,6.0
...
58,0
```

Each solver-ready file represents one fan at one specified speed. Flow must
increase from zero-flow shutoff to the zero-pressure free-air endpoint; pressure
must be non-increasing. Keep raw source records separate when they do not meet
this contract. Never alter raw records to force solver compatibility.

## Canonical ARCTIC P9 Max curve

`arctic_p9_max_4300rpm_manufacturer_cfd.csv` is the preferred P9 Max 4300 RPM
curve. It contains ten positive-pressure numerical points extracted directly
from ARCTIC's manufacturer-published `P9 Max - PQ Curve for CFD` workbook. Its
SHA-256 is
`d1c9123afa5bc3c95226cea0a57b58dc4bdc2a63d20e279fea4b5d09d15ae922`.
The workbook SHA-256, official source links, extraction procedure, excluded
negative-pressure rows, comparison statistics, and unresolved `C=0.95` flow
notation are recorded in [`../../docs/ARCTIC_P9_MAX_CURVE_PROVENANCE.md`](../../docs/ARCTIC_P9_MAX_CURVE_PROVENANCE.md).

The workbook flow values are preserved exactly. No additional 0.95 multiplier
is applied because the workbook does not explain `C=0.95` and its conversion
formulas do not apply a second correction. The ten-point table is more
traceable than the digitization, not higher-resolution. It contains no
published pointwise uncertainty and does not constitute an in-house fan test.

## Historical manual digitization

`arctic_p9_max_4300rpm_digitized.csv` remains unchanged as an approximate manual
digitization of ARCTIC's published P–Q chart (PDF dated 2025-01-17). It is
retained for historical comparison, not as the preferred numerical input
while the manufacturer workbook-derived table is available.

## Noctua NF-A14 PWM, 1500 RPM

`noctua_nf_a14_pwm_1500rpm_source.csv` preserves the manufacturer's five
published coordinates in their published order and native airflow unit
(m³/h). `noctua_nf_a14_pwm_1500rpm_manufacturer.csv` is the corresponding
solver-ready curve. It reverses the point order to increasing flow and converts
m³/h to CFM using `1 CFM = 1.69901082 m³/h`; pressure values are unchanged.
The conversion and both SHA-256 values are recorded in
[`../../docs/NOCTUA_FAN_DATA_PROVENANCE.md`](../../docs/NOCTUA_FAN_DATA_PROVENANCE.md).

This curve is suitable for the deterministic solver at its declared 1500 RPM.
Do not use the M3 affinity-law mode to represent another measured speed: this
dataset contains only one manufacturer curve. The manufacturer's general
performance specifications state ±10%; no pointwise coordinate uncertainty is
published for the five curve points.

## Noctua NF-A14x25 G2 PWM, Cybenetics report 25FN140A

`noctua_nf_a14x25_g2_cybenetics_25FN140A_raw.csv` contains all 72 detailed
airflow/pressure measurements (nine PWM settings × eight points), together
with the report's RPM, current, and power columns. It preserves the report's
values and ordering, including negative terminal pressures and local pressure
increases. Those values are intentional and must not be clipped, sorted,
smoothed, isotonic-regressed, or otherwise modified in the raw file.

This is a source-data table, **not a solver-ready fan curve**. The existing
`FanCurve` contract requires non-negative, non-increasing pressure with a
zero-pressure free-air endpoint. The Cybenetics measurements do not satisfy
that contract without a documented derivation. No derived G2 solver curves or
M2 uncertainty sidecars are supplied in this change. See
[`../../docs/NOCTUA_FAN_DATA_PROVENANCE.md`](../../docs/NOCTUA_FAN_DATA_PROVENANCE.md)
for the source limitations and metrology boundary.

The P9 files remain unchanged. Both Noctua additions are separate evidence
records; neither establishes the installed MI50 system curve or final cooling
performance.
