# AMD Radeon Instinct MI50 — Mechanical and thermal reference envelope

Research snapshot: 2026-11-20. Dimensions in this document are classified by evidence quality. Do not silently promote an estimate to a measured value.

## Coordinate convention

For the cooling CAD, use a consistent card coordinate system:

- **X / length:** along the PCB from the I/O bracket toward the distal card end.
- **Y / card height:** from the PCIe edge-finger datum toward the card's top edge.
- **Z / thickness:** normal to the PCB, across the two-slot envelope.

Keep the **PCB envelope**, **original shroud envelope**, **deshrouded heatsink envelope**, and **replacement shroud envelope** as separate solids/parameter groups. The dimensions below do not describe one interchangeable bounding box.

## Established and provisional dimensions

| Feature | Working value | Evidence status | Use in CAD |
|---|---:|---|---|
| Board length | 267 mm | **AMD specification**: 10.5 in (267 mm) | Use as nominal board length; still compare the exact board edge in photos/STL. |
| Card height | 111.15 mm | **PCIe CEM form-factor value**, not an MI50-specific measured drawing. AMD says “Full Height” but does not publish 111.15 mm on its MI50 page. | Use as a provisional PCB envelope. Preserve datum and allow adjustment. |
| Slot width / thickness | approx. 39–40 mm | **Form-factor inference / nominal dual-slot envelope**, while AMD specifies “Double Slot” rather than a numerical assembled thickness. | Use as an outer packaging constraint only; do not use as the deshrouded heatsink thickness. |
| Original stamped cover thickness | approx. 0.5 mm | **Unverified estimate**; the teardown confirms a removable metal outer shroud and six small screws but does not report sheet thickness. | Keep out of hard-fit constraints until measured. |
| Deshrouded cooler thickness | approx. 35–37 mm | **Provisional estimate** from community teardown/design context; not a dimension published by AMD or the teardown author. | Sensitivity range for preliminary packaging only. Measure both black heatsink and silver fin-stack extrema separately. |
| Outer-shroud fasteners | 6 screws | **Owner teardown report** | Useful for modeling original cover retention; hole coordinates and thread size still need measurement. |
| Vapor-chamber fasteners | 4 spring-loaded screws | **Owner teardown report** | Establishes a four-point retention pattern exists; exact coordinates and standoff heights remain unknown. |
| Vega 20 package footprint | 47.5 × 47.5 mm (candidate only) | **User-supplied, unverified**. The public 47.3 mm report concerns Vega 10 / Radeon Vega Frontier Edition, not MI50 Vega 20. No MI50-specific package outline tying FCBGA-1933 to this dimension has been located. | Do not use as a hard CAD or thermal-contact dimension. Keep separate from vapor-chamber footprint and GPU/HBM heat-source geometry. |
| Fin air gap | 1.0–1.5 mm | **Engineering estimate only** | Sensitivity range for early porous-media / reduced-order models; not a production CFD input until measured. |
| Fin thickness | 0.3–0.5 mm | **Engineering estimate only** | Same as above. Do not infer channel area from the estimate without uncertainty bounds. |

## Audit of the additional dimensions supplied on 2026-11-20

The supplied dimension sheet is a useful collection of working hypotheses. Public evidence supports some entries, but not all of the stated precision. Use the following evidence split:

