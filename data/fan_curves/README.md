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
not manufacturer-supplied numerical data. The separately listed CFD workbook
below is a candidate source whose contents and test conditions remain unverified. It is suitable for exercising the operating-
point solver and preliminary sensitivity analysis, not final design sign-off.


ARCTIC's official [P9 Max documentation](https://support.arctic.de/en/p9-max/docs)
also lists a separate **P9 Max - PQ Curve for CFD** XLSX workbook alongside
the published P-Q chart. That workbook is a candidate numerical source for a more traceable curve
reconstruction; its resolution and equivalence to the chart conditions are unknown. Its sheets, units, pressure
definition, operating conditions, and numerical contents must be inspected
before adopting its data; it has not yet been validated against this CSV.
