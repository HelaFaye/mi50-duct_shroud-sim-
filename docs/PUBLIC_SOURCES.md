# Public-source research register

Research snapshot: 2026-11-20. This is a living evidence register, not a substitute for dimensional inspection or fan testing. Each claim below is tagged by evidence quality.

## Evidence labels

- **Primary specification** — AMD or fan manufacturer technical documentation.
- **Manufacturer product listing** — manufacturer/product-channel listing; useful but the exact suffix and revision still need verification.
- **Measured owner report** — a public user report with a stated setup. Useful for sanity checks, not a controlled comparative benchmark.
- **Design precedent** — published CAD/printable design. Geometry and fit claims are not automatically verified for our card.
- **Unresolved** — no sufficiently authoritative public value located so far.

## MI50 board and cooler

### AMD product specifications — primary

- MI50 16 GB: <https://www.amd.com/en/support/downloads/drivers.html/accelerators/instinct/instinct-mi-series/instinct-mi50.html>
- MI50 32 GB: <https://www.amd.com/en/support/downloads/drivers.html/accelerators/instinct/instinct-mi-series/instinct-mi50-32gb.html>
- Published common envelope: passive cooling, 300 W peak TDP, full-height, double-slot, 267 mm board length, two 8-pin power connectors. The public specs reviewed here do not provide a dimensioned heatsink drawing or a complete board STEP model.

### MI50 mechanical envelope and PCIe form-factor context

- AMD's MI50 support page explicitly gives **10.5 in (267 mm) board length**, **Full Height**, **Double Slot**, **Passive** cooling and **300 W Peak** TDP. It does not publish a numerical 111.15 mm board height, a measured 39–40 mm assembled thickness, a shroud sheet thickness, or a heatsink mechanical drawing: <https://www.amd.com/en/support/downloads/drivers.html/accelerators/instinct/instinct-mi-series/instinct-mi50.html>
- The familiar **111.15 mm** figure is found in older PCIe CEM material as the standard-height card maximum. PCIe CEM revisions differ slightly in some dimensions, so it is recorded as a form-factor nominal rather than an MI50-specific measurement: <https://studylib.net/doc/28414113/pci-express-cem-r2.0-cb>
- A dual-slot card's exact assembled Z-thickness depends on the card and the applicable CEM keepout/envelope. AMD lists only “Double Slot”; use 39–40 mm as a packaging estimate until measured on the target board.
- The teardown confirms six outer-shroud screws, a long black heatsink, a copper vapor chamber with a distinct silver fin stack, four vapor-chamber fasteners, and separate VRM thermal pads. It does not report cover gauge, deshrouded thickness, fin pitch or fin thickness.
- The commonly cited 47.3 × 47.3 mm package report is specifically about the 2017 Radeon Vega Frontier Edition (Vega 10), not the MI50's Vega 20: <https://overclock3d.net/news/gpu-displays/amd-radeon-vega-frontier-edition-pcb-exposed/>. It must not be used as direct proof of the MI50 package outline. A general Amkor package index lists some 47.5 × 47.5 mm FCBGA package families, but it does not establish that the MI50 uses that particular outline: <https://amkor.com/wp-content/uploads/2019/06/Amkor-Line-Card-JP.pdf>. No MI50/Vega 20-specific package drawing tying `FCBGA-1933` to 47.5 × 47.5 mm was found. Keep 47.5 mm only as an unverified user-supplied placeholder, separate from the vapor-chamber contact block.
- The proposed 0.5 mm cover gauge, 35–37 mm deshrouded thickness, 1.0–1.5 mm fin gap and 0.3–0.5 mm fin thickness are unverified estimates. Keep them in sensitivity studies, not hard-fit or final CFD geometry.
- Consolidated parameter set and confidence labels: [`MI50_ENVELOPE.md`](MI50_ENVELOPE.md) and [`mi50_envelope.json`](../data/mi50_envelope.json).

### MI50 teardown — secondary owner review

- Diego Strebel, 25 June 2025: <https://diegostrebel.com/posts/instinct_mi_50/>
- Exposed board photo: <https://diegostrebel.com/images/InstinctMI50/MI50_noshroud.jpg>
- Vapor-chamber / fin-stack photo: <https://diegostrebel.com/images/InstinctMI50/MI50_Cooler.jpg>
- Reports a full-length heatsink, copper vapor chamber over the GPU, four spring-loaded GPU-cooler fasteners, six outer-shroud screws, hidden heatsink fasteners under the backplate, and fragile VRM thermal pads. The author reports using 2 mm replacement VRM pads. These are qualitative teardown observations, not measured CAD dimensions or an AMD service specification.