| Supplied claim | What public sources establish | Current modelling status |
|---|---|---|
| Overall length: 267 mm | AMD explicitly specifies 10.5 in (267 mm). | **Manufacturer-specified**; accepted nominal board length. |
| Overall height: 111.15 mm | AMD says “Full Height”; the numeric 111.15 mm comes from PCIe CEM form-factor material, not an MI50-specific measured drawing. | **Form-factor nominal**; retain as adjustable envelope, not measured PCB edge-to-edge size. |
| Overall thickness: 39–40 mm | AMD says “Double Slot,” but gives no numeric assembled thickness. | **Packaging estimate**; measure the actual card/cover or use the applicable PCIe keepout drawing. |
| Outer cover: ~0.5 mm stamped aluminum | Teardown confirms a removable outer shroud; no sheet gauge is stated. | **Unverified estimate**; do not use as a hard offset or wall thickness. |
| Six M2 cover screws | Teardown explicitly reports six small screws. It does not identify M2 thread size. | **Count supported; thread size unverified.** The model must not assume M2 without a screw/receiver measurement. |
| Deshrouded thickness: 35–37 mm | Teardown photos show the exposed heatsink and silver vapor-chamber fin field but contain no calibrated measurement. | **Unverified estimate**; separately measure the maximum Z-height of the black and silver fin fields. |
| GPU package: 47.5 × 47.5 mm, “FCBGA-1933” | A commonly cited 47.3 mm package source is specifically about the Radeon Vega Frontier Edition (Vega 10), not MI50's Vega 20. No MI50-specific package outline tying FCBGA-1933 to 47.5 mm was found. | **Unverified candidate only.** Do not build a definitive thermal-contact geometry from this value. Confirm package outline and GPU/HBM coordinates independently. |
| Fin gap: 1.0–1.5 mm; fin thickness: 0.3–0.5 mm | No caliper values or dimensioned drawing found. Photos show dense fin fields but are not calibrated metrology. | **Engineering sensitivity ranges only.** Sweep in reduced-order analysis; do not treat as actual fin geometry. |
| Two visually distinct fin regions | Teardown image shows a long black heatsink fin field and a separate silver vapor-chamber fin field. | **Qualitatively supported.** Exact heights, pitch, thickness, airflow direction and overlap remain unmeasured. |

**Important package correction:** the 47.3 mm source currently cited in older notes is about the 2017 Radeon Vega Frontier Edition, whose GPU is Vega 10. It is not evidence that the MI50's Vega 20 package is 47.5 mm square. Keep the 47.5 mm value as a user-supplied placeholder only until a Vega 20/MI50 package drawing or reliable measurement is found.

## What the public teardown actually establishes

Diego Strebel's 25 June 2025 teardown reports:

- six small screws retain the original outer shroud;
- removing it exposes a long black heatsink spanning the card;
- the GPU die is cooled by a copper vapor chamber, visually identified by its silver fins;
- four screws retain the vapor chamber to the GPU die/backside spring hardware;
- the black heatsink has additional fasteners hidden by the backplate;
- VRM thermal pads need care during disassembly; the author reports that 2 mm replacement pads worked in their case.

These observations support a **two-region cooler model** (black heatsink plus vapor-chamber fin stack) and separate thermal interfaces for GPU and VRM areas. The article does not provide a dimensioned drawing, fin pitch, fin thickness, vapor-chamber footprint, or pressure-drop curve.

## Interpretation corrections and modelling cautions

1. AMD's MI50 support specification explicitly states **300 W peak TDP**, **passive cooling**, **full-height**, **double-slot**, and **267 mm board length**. It does not explicitly list a 111.15 mm measured height or a 39–40 mm measured thickness. Those come from the PCIe form factor / nominal slot envelope, not a card-specific AMD mechanical drawing.
2. PCIe CEM revisions have slightly different published full-height values and definitions. The familiar 111.15 mm value appears in earlier CEM material; later revisions may show 111.28 mm. For an MI50-era board, 111.15 mm is a sensible nominal envelope, but the exact card and bracket must govern final fit.
3. The supplied “FCBGA-1933” label and 47.5 × 47.5 mm body size remain unverified for Vega 20. The commonly cited 47.3 mm package source is explicitly about Vega 10 / Radeon Vega Frontier Edition, so it must not be used as direct MI50 evidence.
4. The package footprint is not the vapor-chamber block footprint. The vapor chamber contacts/spreads heat over the GPU/HBM assembly and may have a larger outline, stepped geometry, and separate fin stack. Model those as distinct features.
5. The phrase “two-tier fin profile” is supported qualitatively by the teardown photo: a silver vapor-chamber fin stack is visibly distinct from the long black heatsink. The exact fin pitch, fin thickness, height offsets, and relative open areas are not published.
6. The 1.0–1.5 mm fin-gap and 0.3–0.5 mm fin-thickness ranges are plausible starting hypotheses, not facts. Early CFD should sweep these values and report sensitivity; high-fidelity CFD needs a calibrated geometry or a measured porous-resistance curve.

