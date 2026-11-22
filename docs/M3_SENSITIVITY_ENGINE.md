# M3 deterministic operating-point sensitivity engine

_Status: initial implementation committed as `5919163` and CI-verified. Follow-up scenario-failure-isolation hardening passes 87/87 local tests and awaits its own commit and CI run._

## Purpose and scope

`analysis/operating_point_sensitivity.py` evaluates explicit deterministic combinations of fan RPM, identical parallel-fan count, and system-resistance multiplier. It calls the existing `analysis/fan_operating_point.py` solver; it does not modify that solver's API or CLI.

The first increment is a scenario tool, not an uncertainty engine. It reports each scenario against an explicit baseline and retains failures rather than extrapolating or silently dropping scenarios. Probabilistic comparisons remain outside M3 until M2 is accepted for that use.

## Input requirements

- One single-fan P–Q CSV at a declared `--reference-rpm`.
- An explicit list of RPM values, fan counts, and positive system-resistance multipliers.
- The baseline fan count must be included in the fan-count list. The RPM list must include the reference RPM, and the resistance list must include `1.0`.
- Either a tabulated system curve or both a quadratic screening reference pressure and reference flow.

For the currently available repository data, the P9 Max curve is an approximate manual digitization at 4300 RPM. The MI50 system-curve template is header-only. Therefore, no measured MI50 system-curve sweep is currently possible. A quadratic reference such as 2.0 mmH2O at 50 CFM is a hypothetical screening input, not measured MI50 resistance.

## RPM treatment

The default `--rpm-scaling-mode none` permits only the declared reference RPM. A different RPM list is rejected unless the caller explicitly selects `--rpm-scaling-mode affinity-law`.

The affinity-law mode derives a target-speed curve from the reference curve using, at constant density and fixed geometry:

\[
Q_2/Q_1=N_2/N_1, \qquad \Delta p_2/\Delta p_1=(N_2/N_1)^2.
\]

Every derived scenario is labeled `affinity_law_derived`. The report records the speed ratio and assumptions. This is not a measured multi-speed fan curve or a guarantee of dynamic similarity. The applicability review must include geometric, kinematic, and dynamic similarity, density/compressibility, Reynolds number, and tip-speed Mach number. Using the same fan at another RPM does not by itself establish dynamic similarity. The reference P9 digitization remains approximate, so scaled results inherit its data-quality limitations. See [ANSI/AMCA 99-25, *Standards Handbook*, section 4](https://www.amca.org/assets/resources/public/resources/ansi-amca-99-25-standards-handbook.pdf), for fan-law similarity requirements.

No electrical input power is calculated. The cubic speed relationship is not applied because measured electrical or shaft-power data and a motor/fan efficiency model are absent. RPM, electrical input, and system resistance remain separate quantities.

## System-resistance treatment

- For the quadratic model, a multiplier scales the reference pressure at fixed reference flow, which multiplies the fitted `K` by the same factor.
- For a tabulated system curve, the multiplier scales every pressure ordinate uniformly while preserving its flow coordinates and curve shape. This is an explicit shape-preserving scenario assumption, not a claim that an arbitrary geometry change produces that exact curve.

The tabulated curve still uses the deterministic solver's no-extrapolation behavior. An undersized curve or an invalid per-scenario curve transformation produces a failed scenario with a reason; the tool does not extend the curve or abort otherwise valid scenarios.

## Baseline comparison and report

The baseline is the scenario at reference RPM, the declared baseline fan count, and resistance multiplier `1.0`. The tool refuses to produce relative comparisons if that baseline does not solve.

Every solved row reports total flow, per-fan flow, fan/system pressure, and ideal bulk-air temperature rise, plus absolute and relative differences from baseline. A zero baseline output has an undefined relative percentage, serialized as `null`. Failed rows retain the solver error and a categorized reason. The JSON report includes the input curve hash, solver source hash, RPM transformation assumptions, fixed thermal inputs, and scenario/failure counts.

The temperature output remains an ideal bulk-air energy balance; it is not a GPU junction, HBM, VRM, or heatsink temperature prediction. Parallel fans are assumed identical and equally loaded. Fan interaction, motor electrical input, transients, and temperature-dependent fan behavior are not modeled.

## CLI example

The following is an illustrative screening run only. It deliberately uses a hypothetical quadratic system reference; do not treat the results as measured MI50 performance.

```bash
python3 -m analysis.operating_point_sensitivity \
  --fan-curve data/fan_curves/arctic_p9_max_4300rpm_digitized.csv \
  --reference-rpm 4300 \
  --rpms 4300,4000,3600 \
  --rpm-scaling-mode affinity-law \
  --fan-counts 1,2,3 \
  --baseline-fan-count 2 \
  --system-resistance-multipliers 0.5,0.75,1.0,1.5,2.0 \
  --system-pressure-mmh2o 2.0 \
  --system-reference-flow-cfm 50 \
  --fan-curve-provenance approximate_manual_digitization \
  --output results/m3_sensitivity_screening.json
```

Omit `--rpm-scaling-mode affinity-law` and use only `--rpms 4300` to hold fan speed at the reference curve. When a measured system curve becomes available, replace the two quadratic reference options with `--system-curve <path>`; the current header-only template cannot yet be solved.

## Verification gates

- Synthetic tests cover affinity scaling, explicit opt-in, baseline requirements, fan-count and resistance trends, tabulated-curve pressure scaling, deterministic output, and baseline comparisons.
- Initial commit `5919163` passed 85/85 local tests and GitHub Actions run [45011421134](https://github.com/HelaFaye/mi50-duct_shroud-sim-/actions/runs/45011421134) on Python 3.10, 3.12, and 3.14.
- Follow-up scenario-failure isolation adds two regression tests. The resulting 87-test suite passes locally on Python 3.14.7; the follow-up still requires CI verification.
- Software tests establish implementation behavior only. They do not validate the P9 digitization, the affinity-law similarity assumption, the hypothetical resistance reference, or installed MI50 performance.
