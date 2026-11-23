# Parametric shroud editor and in-browser simulation

`site/` is a static, dependency-free browser application (three.js is loaded
from a pinned CDN URL for the 3D preview only). It combines:

1. **Parametric geometry.** A fan plate with throats and standard screw holes,
   a lofted transition duct, and a straight sleeve that slips over the end of
   the MI50 cooler. Supports 40–140 mm fans, 1–4 fans in a row along the card
   height or thickness, wall/plate thickness, offsets, and fit clearance.
2. **Fabrication exports.**
   - Binary STL: one closed, consistently wound shell (every edge shared by
     exactly two triangles in opposite directions).
   - OpenSCAD: an *independent* CSG model (hull/difference) with a
     Customizer-compatible parameter block.
3. **Operating-point simulation.** A port of
   `analysis/fan_operating_point.py` (same bisection, bounds, and tolerances)
   with the embedded fan curves, optional affinity-law RPM scaling, quadratic
   or tabulated system resistance, and an optional shroud loss
   `K · ½ρv²` evaluated at the sleeve's inner area taken from the geometry.
4. **Acoustic budget.** A first-order SPL budget (identical uncorrelated
   point sources, inverse-square distance loss, energy summation).

## Running it

ES modules need an HTTP server. From the repository root:

```bash
python3 -m http.server 8000
```

Then open <http://localhost:8000/site/>. The documentation links on the page
are relative to the repository root.

Presets can be saved and loaded as JSON (the file also records the geometry
metrics, the simulation result, and the fan-curve SHA-256). **Copy link**
encodes the full state in the URL fragment. The last state is also kept in
the browser's local storage.

## Coordinate system and geometry

All dimensions are in millimetres.

- `x`: airflow direction. The fan plate's fan-side face is at `x = 0`. The
  card's tail end sits at the start of the sleeve.
- `y`: card height.
- `z`: card thickness (slot direction).

The sleeve's inner opening is the cooler inlet plus the fit clearance on each
side. **The cooler inlet height default (100 mm) is an unmeasured
placeholder**, and the 36 mm thickness is the unverified 35–37 mm estimate in
`data/mi50_envelope.json`. Both are badged in the UI, and the editor warns
until the height is changed. Measure your card.

Validation blocks geometry that cannot be built:

- a throat that leaves no 0.5 mm web;
- a throat overlapping the screw holes;
- screw holes cutting into the duct wall;
- values out of range.

It warns about:

- the dual-slot (40 mm) and full-height (111.15 mm) envelopes;
- expanding walls steeper than about 7° (diffuser separation);
- walls steeper than 45° (unsupported overhang when printed fan-plate down).

## Verification

| Check | Where |
|---|---|
| Every valid combination of fan size × count × row axis × offset is watertight with positive (outward) volume | `site/tests/geometry.test.mjs` |
| Default solid volume matches an independent hand calculation (Simpson's rule on the loft) | `site/tests/geometry.test.mjs` |
| JS solver equals the Python solver to 1e-12 relative on 24 cases (P9 Max, NF-A14; 1–3 fans; quadratic and tabulated systems) | `tests/test_site_parity.py` |
| OpenSCAD render of the exported `.scad` has the same volume (within 0.1 %) and bounds as the browser mesh | `tests/test_site_parity.py` (skipped without OpenSCAD) |
| Embedded `site/js/fan_data.js` is regenerated from the source CSVs | `scripts/build_site_data.py --check`, CI |
| Duct loss in series equals a quadratic system with the combined resistance; acoustic identities (+3 dB per doubling of fans, −6 dB per doubling of distance) | `site/tests/solver.test.mjs` |

Run the browser-module tests with:

```bash
node --test site/tests/*.test.mjs
```

After changing a source CSV, regenerate the embedded data with
`python3 scripts/build_site_data.py`.

## Limitations

- The simulation is reduced-order. Bulk-air ΔT is not a GPU, HBM, or VRM
  temperature, and nothing here is CFD.
- The default system resistance (2 mmH₂O at 50 CFM) is the README's
  hypothetical example, not an MI50 measurement. Enter a measured table for
  meaningful results.
- The shroud loss coefficient defaults to 0 (excluded). No correlation is
  built in; enter a value you can justify.
- Wall thickness is applied in each cross-section plane, so on tapered walls
  the true normal thickness is slightly thinner (by cos of the wall angle).
- Fan frames are modelled as square plates only. Fan-to-fan interaction and
  inlet obstruction are not modelled.