### MI50 temperature / power owner report — measured but configuration-specific

- <https://github.com/srvr-farm/mi50-gaming>
- The project reports one MI50 16 GB card, cross-flashed to a Radeon Pro VII VBIOS and tuned to 300 W / 1800 MHz, with 96 °C peak junction in repeated benchmarks; at 1850 MHz it reports 103 °C and throttle-back near a reported 105 °C threshold. It also reports edge temperature about 30–40 °C below junction under load.
- The author explicitly limits the validated setup to a 16 GB card and says to re-derive values for 32 GB. Do not treat 105 °C as a universal AMD MI50 specification or the reported temperatures as a guarantee for another cooler/chassis.
- Engineering implication: use junction/hotspot and memory telemetry, not edge temperature alone, as the primary thermal validation signal.

### ROCm temperature telemetry — API capability, not per-card guarantee

- <https://rocm.docs.amd.com/projects/rocm_smi_lib/en/latest/doxygen/html/rocm__smi_8h.html>
- ROCm SMI defines EDGE, JUNCTION, MEMORY and HBM0–HBM3 temperature types, plus current/critical/emergency metrics. Whether all channels are exposed by a given MI50 board, VBIOS, kernel and ROCm release must be tested on the actual machine.

## Existing cooling-shroud precedents

### OpenSCAD 92 mm single-fan design

- <https://github.com/roackim/mi50-92mm-shroud>
- Public repo README specifies a 92 × 92 × 25 mm ARCTIC P9 Max and separates fan mount, heatsink duct and ramp. It mentions imperfect alignment of some GPU M2 positions. Useful as an independent mechanical reference. Check the repository's current LICENSE file before copying code or geometry; attribution alone is not permission.

### Three slim 80 mm fans

- <https://www.printables.com/model/1413245-amd-radeon-instinct-mi50-triple-slim-80mm-fan-shro>
- Published design describes three 80 × 80 × 15 mm fans and using four of six original shroud mounting points. Its author-reported fit is a design precedent, not independent validation of thermal performance.


### MI50-specific centrifugal blower transition — 10° JSCAD design

- Forum discussion and author notes: <https://forum.prusa3d.com/forum/english-forum-general-discussion-announcements-and-releases/jscad-javascript-cad-in-your-browser/?language=it>
- Published MI50 model: <https://www.printables.com/model/1229329-shroud-for-amd-instinct-mi50-workstation-gpu-and-b>
- Browser CAD share link is posted in the forum entry; the author describes the JSCAD script as approximately 102 lines using coordinate points and hull operations.
- The author reports owning three MI50 cards, trying a 180° U-turn duct with a BBQ-style blower, finding that turn ineffective, then making a 10° sloped transition. Photographs show the shroud mounted on an MI50. This is an owner design report, not a controlled comparative thermal or CFD study; the 10° value is a precedent, not an established optimum.
- This is the strongest public example found so far for making fan-axis angle and the connecting chamber geometry a coupled design variable.

### MI50 blower adapter — EFH-08E12W-JP01

- Model page: <https://3dgo.app/models/thingiverse/7083174>
- Author specifies the EFH-08E12W-JP01 fan, 116 mm total adapter length, M3 × 10 mm fasteners, and says a SolidWorks solution is attached. The listing is CC BY-SA; retain attribution and ShareAlike obligations for any adaptation of those files.
- No trustworthy manufacturer P–Q curve for the exact EFH-08E12W-JP01 was located. A reseller page gives internally inconsistent electrical data (0.7 W in one place versus 0.7 A in the product description) and should not be used as a simulation input without a fan label or manufacturer sheet.

### MI50 / MI25 / MI60 multi-format shroud listing — compatibility caveat

- Listing: <https://www.grelly.com/itm/radeon-instinct-mi25-mi50-mi60-full-shroud-replacement-227141415963>
- Advertises two GDSTIME 6028 blowers, one 75 × 30 mm or 75 × 25 mm blower, two 40 × 40 × 28 mm fans, or single 80/92 mm axial fans. The seller explicitly says the designs were tested on the MI25 only; MI50 fit is claimed from specifications, and MI60 fit is uncertain. Treat all variants as unverified MI50 fitment, not as proven MI50 cooling solutions.

### Multi-size MI25/MI50/MI60 kit

- <https://3dgo.app/models/cults3d/radeon-instinct-mi25-mi50-mi60-cooling-shroud>
- Listing includes 1×, 2× and 3×40 mm, plus 1×80, 1×92 and 1×120 mm configurations. It is marked CULTS PU / Private Use. We can study the listing and photographs but should not copy or redistribute the files/geometry without permission or a license grant.

