# MI50 close-range photogrammetry and dimensional reconstruction

Research snapshot: 2026-11-20. This is the capture and validation protocol for building revision-specific mechanical references from photographs. A reconstructed mesh is evidence, not automatically a dimensionally accurate CAD model.

## 1. What photogrammetry can and cannot recover

Photogrammetry can help recover the visible external surfaces of the assembled card, factory cover, exposed heatsink, vapor chamber, bracket and large component packages. It is especially useful for overall envelopes, relative heights, cover shape, major planforms, fastener locations and the spatial relationship between assemblies.

It cannot recover hidden interfaces from a view in which they are occluded. It is also unreliable on smooth, shiny or repetitive surfaces and on very thin features. The repeated narrow fin channels are therefore a special case: use photographs for context and alignment, but use calipers/micrometer measurements, macro images, fin counts and optical cross-sections to determine fin pitch, thickness and hydraulic geometry. The University of Melbourne photogrammetry guide specifically warns about repeated features and very thin/small subjects; the photogrammetry literature also identifies repetitive objects, weak texture and specular reflections as matching problems.

Do not treat a watertight mesh or a high polygon count as proof of accuracy. Dense reconstruction can smooth, bridge or erase the very thin fins that matter to airflow.

## 2. Keep separate specimens and capture states

Never merge images from different physical cards or mechanical states into one reconstruction. Use separate capture jobs for:

- `MI50-16GB-<specimen>-assembled`: original cover fitted.
- `MI50-16GB-<specimen>-deshrouded`: cover removed, cooler still installed.
- `MI50-16GB-<specimen>-cooler-removed`: only if the cooler is removed for service and the state is documented.
- Equivalent separate jobs for every 32GB specimen and every OEM/reworked board.

The 16GB teardown currently available publicly is not proof of 32GB internal geometry. AMD's common published 267 mm / Full Height / Double Slot envelope can be used as a nominal cross-check for both official SKUs, but internal geometry must remain specimen-specific until compared physically.

Before capture, record the specimen identity in `data/mi50_measurement_template.csv`: marketed SKU, vendor, PCB revision, VBIOS P/N, PCI vendor/device and subsystem IDs, cooler/assembly identifiers, and whether the photograph shows assembled or deshrouded hardware. Redact serial numbers before publishing images.

## 3. Establish coordinate datums

Use one consistent card coordinate system across photographs, caliper records and CAD:

- X: along the PCB from the I/O bracket toward the distal card end.
- Y: from the PCIe edge-finger datum toward the top edge of the card.
- Z: normal to the PCB, positive toward the component/cooler side.

For each specimen, record the origin point and the exact surfaces/edges used. Keep the PCB, factory cover, black heatsink, silver vapor-chamber fin field, vapor chamber, backplate and replacement shroud as separate geometric objects. Do not infer their contact interfaces from an external scan.

## 4. Camera preparation

1. Prefer the phone's main 1x camera or a camera/lens with a fixed focal length. Avoid ultrawide, digital zoom, portrait mode, panorama, beauty filters and computational background replacement.
2. Keep the same physical lens and focal setting for a capture set. Lock focus/exposure/white balance where the camera app permits; do not change zoom between frames. Save original full-resolution files and preserve EXIF metadata.
3. Use a fast enough shutter to prevent motion blur. Support the card and camera; do not move the card during a normal orbit capture.
4. Before the card scan, calibrate the camera/lens using a flat checkerboard or ChArUco target. Photograph the target at many positions, tilts and distances while keeping the camera's focus and focal setting representative of the actual scan. Measure the printed square spacing with calipers; do not trust “100% print size” without checking it.
5. Recalibrate when changing lens, zoom, focus regime or image processing. Camera calibration parameters materially affect reconstruction accuracy.

OpenCV's camera-calibration guidance explicitly calls for images of a known calibration pattern from multiple views and a measured physical grid spacing. COLMAP can reuse externally calibrated intrinsics; its documentation recommends avoiding unnecessarily complex camera models that can overfit sparse calibration data.

## 5. Scale: use multiple independent constraints

Structure-from-motion reconstructions normally have an arbitrary scale until a known real-world distance is applied. Do not use a single image's pixel count as a 3D measurement unless the reference and measured feature are coplanar and the image has been rectified for perspective and lens distortion.

Use several independent scale constraints where possible:

