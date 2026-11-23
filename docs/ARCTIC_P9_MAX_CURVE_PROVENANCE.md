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

## Electrical PWM dataset and source handling

The canonical P9 P–Q curve and this electrical PWM table describe different
properties. The P–Q curve is an airflow/static-pressure relationship at a
specified fan speed; this table records fan speed, supply voltage, current,
and power against PWM duty cycle. Do not merge the two datasets or infer
motor input from the aerodynamic curve.

- Fan: ARCTIC P9 Max, nominal 4300 RPM model.
- Official documentation page: <https://support.arctic.de/en/p9-max/docs>.
- Official PDF title/listing: `PWM Curve, 4300 RPM, P9 Max (2025-01-17)`.
- Official PDF: <https://support.arctic.de/products/p9-max/techdocs/PWM%20Curve%2C%204300%20RPM%2C%20P9%20Max%20%282025-01-17%29.pdf>.
- Local source filename: `arctic_p9_max_pwm_curve_2025-01-17.pdf`.
- Local source PDF SHA-256: `9a7ea47c8965cfd303a347c03e10784ef83eeb26afcda00b65ca04e09608b41f`.
- PDF physical page count: 1. The footer says `Page 2`; record both facts.
- Footer document date: `2024-11-15`. The official documentation listing
  labels the PDF `(2025-01-17)`; these are distinct metadata fields.
- Footer classification: `Confidential`.
- Tables: 12.00 V, 7.00 V, and 5.00 V, each with 20 PWM rows.
- Local transcription:
  `data/fan_curves/arctic_p9_max_pwm_electrical.csv`.
- Local CSV SHA-256: `ed98b8526bc711b0b8ec15cf588784e794c0db62f986fd9e0c7bab5e2e4654f7`.

### Transcription and handling rules

`source_table_row` preserves the original row number within each voltage table
and resets from 1 through 20 for each voltage. The CSV retains the three source
tables in 12 V, 7 V, then 5 V order. The displayed two-decimal current and
power values are preserved as strings. In particular, at 7 V and 6–10% PWM
the source displays `0.00 A` and `0.02 W`; at 12 V it displays `0.01 A` and
`0.07 W`. Do not enforce `P = V I` against rounded source values, recompute
power, or replace the displayed values with calculated values.

The source PDF footer is marked `Confidential`; this classification is
recorded here as source-provenance metadata. The repository retains a
numerical transcription of the reported values for reproducible engineering
analysis and links to ARCTIC's official source rather than bundling the PDF.
The CSV preserves the displayed source precision and ordering. It is a
project-maintained transcription, not an in-house measurement or an
ARCTIC-endorsed project artifact.

### Derived 4300 RPM electrical estimate at 12 V

The 4300 RPM target lies between the 90% PWM observation (4119 RPM, 0.25 A,
3.05 W) and the 100% observation (4476 RPM, 0.32 A, 3.85 W). Linear
interpolation in RPM gives approximately **0.28549 A** and **3.45560 W per
fan** at 12 V. These are derived estimates, not measured 4300 RPM electrical
observations. The interpolation is only between the two supplied endpoint
observations; it does not establish behavior at another supply voltage.
