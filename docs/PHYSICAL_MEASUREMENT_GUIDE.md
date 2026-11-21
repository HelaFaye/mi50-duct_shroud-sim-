# MI50 physical inspection and measurement guide

Goal: create revision-specific mechanical references for MI50 16GB and MI50 32GB without mixing measurements from different cards.

## Before measuring: identify the specimen

For each card, record:

- marketed SKU / memory capacity;
- manufacturer/board vendor and every visible PCB or assembly revision marking;
- all backplate labels and serial/part-number stickers (redact serial numbers before sharing publicly);
- VBIOS part number if readable;
- PCI vendor/device and subsystem IDs from the host;
- whether the card is an original AMD board, OEM board, or modified/reworked board (only if evidence supports it).

A Linux host can collect initial PCI identity without removing the card:

```bash
lspci -nn -d 1002:

for d in /sys/bus/pci/devices/*; do
  [ -r "$d/vendor" ] || continue
  [ "$(cat "$d/vendor")" = "0x1002" ] || continue
  printf '\n%s\n' "$d"
  for f in vendor device subsystem_vendor subsystem_device revision; do
    [ -r "$d/$f" ] && printf '%-18s %s\n' "$f" "$(cat "$d/$f")"
  done
done
```

This identifies PCI functions, not mechanical revision by itself. Preserve the raw output alongside photographs.

## Photograph set

For a calibrated multi-view reconstruction, follow [`PHOTOGRAMMETRY_WORKFLOW.md`](PHOTOGRAMMETRY_WORKFLOW.md) and fill in `data/photogrammetry_capture_log_template.csv`. Keep every card and mechanical state in a separate session.

For each card, take:

1. Factory-assembled top view, camera perpendicular to PCB; include a steel ruler in the PCB plane.
2. Factory-assembled bottom/backplate view, with labels visible but serials masked for public sharing.
3. I/O bracket end view and distal-end view.
4. Both long edges at camera height, with a scale in the same plane.
5. After removing only the outer cover: exposed cooler top view and all four side/edge views.
6. Close-ups of both fin fields, vapor chamber perimeter, fasteners, VRM pads, and any visible PCB revision marks.
7. If a cover is removed, photograph every screw and its original location before mixing fasteners.

Avoid wide-angle distortion. Use the main camera at moderate zoom, keep the sensor parallel to the measured plane, and include a scale on that plane. Keep original-resolution files.

## Measurement method

Photogrammetry may supplement caliper measurements for broad visible surfaces and relative heights, but it does not replace direct measurements for fin pitch/thickness or fit-critical hole coordinates. Use multiple independent 3D scale constraints and record the reconstruction residuals; see [`PHOTOGRAMMETRY_WORKFLOW.md`](PHOTOGRAMMETRY_WORKFLOW.md).

- Use calipers for accessible hard edges and screw diameters; do not clamp delicate fins or PCB components.
- Use a depth gauge or height gauge from a repeatable PCB datum for Z-height.
- Measure cover sheet gauge on a flat, unbent flange; do not measure over paint, embossing, or folded edges.
- Measure fin pitch across at least 10 intervals, then divide by the interval count. Measure fin thickness at several accessible points; record tool resolution and uncertainty.
- Measure fin-channel depth and identify whether the channels are continuous or interrupted.
- Record each fin field separately. Do not assume the silver and black fields share pitch or flow direction.
- For mounting holes, record center-to-center distances in X/Y from a declared datum. Photograph the caliper setup.
- Do not remove the vapor chamber or peel thermal pads merely to expose package dimensions. That is a separate service operation with TIM replacement consequences.

## Required measurement record

Use `data/mi50_measurement_template.csv`. Make a separate row for every feature on every physical specimen. Use `not_measured` rather than filling an unknown with a guessed value. For estimates derived from photographs, label the method `photo_estimate`, include the source image filename, and do not mark it as measured.

## Thermal validation data to capture later

At idle, intermediate load, and sustained full load, log board power, GPU edge and junction/hotspot temperatures where available, HBM temperatures where exposed, VRM temperatures where exposed, fan RPM, inlet air temperature, outlet air temperature, and workload duration. Record ambient conditions and sensor/tool versions. Do not infer component heat split from board power alone.