- Full-board length: AMD publishes 267 mm for both official MI50 16GB and 32GB SKUs. This is a useful nominal whole-card check only after specimen identity is confirmed; independently measure the physical card if possible.
- A steel rule or rigid scale bar placed in the same plane as the feature being measured.
- Caliper measurements between recognizable, visible points, such as two hole centers or two machined edges.
- A second known dimension in another direction or plane to test for anisotropic reconstruction error.

For features at different heights, use a 3D reconstruction and apply scale to corresponding 3D points. A ruler on the table behind the card is not a valid direct pixel scale for a heatsink feature above the table. Use at least two independent known distances for scale fitting and more for validation. Distances should span different axes and, if possible, different Z levels.

The project script `scripts/photogrammetry_scale_fit.py` fits one uniform model-to-mm scale factor from a CSV of measured 3D reference distances. It reports each residual so inconsistent references are visible. It does not correct lens distortion, perspective, model warping or anisotropic errors; those must be addressed in capture/reconstruction and checked against independent dimensions.

### Comparing dimensions inside one image

Image ratios are useful for a quick estimate only when the compared length and reference lie on the same plane (or are both edges of the same planar face), are both measured in the image's local direction, and lens distortion is corrected. If one feature is higher or closer to the camera, perspective changes its apparent size. A single ratio from a perspective photograph must not be promoted to a CAD constraint.

## 6. Photograph capture plan

Capture each physical specimen and each mechanical state in its own directory. Shoot overlapping views with stable diffuse lighting and no object movement.

### Whole card / outer cover

- Top: near-normal view plus four oblique quadrants.
- Bottom/backplate: near-normal plus four oblique quadrants.
- Both long edges: low camera height, with a scale in the card plane.
- I/O bracket end and distal end: straight-on and oblique views.
- Cover seams, fasteners, fan/duct openings, flanges and bends: close-ups with a scale in the same plane.

### Deshrouded cooler

- Repeat top, bottom and edge views after removing only the outer cover.
- Photograph black and silver fin fields separately at oblique angles that reveal fin height and channel direction.
- Photograph the vapor-chamber perimeter, fastener bosses, contact block edges and VRM pad locations without disturbing thermal-interface material.
- Take macro close-ups of the fin regions with a ruler or calibrated scale bar parallel to the fin plane.

### Capture density

As a practical starting point, use three overlapping camera orbits: a high oblique orbit, a mid-height orbit and a low orbit. Aim for roughly 70–80% overlap between neighboring images, with enough parallax that edges move relative to one another. Add targeted close-ups for details; do not expect the close-up set to align automatically with the whole-card scan if there is insufficient shared visual detail.

Move the camera around a stationary object. A turntable can work, but a rotating object against a static background can cause the background to dominate feature matching; if using a turntable, use a controlled background/masking workflow and keep the object well separated from it.

## 7. Reflective metal, black anodizing and fine fins

The MI50 cooler combines dark anodized surfaces and reflective metal. Use broad, diffuse light sources, avoid direct flash and moving specular highlights, and capture the same surface from convergent viewpoints. Cross-polarized lighting can reduce reflections if the setup permits it.

Do not apply scanning spray, powder, paint or adhesive markers to an assembled graphics card, PCB, connectors, thermal pads, heatsink contact surfaces or other sensitive electronics. If a removable matte coating is ever considered, it must be explicitly safe for the particular surface, completely removable, and applied only to a detached, non-electronic component after checking material compatibility. Prefer non-contact lighting and manual metrology.

Fin channels are highly repetitive and narrow. Photogrammetry may confuse one fin with its neighbor, close gaps, or smooth thin edges. For each fin field, measure at least ten fin intervals and divide by the interval count to estimate pitch; measure fin thickness at multiple accessible flat locations with a suitable micrometer. Record black and silver fields separately. Use high-resolution macro photographs for documentation and a direct cross-sectional measurement for hydraulic geometry.

## 8. Recommended open-source toolchain

- **OpenMVG + OpenMVS:** good first open-source Linux route to investigate. OpenMVG provides camera calibration/feature matching/structure-from-motion and runs on Linux. OpenMVS accepts OpenMVG scenes and provides dense point clouds, mesh reconstruction and texturing. OpenMVS also documents a CPU Semi-Global Matching route (`DensifyPointCloud ... --fusion-mode -2`) when GPU acceleration is unavailable. CPU reconstruction may be slow.
- **COLMAP:** strong alternative for SfM and camera-pose reconstruction, with a GUI and command-line interface. Current Linux distributions may package it without CUDA/HIP; current upstream supports building with CUDA or AMD HIP/ROCm when those toolchains are available. Keep the exact build configuration with the reconstruction record.
- **Meshroom / AliceVision:** convenient node-based desktop workflow with a ready photogrammetry pipeline. The documented dense MVS workflow requires an NVIDIA CUDA GPU; CPU draft meshing exists but is a lower-detail fallback. It is not the default choice for a machine without a supported NVIDIA GPU.
- **OpenCV:** use for camera calibration and optional checkerboard/ChArUco detection. It is not itself the complete photogrammetry pipeline.

