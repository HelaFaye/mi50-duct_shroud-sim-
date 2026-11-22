# ARCTIC P9 Max 4300 RPM fan-curve provenance

## Canonical numerical source

The canonical repository curve is
`data/fan_curves/arctic_p9_max_4300rpm_manufacturer_cfd.csv`. It contains ten
positive-pressure P–Q points extracted from ARCTIC's manufacturer-published
`P9 Max - PQ Curve for CFD` workbook. This is manufacturer-published numerical
data, not a laboratory measurement made by this project.

- Fan: ARCTIC P9 Max, workbook operating condition 4300 RPM.
- Workbook filename: `P9 Max - PQ Curve for CFD.xlsx`.
- Official documentation: <https://support.arctic.de/en/p9-max/docs>.
- Workbook download:
  <https://support.arctic.de/products/p9-max/techdocs/P9%20Max%20-%20PQ%20Curve%20for%20CFD.xlsx>.
- Inspected local source filename:
  `arctic_p9_max_pq_curve_for_cfd.xlsx`.
- Workbook SHA-256:
  `0d323c1ddc730919366df477a298f9d0cdbcee88d0a70e00674a47697d2d8854`.
- Extracted worksheet: `xl/worksheets/sheet1.xml`, rows 14–23, columns B
  (flow) and C (static pressure).
- Retained points: 10, including shutoff `(0 CFM, 6.1692830885 mmH2O)` and
  free-air `(58.25 CFM, 0 mmH2O)`.
- Canonical CSV SHA-256:
  `d1c9123afa5bc3c95226cea0a57b58dc4bdc2a63d20e279fea4b5d09d15ae922`.

The two later workbook rows at approximately 59.2449 and 62.9680 CFM have
negative static pressure and are excluded. The solver's fan-curve contract
requires a nonnegative, non-increasing pressure curve ending at zero pressure;
these rows are outside the valid positive-pressure branch for this input.

## Extraction and reproducibility

The workbook itself is not copied into the repository. Download it from the
official ARCTIC documentation link above and save it as
`~/Downloads/arctic_p9_max_pq_curve_for_cfd.xlsx`. Then, from the repository
root, run:

```bash
python3 scripts/extract_arctic_p9_max_cfd_curve.py
```

The standard-library-only extractor verifies the exact workbook SHA-256,
extracts worksheet rows 14–23, validates ordering/endpoints/pressure
monotonicity, and verifies the expected CSV SHA-256. It does not overwrite an
existing CSV unless that file already has the canonical hash. The ten source
ordinates are preserved; no additional intermediate points are synthesized.

The workbook's flow-column label includes `Flow rate (ft^3/min) C=0.95`, but
the workbook does not explain that notation in the inspected content. Its
conversion formulas do not apply an additional 0.95 multiplier, and the
extracted free-air endpoint is 58.25 CFM, matching ARCTIC's published product
specification. Therefore the supplied tabular values are preserved exactly;
`C=0.95` remains unresolved source metadata. Do not apply another correction
factor without clarification from ARCTIC.

The workbook identifies an 85 mm outer rotor diameter and 33 mm hub diameter.
Those are workbook geometry metadata, not a basis for changing the P–Q data.

## Comparison with the historical chart digitization

The original file
`data/fan_curves/arctic_p9_max_4300rpm_digitized.csv` is retained unchanged as
a historical manual-digitization comparison artifact. Linear interpolation of
that 19-point curve at the manufacturer's ten flow coordinates gives:

- RMSE: `0.05327346 mmH2O`.
- Maximum absolute difference: `0.09022237 mmH2O`.
- Mean absolute difference: `0.04088139 mmH2O`.

The comparison supports that the manual digitization was reasonably close; it
does not make the digitized values manufacturer data. Conversely, the
manufacturer workbook has only ten retained points. It is the preferred,
more traceable numerical source, not a higher-resolution curve. Do not
interpolate and commit fabricated additional source measurements.

## Deterministic M3 source-substitution comparison

On 2026-11-22, the manufacturer curve and historical digitized curve were
evaluated using identical M3 sensitivity-engine settings:

- RPM: 4300, 4000, and 3600; affinity-law scaling explicitly enabled.
- Parallel fan counts: 1, 2, and 3.
- System-resistance multipliers: 0.5, 0.75, 1.0, 1.5, and 2.0.
- Hypothetical quadratic system reference: 2.0 mmH2O at 50 CFM.
- Baseline: 4300 RPM, two parallel fans, resistance multiplier 1.0.

Both reports completed all 45 scenarios with zero failures. Both used the
same deterministic solver source SHA-256. The manufacturer and digitized
fan-curve SHA-256 values were respectively:

- Manufacturer: `d1c9123afa5bc3c95226cea0a57b58dc4bdc2a63d20e279fea4b5d09d15ae922`.
- Historical digitization: `8b630deda1167e0fc72baaeac88cb8e44dc9956cadb0cff29f4aee696160147f`.

At the baseline, manufacturer minus digitized results were:

| Output | Manufacturer | Digitized | Change |
|---|---:|---:|---:|
| Total airflow | 60.233563 CFM | 60.522707 CFM | -0.289144 CFM (-0.4777%) |
| Fan/system pressure | 2.902466 mmH2O | 2.930398 mmH2O | -0.027932 mmH2O (-0.9532%) |
| Ideal bulk-air temperature rise | 8.712937 C | 8.671312 C | +0.041625 C (+0.4800%) |

Across the 45 paired scenarios, the maximum absolute differences were
0.38261531 CFM in total airflow at (4300 RPM, one fan, resistance multiplier
0.5), 0.05599750 mmH2O in pressure at (4300 RPM, three fans, multiplier 2.0),
and 0.11064213 C in ideal bulk-air temperature rise at (3600 RPM, one fan,
multiplier 1.5). The corresponding maximum absolute relative differences
were 0.75160%, 1.50884%, and 0.74599%.

These are deterministic differences caused by substituting one central-value
fan dataset for another under the stated hypothetical system model. They are
not uncertainty intervals, accuracy estimates, or evidence of installed MI50
performance. The comparison does not resolve `C=0.95` or validate affinity-law
similarity at the other RPM values.

## Engineering limitations

The workbook does not provide defensible pointwise uncertainty for the table
ordinates, and the meaning of `C=0.95` remains unresolved. A source SHA-256
establishes file identity, not measurement uncertainty, calibration quality,
flow-reference conditions, or equivalence to every condition represented by
the published P–Q PDF. The curve is suitable for deterministic solver and
sensitivity work with these limitations recorded. It does not validate an
installed MI50 fan/system operating point.

The MI50 system-curve template remains header-only. A hypothetical quadratic
system reference such as 2.0 mmH2O at 50 CFM remains a screening assumption,
not measured MI50 resistance. No real MI50 probabilistic or physical
performance result follows from adopting this fan dataset.