### 120 mm curved inlet adapter

- <https://www.3dgo.app/models/thingiverse/7189349>
- Listing describes a 120 mm adapter with about 65 mm length excluding the fan; variants with 3×120 mm or 2×120 mm were not tested by its author. The exact operating fan and sustained GPU temperatures need additional verification.

### Dual MI60 duct — valuable but not an MI50 test

- <https://www.3dgo.app/models/thingiverse/7203670>
- Published 17 November 2025; designed for two MI60 cards, with MI50/MI100 compatibility explicitly untested. Uses a common card-side housing and gasket plus interchangeable 92 × 38 or 120 × 38 fan housings.
- Author reports that a 120 × 38 mm fan held two MI60s below 75 °C edge and 85–95 °C junction. A 92 × 38 mm version initially looked acceptable by edge temperature but had high junction temperature in the dual-GPU configuration. This is a valuable qualitative comparison, not a controlled single-MI50 benchmark.
- License is Creative Commons Attribution-ShareAlike. Follow the specific license terms if adapting that design.

## Fan manufacturers and models

All maximum airflow values below are free-air endpoints; maximum static-pressure values are zero-flow endpoints. Neither is the fan's installed operating point. For CFD, use the full P–Q curve, not the two maxima.


### AVC — BA series centrifugal blower, 97 × 97 × 33 mm

- AVC FAN catalogue, Ver.00 2016 (third-party hosted copy of manufacturer catalogue): <https://www.meditronik.com.pl/doc/plusik/avc-fan-catalog-10-2017.pdf>
- The catalogue gives a BA10033 series mechanical drawing and pressure-flow curves. Its table lists separate 12 V and 24 V versions. The table uses short forms such as `BA10033_12H`; the MI50 JSCAD designer names `BA10033B12H`. This looks consistent with the catalogue bearing-code scheme, but verify the fan's physical label before treating the part number as an exact match.
- Catalogued 12 V grades: `12L` 2700 RPM / 24.40 CFM / 18.95 mmH₂O / 4.56 W / 48.0 dBA; `12M` 3200 / 28.74 / 29.21 / 7.92 W / 52.5 dBA; `12H` 3600 / 32.21 / 35.10 / 10.56 W / 54.8 dBA; `12U` 4200 / 38.68 / 50.61 / 18.60 W / 58.4 dBA; `12S` 5000 / 45.61 / 74.68 / 22.80 W / 62.7 dBA.
- Catalogued 24 V grades: `24L` 2700 RPM / 24.40 CFM / 18.95 mmH₂O / 5.28 W / 48.0 dBA; `24M` 3200 / 28.74 / 29.21 / 8.16 W / 52.5 dBA; `24H` 3600 / 32.21 / 35.10 / 10.80 W / 54.8 dBA.
- All listed flow maxima are free-air endpoints and pressure maxima are zero-flow endpoints. The catalog includes P–Q curves for the grades, but this pass has not digitized the curve ordinates into numeric data. The catalog's extracted table does not specify the acoustic measurement distance/method, so its dBA figures must not be compared directly with Delta's explicitly one-metre figures.
- An ElecSpares reseller page for `BA10033B12H` lists 3570 RPM, 32.13 CFM and 54.7 dBA, but claims 1.32 A / 15.84 W; the AVC catalogue's 12H row specifies 0.88 A / 10.56 W at 3600 RPM. This is a material discrepancy. Use the manufacturer catalogue values provisionally and verify the physical label or obtain AVC confirmation before selecting a PSU or fan controller.
- Reseller page showing the discrepant values: <https://www.elecspares.com/product/ba10033b12h-avc-12v-1-32a-4-wire-turbine-blower-fan/>.

### ARCTIC — 80 mm slim P8 Slim PWM PST

- Product documentation: <https://support.arctic.de/en/p8-slim-pwm-pst/docs>
- P–Q PDF: <https://support.arctic.de/products/p8-slim-pwm-pst/techdocs/20240528_P8_SLIM_PQ_Curve_Web.pdf>
- CFD spreadsheet: <https://support.arctic.de/products/p8-slim-pwm-pst/techdocs/P8%20SLIM%20-%20PQ%20Curve%20for%20CFD.XLSX>
- Public specs: 80 × 80 × 15 mm; 3000 RPM; 22.5 CFM; 2.35 mmH₂O. A dBA value was not found in the cited spec page. Three are included in an existing MI50 shroud precedent.

