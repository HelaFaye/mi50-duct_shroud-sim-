# MI50 supplied dimension-sheet claim audit

Date reviewed: 2026-11-20  
Scope: the dimension list and screenshot supplied during the MI50 active-cooling research discussion.

This is an evidence audit, not a new mechanical drawing. The source sheet is useful as a provisional input list, but some numerical values are generic form-factor values or estimates rather than measurements of an MI50 assembly.

## Claim-by-claim status

| Claim from supplied sheet | Evidence found | Decision |
|---|---|---|
| 267 mm overall length | AMD's MI50 product specification explicitly states 10.5 in (267 mm). | Accept as the nominal board length. |
| 111.15 mm overall height | AMD lists “Full Height”; the numerical dimension is from PCIe CEM form-factor material rather than an MI50 mechanical drawing. | Use as a nominal adjustable full-height envelope only. |
| 39–40 mm total thickness | AMD lists “Double Slot,” not an exact card measurement. | Use only as a slot-class packaging assumption. |
| ~0.5 mm cover gauge | Teardown confirms a removable outer metal shroud but does not measure the sheet. | Keep as an unverified estimate. |
| Six M2 outer-cover screws | Teardown confirms six small outer-shroud screws. It does not specify the thread. | Screw count supported; M2 thread claim unverified. |
| 35–37 mm deshrouded thickness | No calibrated measurement located. | Keep as a user-supplied estimate; measure separately to black fin and silver fin extrema. |
| 47.5 × 47.5 mm FCBGA-1933 package | No Vega 20/MI50-specific package outline found. The often-cited 47.3 × 47.3 mm article is about Vega 10 / Radeon Vega Frontier Edition. | Do not treat as confirmed MI50 package geometry. Keep placeholder only. |
| 1.0–1.5 mm fin gap and 0.3–0.5 mm fin thickness | No dimensioned source or calibrated teardown measurement found. | Sensitivity estimates only. |
| Two distinct fin regions | Visible in teardown imagery: long black heatsink fin field and silver vapor-chamber fin field. | Qualitatively supported; dimensions and exact spatial relationships remain unknown. |

## Primary and secondary references

1. AMD MI50 16 GB specifications: <https://www.amd.com/en/support/downloads/drivers.html/accelerators/instinct/instinct-mi-series/instinct-mi50.html>
2. AMD MI50 32 GB specifications: <https://www.amd.com/en/support/downloads/drivers.html/accelerators/instinct/instinct-mi-series/instinct-mi50-32gb.html>
3. Diego Strebel's MI50 teardown (25 June 2025): <https://diegostrebel.com/posts/instinct_mi_50/>
4. Exposed cooler photograph: <https://diegostrebel.com/images/InstinctMI50/MI50_noshroud.jpg>
5. Removed vapor-chamber photograph: <https://diegostrebel.com/images/InstinctMI50/MI50_Cooler.jpg>
6. Vega Frontier Edition / Vega 10 package reporting (not MI50 evidence): <https://overclock3d.net/news/gpu-displays/amd-radeon-vega-frontier-edition-pcb-exposed/>
7. Amkor general package index (not an MI50 package identification): <https://amkor.com/wp-content/uploads/2019/06/Amkor-Line-Card-JP.pdf>

## CAD implications

- Keep board length, board height, slot envelope, original cover, and deshrouded heatsink as separate parameter groups / solids.
- Do not subtract a presumed 0.5 mm sheet gauge from the 40 mm slot envelope to infer the heatsink height.
- Do not place M2 bosses or screw holes solely from the screw-count report. Hole centers and thread identity are separate unknowns.
- Model the black heatsink and silver vapor-chamber fin regions as separate thermal/flow zones.
- For first-pass CFD, test a range of fin resistance values. Do not instantiate the estimated fin gap and thickness as literal fin geometry until calibrated.
- Keep the Vega package placeholder separate from the vapor chamber contact patch and from the four HBM stacks.

## Measurements that would close the highest-impact gaps

1. Overall deshrouded Z-height to the black-fin maximum and silver-fin maximum.
2. Cover sheet thickness measured with calipers away from bends/flanges.
3. Outer-cover screw diameter, pitch, head type, and hole coordinates.
4. Fin pitch and thickness for each of the two fin fields, plus fin depth and flow direction.
5. Vapor-chamber planform, contact footprint, thickness and fin-field dimensions.
6. GPU/HBM package outline and the location/size of each heat-generating region.
