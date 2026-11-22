# Fan P–Q curve data

CSV schema:

```csv
flow_cfm,static_pressure_mmh2o
0,6.0
...
58,0
```

Each file represents one fan at one specified speed. Flow must increase from
zero-flow shutoff to the zero-pressure free-air endpoint; pressure must be
non-increasing. Keep the exact fan model, RPM/PWM, source URL, extraction method,
and data quality in the corresponding documentation or filename.

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
digitization of ARCTIC's published P9 Max 4300 RPM P–Q chart (PDF dated
2025-01-17). It is retained for historical comparison, not as the preferred
numerical input while the manufacturer workbook-derived table is available.

Both files are suitable for exercising the operating-point solver and
preliminary screening only. Neither establishes the installed MI50 system
curve or final cooling performance.
