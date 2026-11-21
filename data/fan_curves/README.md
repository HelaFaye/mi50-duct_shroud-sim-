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

`arctic_p9_max_4300rpm_digitized.csv` is an **approximate manual digitization**
of ARCTIC's published P9 Max 4300 RPM P–Q chart (PDF dated 2025-01-17). It is
not the manufacturer's underlying CFD spreadsheet and should be replaced by
that numeric data if extracted. It is suitable for exercising the operating-
point solver and preliminary sensitivity analysis, not final design sign-off.
