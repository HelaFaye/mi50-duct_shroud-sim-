# Noctua NF-A14 fan-data provenance

_Status: source data imported and integrity-tested; only the original NF-A14 curve is solver-ready. The G2 raw measurements are intentionally not transformed into a solver curve._

## Scope and repository treatment

This change adds two distinct Noctua datasets without replacing or modifying the
canonical ARCTIC P9 Max curve:

1. The original **NF-A14 PWM at 1500 RPM** manufacturer five-point curve. Its
   five source coordinates are numerically published and meet the project's
   fixed-speed fan-curve shape requirements after reversing the published
   point order and converting airflow units.
2. The **NF-A14x25 G2 PWM** independent Cybenetics report 25FN140A. It contains
   72 detailed records across nine PWM settings. These are retained as raw
   laboratory records and are not yet valid `FanCurve` inputs.

The source measurements, normalized solver input, and any future fitted or
derived curve must remain separate artifacts. A future G2 processing proposal
must be reviewed against `docs/UNCERTAINTY_MODEL_SPEC.md` before generating
derived curves or uncertainty sidecars.

## 1. Original NF-A14 PWM manufacturer curve

- Manufacturer: Noctua
- Model: NF-A14 PWM (original 140 mm × 140 mm × 25 mm model)
- Curve operating speed: 1500 RPM
- Source: [Noctua NF-A14 PWM specification PDF](https://cdn.noctua.at/media/2aa6498c/Noctua%20NF-A14%20PWM%20Specification.pdf?download=true)
- Source section: 3.2, Performance curve
- Manufacturer's general performance specification tolerance: ±10%
- Source point count: 5

`data/fan_curves/noctua_nf_a14_pwm_1500rpm_source.csv` preserves the five
published numeric ordinates and the order in the source table:

| Source point | Airflow (m³/h) | Static pressure (mm H₂O) |
|---:|---:|---:|
| 1 | 140.20 | 0.00 |
| 2 | 104.10 | 0.67 |
| 3 | 69.70 | 0.98 |
| 4 | 31.20 | 1.66 |
| 5 | 0.00 | 2.08 |

Its SHA-256 is
`4a74752dbbc0a82952d532b827c462304eab86185b514685f6db4b930eb25254`.

### Unit-normalized solver input

`data/fan_curves/noctua_nf_a14_pwm_1500rpm_manufacturer.csv` is the same
five coordinates in the existing solver schema and increasing-flow order.
Airflow is converted using:

\[
Q_{CFM} = Q_{m^3/h} / 1.69901082
\]

No pressure ordinate is changed. Converted flow values are retained to six
decimal places; this is unit normalization, not additional measurement
precision. The resulting free-air endpoint is 82.518603 CFM (82.52 CFM at the
manufacturer's stated precision). The pressure endpoints remain 2.08 and
0.00 mmH₂O.

Normalized CSV SHA-256:
`b2ca9397f7e327fd0fbb4e63ff8a595012a1809316eedb0524e603215bf214af`.

This file can be loaded by `FanCurve.from_csv()` at the declared 1500 RPM.
It has no pointwise uncertainty information. The manufacturer’s ±10% general
performance qualification must not be interpreted as five independent
pointwise standard uncertainties or converted directly into an M2 PDF.

## 2. NF-A14x25 G2 PWM — Cybenetics 25FN140A

- Manufacturer: Noctua
- Model: NF-A14x25 G2 PWM
- Test report: [Cybenetics report 25FN140A (PDF)](https://www.cybenetics.com/evaluations/fans/140/pdf/)
- Structured report page: [Cybenetics NF-A14x25 G2 report](https://www.cybenetics.com/evaluations/fans/140/ch/)
- Lab ID: NC14000140
- Test date: 2024-10-14
- Report issue date: 2024-10-15
- Test apparatus: Long Win LW-9266
- Measurement basis: static pressure, airflow in CFM
- Detailed raw records: 72 (nine PWM settings × eight points)

`data/fan_curves/noctua_nf_a14x25_g2_cybenetics_25FN140A_raw.csv`
transcribes Section E's detailed measurement tables in report order. The CSV
columns are:

- `source_row_index`: sequential record order across the nine tables;
- `pwm_percent`: commanded PWM setting;
- `point_in_setting`: row order within one PWM table;
- `flow_cfm`: reported airflow (CFM);
- `static_pressure_mmaq`: reported static pressure (mmAq);
- `fan_speed_rpm`: reported point-level RPM;
- `current_a`: reported current (A);
- `power_w`: reported electrical power (W).

Raw CSV SHA-256:
`1a7266bafe0bb1acf3e2337f01b18735ab9d3585f193e5c58b5184008c132d8d`.

The nine source-table operating envelopes are:

| PWM | Max flow (CFM) | Max pressure (mmAq) | RPM range | Max power (W) |
|---:|---:|---:|---:|---:|
| 20% | 16.86 | 0.06 | 305–307 | 0.13 |
| 30% | 23.60 | 0.22 | 452–455 | 0.22 |
| 40% | 33.43 | 0.38 | 604–609 | 0.34 |
| 50% | 43.44 | 0.63 | 752–757 | 0.52 |
| 60% | 52.04 | 0.84 | 904–911 | 0.80 |
| 70% | 63.68 | 1.19 | 1060–1068 | 1.19 |
| 80% | 73.53 | 1.62 | 1209–1222 | 1.70 |
| 90% | 83.83 | 2.08 | 1360–1371 | 2.45 |
| 100% | 94.59 | 2.51 | 1501–1513 | 3.35 |

The detailed 40% table gives 33.43 CFM; the report's Section F summary graphic
labels the same setting 33.42 CFM. The raw CSV uses the Section E detailed P–Q
table value, 33.43 CFM, and does not reconcile the 0.01 CFM source discrepancy.

### Raw anomalies are retained

Eight of the nine detailed curves end at −0.01 mmAq; the 80% PWM curve ends at +0.01 mmAq.
There are also local increases in the measured pressure sequence at:
- 20% PWM: 0.02 → 0.03 mmAq;
- 60% PWM: 0.46 → 0.50 mmAq;
- 90% PWM: 1.10 → 1.13 mmAq;
- 100% PWM: 1.31 → 1.34 mmAq.

These are raw report values. Do not treat −0.01 mmAq as meaningful reverse fan
pressure, but also do not replace it with zero in the raw data. Similarly, do
not smooth away local increases or sort/clip/project the measurements to make
them pass the solver. Keep any future derivation in a separate, reviewed
artifact with point-by-point transformation provenance and residual analysis.

### Uncertainty record and unresolved interpretation

Cybenetics states that expanded uncertainty uses coverage factor `k = 2`,
corresponding to approximately 95% coverage under an assumed normal
distribution, and references JCGM 100:2008 and ISO/IEC 17025:2017.

The report gives:
- airflow expanded-uncertainty equation:
  `U(Q) = 2 * sqrt((1.8200)^2 + (0.0123176 * Q)^2) CFM`,
  stated as valid over 2.4–250 CFM;
- static-pressure expanded uncertainty: ±0.6727 Pa, stated for the apparatus'
  0–20 mmAq range.

The report's table also labels airflow uncertainty as “±1.23176% of reading,”
while the printed equation includes a nonzero 1.8200 CFM term and the worked
examples (±3.69 CFM at 25 CFM, ±4.29 CFM at 92 CFM, ±7.15 CFM at 250 CFM)
are consistent with that equation rather than a simple constant 1.23176%
relative uncertainty. The repository records both the wording and equation;
the apparent presentation inconsistency is unresolved and must not be silently
simplified.

The airflow formula is not stated as valid below 2.4 CFM. In particular, the
zero-flow rows are pressure-curve measurements and must not be assigned an
airflow uncertainty by extrapolating this formula to zero. The pressure
uncertainty is stated over the 0–20 mmAq apparatus range. The report's
uncertainty is not a full source-specific probability model for every
coordinate, so this import does not create an M2 uncertainty sidecar.

## 3. Comparison with Noctua's G2 specification

Noctua's [NF-A14x25 G2 PWM specifications](https://www.noctua.at/en/products/nf-a14x25-g2-pwm/specifications)
give 1500 RPM, 91.58 CFM, 2.56 mmH₂O, 24.8 dB(A), 2.28 W maximum input
power, and 0.19 A maximum input current.

Cybenetics reports 94.59 CFM, 2.51 mmAq, up to 1513 RPM, 32.40 dB(A),
3.35 W, and 0.279 A in the 100% PWM detailed table. These are different
source-specific results. Their differences are retained rather than averaged
or “corrected”; the source documentation does not establish a conversion that
would make them interchangeable.

## 4. Solver and M3 eligibility

- The original NF-A14 manufacturer CSV is eligible for the deterministic
  solver and M3 at 1500 RPM, using `--rpm-scaling-mode none`.
- It is not a measured multi-speed dataset. Do not use affinity-law scaling as
  a substitute for additional manufacturer or laboratory curves without the
  project's explicit similarity/applicability assessment.
- The G2 long-form raw CSV is **not** eligible for `FanCurve.from_csv()` and
  is not used by M3 or M2 in this change. It remains queryable for plotting,
  analysis, and future metrology review.
- The existing P9 curve, its CSV, its provenance, and its M3 baseline remain
  unchanged.
- No measured MI50 duct/system curve is present. Any comparison against the
  current quadratic system reference remains hypothetical screening, not
  installed MI50 performance.

## References

1. Noctua, [NF-A14 PWM specification PDF](https://cdn.noctua.at/media/2aa6498c/Noctua%20NF-A14%20PWM%20Specification.pdf?download=true), performance curve, section 3.2.
2. Cybenetics, [NF-A14x25 G2 PWM test report 25FN140A](https://www.cybenetics.com/evaluations/fans/140/pdf/), sections E and G, report issued 2024-10-15.
3. Noctua, [NF-A14x25 G2 PWM specifications](https://www.noctua.at/en/products/nf-a14x25-g2-pwm/specifications).
