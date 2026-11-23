# Fan electrical interpolation model

_Status: project implementation for a numerical transcription of ARCTIC P9 Max electrical PWM data. The official source is linked below; the original PDF is not bundled in this repository._

## Scope and source contract

`analysis/fan_electrical.py` is separate from the aerodynamic P–Q solver and the non-monotonic measured-fan intersection solver. Its input is a long-form electrical table with columns:

```csv
source_table_row,pwm_percent,supply_voltage_v,fan_speed_rpm,current_a,power_w
```

Each supply voltage is treated as a separate table. The P9 source contains 20 rows at each of 12 V, 7 V, and 5 V. The model does not interpolate between supply voltages.

## Interpolation contract

RPM is the independent coordinate. Current and published power are independently interpolated linearly between adjacent distinct RPM observations. No extrapolation is allowed. Exact RPM observations are reported as source observations rather than interpolations.

Several PWM rows can share one RPM because the source reports a speed plateau. Such rows are consolidated only when their current and power values agree exactly; all original PWM settings and source-table row numbers remain attached to the consolidated coordinate. Conflicting telemetry at the same voltage and RPM is rejected as ambiguous rather than averaged.

The model preserves source-reported current and power independently. It does not enforce `P = V I`, recompute power, or replace displayed precision. For example, the source's 7 V low-PWM observation is retained as 0.00 A and 0.02 W.

## Array estimates

For `N` identical fans connected in parallel to the same supply, array current and power estimates are the per-fan interpolated current and power multiplied by `N`. This assumes each fan is operating at the requested RPM. It is not a multi-fan measurement and does not model wiring losses, controller losses, start-up current, transient behavior, or fan-to-fan variation.

## Reproduction

The local source transcription is `data/fan_curves/arctic_p9_max_pwm_electrical.csv`; its audited SHA-256 is `ed98b8526bc711b0b8ec15cf588784e794c0db62f986fd9e0c7bab5e2e4654f7`. The official source is [ARCTIC: PWM Curve, 4300 RPM, P9 Max (2025-01-17)](https://support.arctic.de/products/p9-max/techdocs/PWM%20Curve%2C%204300%20RPM%2C%20P9%20Max%20%282025-01-17%29.pdf). Its footer is marked `Confidential`; that classification is retained here as provenance metadata. The source PDF SHA-256 is `9a7ea47c8965cfd303a347c03e10784ef83eeb26afcda00b65ca04e09608b41f`. The PDF itself is linked, not bundled.

Example local invocation:

```bash
python3 -m analysis.fan_electrical \
  --measurement-csv data/fan_curves/arctic_p9_max_pwm_electrical.csv \
  --voltage-v 12 \
  --rpm 4300 \
  --fan-count 2 \
  --json
```

The 4300 RPM, 12 V per-fan estimate is approximately 0.285490196 A and 3.455602241 W. It is interpolated between the 4119 RPM and 4476 RPM source observations, not measured at exactly 4300 RPM.

## Limitations

- No interpolation across supply voltage.
- No RPM extrapolation.
- No inference of power from voltage multiplied by current.
- No use of this electrical dataset as an aerodynamic curve.
- No inference of start-up, stall, transient, or thermal behavior from steady PWM table values.
- The electrical values are transcribed from the cited manufacturer source, not measurements performed by this project.