### ARCTIC — 92 mm P9 Max

- Product specification PDF: <https://www.arctic.de/media/3c/7a/6e/1737639490/Spec_Sheet_P9_Max_EN.pdf>
- Documentation page: <https://support.arctic.de/en/p9-max/docs>
- P–Q PDF: <https://support.arctic.de/products/p9-max/techdocs/PQ%20Curve%2C%20P9%20Max%20%282025-01-17%29.pdf>
- CFD spreadsheet: <https://support.arctic.de/products/p9-max/techdocs/P9%20Max%20-%20PQ%20Curve%20for%20CFD.xlsx>
- Specs: 92 × 92 × 25 mm; 450–4300 RPM; 58.25 CFM; 6.17 mmH₂O. The official CFD workbook provides a ten-point numerical table for the 4300 RPM curve; its extracted data and limitations are documented in [`ARCTIC_P9_MAX_CURVE_PROVENANCE.md`](ARCTIC_P9_MAX_CURVE_PROVENANCE.md). The workbook's `C=0.95` flow-column notation remains unresolved. No dBA value was found in the cited specification sheet. Product documentation also provides a 92 mm mounting-hole drawing.

### ARCTIC — 120 mm P12 Max

- Documentation page: <https://support.arctic.de/en/p12-max/docs>
- P–Q PDF: <https://support.arctic.de/products/p12-max/techdocs/P12%20MAX%20-%20PQ%20Curve.pdf>
- CFD spreadsheet: <https://support.arctic.de/products/p12-max/techdocs/P12%20MAX%20-%20PQ%20Curve%20for%20CFD.XLSX>
- Specs: 120 × 120 × 25 mm; 200–3300 RPM; 81.04 CFM; 4.35 mmH₂O; noise is published as 0.6 sone, not dBA. Do not convert sone to dBA as if it were a fixed unit conversion.

### Noctua — 92 mm NF-A9 PWM

- <https://www.noctua.at/en/products/nf-a9-pwm/specifications>
- Specs: 92 × 92 × 25 mm; 46.44 CFM; 2.28 mmH₂O; 22.8 dBA. Detailed P–Q points are in the manufacturer's technical data. Confirm acoustic test conditions before comparing the number directly against another brand's rating.

### Noctua — 120 mm NF-A12x25 PWM

- Datasheet: <https://noctua.at/pub/media/blfa_files/infosheet/noctua_nf_a12x25_pwm_datasheet_en_web.pdf>
- Specs: 120 × 120 × 25 mm; 60.1 CFM; 2.34 mmH₂O; 22.6 dBA. Manufacturer P–Q data is included in the datasheet. Low shutoff pressure makes the heatsink/system curve especially important.

### Delta — 40 × 40 × 28 mm TFA0412BN

- Manufacturer catalogue/datasheet: <https://filecenter.deltaww.com/Products/Download/03/0301/Catalogue/TFA0412BN.pdf>
- Specs: 40 × 40 × 28 mm; 32 mm mounting-hole spacing; 15,600 RPM; 22.20 CFM; 38.19 mmH₂O; 50.8 dBA. The sheet says noise is measured in an anechoic chamber in free air at 1 m from the inlet. It also states max flow and max pressure are separate endpoints.
- A different TFA0412CN-CN product listing reports 25.29 CFM, 47.44 mmH₂O and 55 dBA. Treat it as a different exact variant, not as a correction to the BN datasheet: <https://www.delta-fan.com/technology/pulse-width-modulation-pwm.html>.

### Delta — 92 × 92 × 38 mm PFB series

- Manufacturer series catalogue: <https://filecenter.deltaww.com/Products/download/03/0301/catalogue/Industry-Energy.pdf>
- Exact PFB0924DHEP0 product page and STEP model listing: <https://www.delta-fan.com/pfb0924dhep0.html>
- PFB0924DHEP0: 24 V; 8000 RPM; 175.03 CFM; 46.21 mmH₂O; 66.5 dBA; 34.8 W. Its datasheet has a P–Q curve, acoustic test geometry and mechanical drawing; its drawing specifies 92 × 92 × 38 mm, 82.5 mm hole spacing and 8 × Ø4.5 mm hole features.
- PFB0924GHEP0: 24 V; 6000 RPM; 124.19 CFM; 25.49 mmH₂O; 60.5 dBA; 15.12 W.
- PFB0924EHEP0: 24 V; 4800 RPM; 103.67 CFM; 17.56 mmH₂O; 54 dBA; 7.92 W.
- The catalogue specifies sound pressure at 1 m from the air inlet. These are industrial fans and are very loud relative to desktop PC fans. The exact PFB0924DHEP0 product page lists a STEP file, which may help build an exact fan solid for CAD.