## CAD parameter set to use now

Use the following as an editable, provenance-tagged envelope, not as a single rigid card solid:

- `board_length = 267.0` (AMD-published)
- `board_height = 111.15` (PCIe nominal; adjustable)
- `slot_envelope_thickness = 40.0` (nominal dual-slot; adjustable)
- `original_cover_thickness = 0.5` (estimate; do not subtract automatically from other dimensions)
- `deshrouded_cooler_thickness_min = 35.0`
- `deshrouded_cooler_thickness_max = 37.0`
- `vega_package_footprint = 47.5` (unverified user-supplied placeholder only; do not use as a hard constraint)
- `fin_gap_min = 1.0`, `fin_gap_max = 1.5` (uncertain)
- `fin_thickness_min = 0.3`, `fin_thickness_max = 0.5` (uncertain)

Do not use this provisional set to make a final-fit STL without physical verification. The uploaded MI50 shroud STL's 120.00 × 132.29 × 78.43 mm mesh envelope is the envelope of that **shroud reference mesh**, not the card PCB or factory cooler.

## Best next public-source and measurement targets

1. Find a PCIe CEM mechanical drawing appropriate to the MI50's design era and preserve the exact revision in the evidence record.
2. Find a MI50 board-revision-specific drawing, service manual, or original cooler part number. No authoritative complete MI50 card/heatsink STEP model has been located yet.
3. Examine the teardown's original-resolution photographs with a known scale reference; use pixel ratios only for preliminary estimates and record image perspective uncertainty.
4. Locate a surviving original shroud/cooler for caliper measurement. Prioritize board mounting holes, fan/duct attachment plane, inlet/outlet boundaries, fin pitch/thickness, fin height and clear free-flow area.
5. Measure the two distinct fin regions separately: black heatsink fins and silver vapor-chamber fins. Their channel areas and flow resistances may differ materially.

## Sources

- AMD MI50 16 GB specifications: <https://www.amd.com/en/support/downloads/drivers.html/accelerators/instinct/instinct-mi-series/instinct-mi50.html>
- AMD MI50 32 GB specifications: <https://www.amd.com/en/support/downloads/drivers.html/accelerators/instinct/instinct-mi-series/instinct-mi50-32gb.html>
- PCI Express Card Electromechanical Specification, older revision excerpt showing the 111.15 mm full-height maximum: <https://studylib.net/doc/28414113/pci-express-cem-r2.0-cb>
- PCI Express CEM Rev. 4.0 excerpt showing dual-slot component-height constraints: <https://pdfcoffee.com/pci-express-cem-specification-revision-40-pdf-free.html>
- Diego Strebel, MI50 teardown (25 June 2025): <https://diegostrebel.com/posts/instinct_mi_50/>
- Exposed MI50 cooler photo: <https://diegostrebel.com/images/InstinctMI50/MI50_noshroud.jpg>
- MI50 vapor chamber photo: <https://diegostrebel.com/images/InstinctMI50/MI50_Cooler.jpg>
- Vega-family 47.3 mm package report (Radeon Vega Frontier Edition, not MI50): <https://overclock3d.net/news/gpu-displays/amd-radeon-vega-frontier-edition-pcb-exposed/>
- MI50 replacement shroud project: <https://github.com/roackim/mi50-92mm-shroud>
- MI50/MI25/MI60 replacement shroud listing: <https://cults3d.com/en/3d-model/tool/radeon-instinct-mi25-mi50-mi60-full-shroud-replacement>