The first experiment should be a small 20–40 image card-top dataset, not a full 200-image scan. Confirm camera calibration and alignment first, then expand. Tool versions, exact commands, build flags, source image hashes and processing parameters belong in the capture log.

## 9. Convert the scan into engineering CAD

1. Preserve original images and raw sparse/dense reconstruction outputs; never overwrite them with edited meshes.
2. Align the model to the card coordinate system using the PCIe edge/bracket and measured datum references.
3. Scale from multiple independent 3D distance constraints using the scale-fit script; inspect residuals.
4. Compare reconstructed lengths against independent caliper measurements not used in the scale fit.
5. Extract broad surfaces and envelopes from the point cloud; do not use a smoothed mesh to define fin gaps.
6. Rebuild clean parametric solids in CAD: board outline, cover panels, mounting-hole patterns, vapor-chamber envelope, heatsink base and separately parameterized fin fields.
7. Record each CAD dimension's source, specimen, method, uncertainty and confidence in the measurement CSV and `data/mi50_envelope.json`.
8. Keep the raw photogrammetry mesh as a reference object in CAD, not as the only editable geometry.

## 10. Confidence and acceptance criteria

Use these evidence labels consistently:

- `manufacturer_specified`: primary manufacturer dimension/specification.
- `caliper_measured`: physical measurement with tool and uncertainty recorded.
- `photogrammetry_scaled`: dimension derived from a scaled reconstruction and checked against at least one independent dimension.
- `photo_estimate`: planar/perspective-corrected estimate from an image; not equivalent to direct measurement.
- `engineering_estimate`: inferred for sensitivity studies only.
- `not_measured`: no value is available.

A reconstructed dimension is not ready for fit-critical CAD until it has at least one independent physical check. For mounting interfaces, use calipers/coordinate measurements directly wherever accessible. For airflow-critical fin passages, direct fin pitch, thickness, height, channel count and flow-direction measurements take precedence over a photogrammetry mesh.

## 11. Project templates and references

- Capture metadata: `data/photogrammetry_capture_log_template.csv`.
- Scale constraints: `data/photogrammetry_scale_constraints_template.csv`.
- Scale fitter: `scripts/photogrammetry_scale_fit.py`.
- Physical inspection and caliper procedure: `docs/PHYSICAL_MEASUREMENT_GUIDE.md`.
- Current variant-specific parameter/evidence file: `data/mi50_envelope.json`.

## 12. Public technical references

1. [AliceVision / Meshroom photogrammetry pipeline](https://github.com/alicevision/meshroom-manual/blob/develop/source/feature-documentation/core/pipelines/photogrammetry.rst) — feature extraction/matching, Structure-from-Motion, depth maps, meshing and texturing.
2. [Meshroom official requirements](https://github.com/alicevision/meshroom-manual/blob/develop/source/first-steps/install/requirements.rst) — NVIDIA CUDA requirement for dense MVS; CPU draft meshing alternative.
3. [OpenCV camera calibration](https://docs.opencv.org/4.x/dc/dbb/tutorial_py_calibration.html) — checkerboard camera calibration and known square dimensions.
4. [COLMAP installation](https://colmap.github.io/install.html) and [FAQ](https://colmap.github.io/faq.html) — Linux build options, CUDA/HIP support and camera-intrinsic handling.
5. [OpenMVG](https://github.com/openMVG/openMVG) — open-source Linux-capable Structure-from-Motion framework.
6. [OpenMVS usage](https://github.com/cdcseacave/openMVS/blob/develop/docs/wiki/Usage.md) — dense reconstruction, mesh reconstruction and CPU Semi-Global Matching option.
7. [University of Melbourne photogrammetry benchmark](https://ms-kb.msd.unimelb.edu.au/next-lab/3d-scanning/guides/photogrammetry/photogrammetry-benchmark) — repeated features and very thin/small subjects are challenging.
8. [Image matching in photogrammetry review](https://doi.org/10.1111/j.1477-9730.2011.00671.x) — repetitive objects, weak texture, specular reflections and occlusions as matching difficulties.
