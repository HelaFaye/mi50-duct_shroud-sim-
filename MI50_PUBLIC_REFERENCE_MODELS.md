# MI50 public mechanical references and design precedents

Research snapshot: 2026-11-20. This records what public sources actually establish, separating manufacturer facts, author-reported prototype observations, community claims, and inference.

## 1. Manufacturer baseline: both official MI50 SKUs

AMD's official MI50 16GB and 32GB pages both list Vega20, 3,840 stream processors / 60 compute units, 300 W peak TDP, passive cooling, PCIe add-in card, Full Height, 267 mm board length, and Double Slot.

- [AMD MI50 16GB specifications](https://www.amd.com/en/support/downloads/drivers.html/accelerators/instinct/instinct-mi-series/instinct-mi50.html)
- [AMD MI50 32GB specifications](https://www.amd.com/en/support/downloads/drivers.html/accelerators/instinct/instinct-mi-series/instinct-mi50-32gb.html)
- [AMD accelerator specification table](https://www.amd.com/en/products/specifications/accelerators.html)

This establishes a common published product envelope, not identical PCB outline, component placement, HBM stack height, heatsink, vapor chamber, shroud, fasteners, or cooler compatibility.

### Conflicting community report

The [evilJazz MI50 32GB VBIOS research](https://gist.github.com/evilJazz/14a4c82a67f2c52a6bb5f9cea02f5e13) reports an original-AMD 32GB PCB and a simplified Chinese PCB, distinguished by reported ROP/TMU counts and backplate sticker patterns. It also claims 64 CUs / 4,096 shaders for the original 32GB card, which conflicts with AMD's official 32GB MI50 page (60 CUs / 3,840 stream processors). Treat the PCB distinction as an unresolved community lead, not a verified mechanical variant. Its listed VBIOS P/Ns are not cooler part numbers.

## 2. Best public teardown: 16GB specimen only

[Diego Strebel's MI50 teardown, 25 June 2025](https://diegostrebel.com/posts/instinct_mi_50/) explicitly discusses a genuine 16GB MI50. The author reports six small outer-shroud screws, a long black heatsink, a copper vapor chamber with silver fins over the GPU, four vapor-chamber retaining screws, hidden black-heatsink fasteners under the backplate, and VRM thermal pads. The author's 2 mm replacement-pad comment is a repair anecdote, not a factory specification.

- [MI50 without outer shroud](https://diegostrebel.com/images/InstinctMI50/MI50_noshroud.jpg)
- [Removed vapor chamber](https://diegostrebel.com/images/InstinctMI50/MI50_Cooler.jpg)

The photograph shows two visually distinct finned regions. It does not establish calibrated fin pitch, thickness, channel depth, exact relative Z-height, overlap, airflow direction, or hole coordinates. The same author distinguishes genuine MI50 16GB (`1002:66A1`) from a Radeon-VII-like Chinese card (`1002:66AF`).

## 3. Public MI50 shroud prototypes

### 3.1 Single 92 mm axial fan — MIT OpenSCAD

[roackim/mi50-92mm-shroud](https://github.com/roackim/mi50-92mm-shroud) is a three-part OpenSCAD design for a 92 × 92 × 25 mm fan; the author recommends ARCTIC P9 Max. It separates fan mount, heatsink duct, and ramp, and says the duct is intended to force air through the fins. Importantly, the README explicitly says some GPU M2 mounting-hole placement is not yet a perfect fit. License: MIT. This is the best editable-CAD precedent found, but not a factory drawing or validated thermal model.

### 3.2 Triple slim fans — 80/90 mm listing discrepancy

[Printables triple slim MI50 shroud](https://www.printables.com/model/1413245-amd-radeon-instinct-mi50-triple-slim-80mm-fan-shro) has a title saying 80 mm, body text saying 90 mm, and a parts list identifying ARCTIC P8 Slim (80 mm). The author reports using four of six original shroud mounting holes, 4 × M2 × 5 mm replacement screws, and a finished shroud height of 55 mm. The fans are powered/controlled from a motherboard header or fan controller, not the card. The author says their specimen is 16GB. License: CC BY-NC-SA 4.0. Resolve the fan-size discrepancy from the actual downloadable model and fan dimensions before adopting its geometry. No controlled thermal/acoustic data is provided.

### 3.3 Single 120 mm fan with 90-degree routing

[Thingiverse MI50/MI25 120 mm shroud](https://www.thingiverse.com/thing:7179158), also indexed at [3DGo](https://3dgo.app/models/thingiverse/7179158), uses a curved route to place the fan above/below the card and reduce lengthwise clearance. The author reports that one 120 mm fan was not sufficient under load and advises monitoring temperatures. This is useful negative prototype evidence, but no controlled workload, ambient, RPM, junction temperature, flow, or pressure data is supplied. The index reports CC BY-SA; verify the original listing before redistribution.

### 3.4 AVC BA10033B12H centrifugal blower

[Printables BA10033B12H MI50 shroud](https://www.printables.com/model/1229329), also indexed by [STLFinder](https://www.stlfinder.com/model/shroud-for-amd-instinct-mi50-workstation-gpu-and-ba10033b12h-bbq-blower-fan-KMlYMRCi/5856175/), identifies an exact blower family. A related design discussion describes a 10-degree sloped transition and reports an earlier U-turn arrangement had 3.1–3.2 m/s at the GPU bracket. These are author-reported observations, not controlled comparative CFD or thermal results. The indexed record says CC BY; verify original listing terms. Match the exact suffix to the fan label and manufacturer curve.

## 4. Conclusions supported by these sources

- Public MI50 conversions exist for 92 mm axial, triple slim axial, 120 mm bent duct, and BA10033B12H centrifugal blower configurations.
- Some conversions reuse four of the original six shroud holes.
- At least one 92 mm OpenSCAD project warns its GPU mounting holes are not yet perfectly positioned.
- One 120 mm prototype author reports insufficient cooling under load. This is anecdotal and does not establish that every 120 mm design fails.
- A shallow-angle blower transition is worth testing against a sharp U-turn, but no controlled A/B dataset was found.

These sources do not establish minimum CFM, minimum duct section, factory hole coordinates, fin pitch/thickness, heatsink pressure drop, identical 16GB/32GB internals, or controlled acoustic/thermal superiority.

## 5. CAD policy

1. Keep AMD's 267 mm / Full Height / Double Slot as common published packaging constraints.
2. Keep teardown-derived internal geometry under a 16GB specimen identity.
3. Keep 32GB internal geometry unknown until a direct teardown or dimensioned source is found.
4. Treat community PCB-variant reports as unresolved identity clues only.
5. Treat third-party shrouds as prototype precedents; check actual CAD/STL, dimensions, and license before reuse.
6. Do not adopt the triple-slim model's 80/90 mm claim until resolved.
7. Keep reported cooling outcomes anecdotal; do not use them as CFD boundary conditions.

## 6. Remaining public-source gaps

- Direct 32GB MI50 teardown with cover and cooler removed.
- Authoritative MI50 PCB/heatsink STEP/IGES or service drawing.
- Original cover and heatsink mounting coordinates.
- Calibrated orthogonal photographs of 32GB PCB/cooler.
- Original downloadable CAD/STL for each public conversion, for geometric comparison.
- Controlled fan-conversion temperatures, RPM, ambient, airflow and pressure measurements.
- Actual heatsink fin-channel pressure-drop data.