### Delta — 120 × 120 × 38 mm PFB1212UHE-F00

- Manufacturer datasheet: <https://www.delta-fan.com/Download/Spec/PFB1212UHE-F00.pdf>
- Product listing / availability: <https://www.digikey.com/en/products/detail/delta-electronics/PFB1212UHE-F00/11563883>
- Specs: 12 V; 5500 RPM; 252.85 CFM; 35.877 mmH₂O; 66.5 dBA; 48 W. Its catalogue P–Q curve and dimension drawing are in the datasheet; the drawing specifies 120 × 120 × 38 mm and 105 mm mounting-hole spacing. Acoustic measurements are in free air in an anechoic chamber, with the microphone 1 m from the intake. A distributor currently lists this exact F00 variant as obsolete, so availability must be checked; do not plan a production design around it before obtaining a source.

## Thermal and airflow modelling implications

1. Start with a 300 W card-level load because AMD lists 300 W peak TDP. A first-principles air energy balance gives about 52.7 CFM for a 10 °C bulk-air rise and 35.1 CFM for a 15 °C rise at 1.20 kg/m³ and 1005 J/(kg·K). These are ideal bulk-flow requirements, not guaranteed cooling performance.
2. Solve fan/duct/heatsink operating points from actual P–Q curves and system resistance. Parallel fans add flow at a common pressure; they do not add shutoff pressure.
3. Measure or model flow through the actual fin channels. Duct outlet area alone does not prove the air is crossing the fin field uniformly.
4. Use junction and memory temperatures where exposed; edge temperature can substantially under-report hotspot temperature in owner-reported MI50 tests.
5. For early CFD, use P–Q fan boundary conditions and a measured/calibrated heatsink porous resistance if resolving every fin is too expensive. CHT comes after solid regions, power distribution and interface resistances are defensible.
6. Acoustic specifications are not directly comparable unless weighting, distance, environment, inlet/outlet side, RPM and measurement standard are known. Delta explicitly provides one-metre anechoic inlet-side measurements for several server-fan sheets; some desktop fan pages do not state comparable test geometry. Sone must remain separate from dBA.

## Information not found yet

- No authoritative, dimensioned public MI50 heatsink STEP/IGES model or complete card mechanical drawing was found in this research pass. The public AMD specification gives length and form-factor categories, while the detailed cooler dimensions remain unverified; see `MI50_ENVELOPE.md`.
- No public MI50 fin pitch, fin thickness, channel hydraulic diameter, free-flow area, heatsink pressure-drop curve, or fan/system operating point has been established.
- An MI50-specific public JSCAD blower duct uses a 10° sloped transition and reports an earlier 180° U-turn duct was ineffective, but does not publish a controlled A/B temperature or pressure-drop result.
- AVC BA10033 family P–Q plots exist in the catalog, but their graph data has not yet been digitized; the exact BA10033B12H designation also needs confirmation against the physical label.
- Exact Delta fan mechanical STEP models are available from some product pages (for example PFB0924DHEP0), but no comparable manufacturer CAD model for the MI50 card/heatsink assembly was located.
- No verified per-rail or per-component 300 W power split between GPU die, HBM and VRM was found.
- No authoritative AMD MI50-specific junction/HBM operating limit was found in the reviewed public product sources. The 105 °C threshold in the community tuning log is a report for that configuration, not an AMD specification.
- No manufacturer one-third-octave / tonal acoustic spectra were found for the fan candidates above. Catalogue dBA values are not enough to model blade-pass tones or duct resonances.

## Next research tasks

1. Identify the exact MI50 board vendor/revision and whether it is 16 GB or 32 GB; compare the uploaded reference STLs to public teardown imagery and board mounting features.
2. Verify the BA10033B12H fan suffix and electrical rating against the actual fan label or a direct AVC response; then digitize the manufacturer P–Q curve.
3. Search for seller/repair listings that identify the original blower or heatsink assembly part number; this may lead to a service drawing or donor assembly.
4. Download the ARCTIC P8/P9/P12 CFD spreadsheets and turn their manufacturer curves into versioned numeric datasets after checking the tabular units and RPM conditions.
5. Obtain the exact Delta 92/120 mm STEP models only as fan-geometry references, and retain manufacturer licensing/redistribution terms.
6. Locate exact acoustics measurement data (preferably one-third-octave spectra) or plan repeatable in-house measurements at fixed RPM, distance and orientation.
