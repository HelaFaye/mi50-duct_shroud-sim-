# Simulation status and next calibration steps

## Implemented reduced-order flow model

The project now includes `analysis/fan_operating_point.py`, which calculates
an operating point for one fan or an array of identical fans in parallel. It
interpolates a supplied P–Q curve, models the duct/heatsink as a quadratic
system resistance, and solves for the fan/system pressure intersection.

The supplied ARCTIC P9 Max curve is a chart digitization with approximate
intermediate points. The example system curve used in the README is a
hypothetical sensitivity input, not an MI50 measurement.

See [`docs/FAN_OPERATING_POINT_MODEL.md`](../docs/FAN_OPERATING_POINT_MODEL.md)
for the model contract and example CLI invocation.

## Still not CFD or conjugate heat transfer

The reduced-order model does not resolve velocity fields, recirculation,
branch maldistribution, bypass leakage, turbulence, fin-scale pressure loss,
solid conduction, contact resistance or local GPU/HBM/VRM temperatures. The
ideal bulk-air temperature rise is an energy-balance estimate only.

## Required data before predictive use

1. A numeric manufacturer or measured fan P–Q curve at the intended RPM/PWM.
2. MI50 heatsink pressure drop versus flow, measured on the actual heatsink or
   represented by a validated porous-media fit.
3. Duct and fitting losses or a calibrated system pressure/flow point.
4. Leakage/bypass measurement and flow-distribution information.
5. For thermal predictions: reliable power partition, heatsink/base geometry,
   material properties, thermal-interface/contact resistance and inlet ambient.

Once these are available, fit the system curve and check it against a second
pressure/flow point. Then compare the reduced-order result with flow-only CFD;
add conjugate heat transfer only after the fluid and solid domains and boundary
conditions are defensible.
