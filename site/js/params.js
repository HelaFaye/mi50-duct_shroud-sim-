// Parameter schema, defaults, and validation for the MI50 shroud editor.
// Pure module (no DOM). Every parameter is explicit and carries a provenance
// note when its default is not a measured MI50 value.

import { FAN_SCREW_SPACING_MM, MIN_WEB_MM, deriveDimensions } from './geometry.js';

// Public envelope references (see data/mi50_envelope.json for sources/status).
export const ENVELOPE = Object.freeze({
  board_length_mm: 267.0, // manufacturer specified
  board_height_mm: 111.15, // PCIe CEM full-height nominal
  slot_envelope_thickness_mm: 40.0, // "double slot" form-factor estimate
  deshrouded_cooler_thickness_mm: [35.0, 37.0], // unverified estimate
});

export const GROUPS = [
  { id: 'fans', label: 'Fans' },
  { id: 'duct', label: 'Duct' },
  { id: 'fit', label: 'Card fit' },
];

export const PARAMETERS = [
  { id: 'fan_size_mm', group: 'fans', label: 'Fan frame size', unit: 'mm', type: 'select',
    options: Object.keys(FAN_SCREW_SPACING_MM).map(Number), default: 92,
    help: 'Square frame size; sets the standard screw-hole spacing.' },
  { id: 'fan_count', group: 'fans', label: 'Fans in parallel', unit: '', type: 'int', min: 1, max: 4, step: 1, default: 1 },
  { id: 'fan_row_axis', group: 'fans', label: 'Fan row direction', type: 'select',
    options: ['height', 'thickness'], default: 'height',
    help: 'Multiple fans sit side by side along the card height or thickness.' },
  { id: 'fan_throat_diameter_mm', group: 'fans', label: 'Fan throat diameter', unit: 'mm', type: 'number', min: 0, max: 200, step: 0.5, default: 0,
    help: '0 = automatic (frame size minus two walls and a 0.5 mm web each side).' },
  { id: 'screw_hole_diameter_mm', group: 'fans', label: 'Screw hole diameter', unit: 'mm', type: 'number', min: 2, max: 6, step: 0.1, default: 4.4 },
  { id: 'plate_thickness_mm', group: 'duct', label: 'Fan plate thickness', unit: 'mm', type: 'number', min: 1, max: 10, step: 0.5, default: 3 },
  { id: 'wall_thickness_mm', group: 'duct', label: 'Wall thickness', unit: 'mm', type: 'number', min: 0.8, max: 6, step: 0.1, default: 2 },
  { id: 'duct_length_mm', group: 'duct', label: 'Transition length', unit: 'mm', type: 'number', min: 5, max: 300, step: 1, default: 60,
    help: 'Length of the lofted section between the fan plate and the sleeve.' },
  { id: 'sleeve_length_mm', group: 'duct', label: 'Sleeve length', unit: 'mm', type: 'number', min: 2, max: 80, step: 1, default: 15,
    help: 'Straight section that slips over the end of the cooler.' },
  { id: 'cooler_height_mm', group: 'fit', label: 'Cooler inlet height', unit: 'mm', type: 'number', min: 20, max: 120, step: 0.1, default: 100,
    provenance: 'unmeasured', help: 'UNMEASURED placeholder. Measure your card; no public value exists.' },
  { id: 'cooler_thickness_mm', group: 'fit', label: 'Cooler inlet thickness', unit: 'mm', type: 'number', min: 10, max: 60, step: 0.1, default: 36,
    provenance: 'estimate', help: 'Unverified 35–37 mm estimate (data/mi50_envelope.json). Measure your card.' },
  { id: 'fit_clearance_mm', group: 'fit', label: 'Fit clearance per side', unit: 'mm', type: 'number', min: 0, max: 3, step: 0.05, default: 0.4 },
  { id: 'outlet_offset_y_mm', group: 'fit', label: 'Outlet offset (height)', unit: 'mm', type: 'number', min: -80, max: 80, step: 0.5, default: 0,
    help: 'Moves the sleeve relative to the fan centre along the card height.' },
  { id: 'outlet_offset_z_mm', group: 'fit', label: 'Outlet offset (thickness)', unit: 'mm', type: 'number', min: -80, max: 80, step: 0.5, default: 0 },
];

export const PARAMETER_IDS = PARAMETERS.map((p) => p.id);

export function defaultParameters() {
  return Object.fromEntries(PARAMETERS.map((p) => [p.id, p.default]));
}

/** Coerce raw (e.g. JSON or form) values to typed values; unknown keys dropped. */
export function normalizeParameters(raw) {
  const out = defaultParameters();
  for (const spec of PARAMETERS) {
    if (!(spec.id in (raw || {}))) continue;
    const value = raw[spec.id];
    if (spec.type === 'select') {
      const match = spec.options.find((o) => String(o) === String(value));
      if (match !== undefined) out[spec.id] = match;
    } else {
      const n = Number(value);
      if (Number.isFinite(n)) out[spec.id] = spec.type === 'int' ? Math.round(n) : n;
    }
  }
  return out;
}

const deg = (rad) => (rad * 180) / Math.PI;

/**
 * Validate parameters. Errors block geometry generation; warnings are fit,
 * flow, or printability concerns the user should review.
 */
export function validateParameters(p) {
  const errors = [];
  const warnings = [];
  for (const spec of PARAMETERS) {
    const v = p[spec.id];
    if (spec.type === 'select') {
      if (!spec.options.includes(v)) errors.push(`${spec.label}: unsupported value ${v}`);
    } else if (!Number.isFinite(v)) {
      errors.push(`${spec.label} must be a number`);
    } else if (v < spec.min || v > spec.max) {
      errors.push(`${spec.label} must be between ${spec.min} and ${spec.max} ${spec.unit}`.trim());
    }
  }
  if (errors.length) return { errors, warnings, metrics: null };

  const d = deriveDimensions(p);
  const margin = MIN_WEB_MM;
  const maxThroat = d.S - 2 * d.t - 2 * margin;
  if (d.throatRadius <= 0) errors.push('Fan throat diameter must be positive (reduce wall thickness).');
  if (2 * d.throatRadius > maxThroat + 1e-9) {
    errors.push(`Fan throat (${(2 * d.throatRadius).toFixed(1)} mm) leaves no web before the duct wall; maximum is ${maxThroat.toFixed(1)} mm.`);
  }
  if (d.throatRadius + d.holeRadius + margin > d.holeOffset * Math.SQRT2) {
    errors.push('Fan throat overlaps the screw holes; reduce the throat or screw-hole diameter.');
  }
  if (d.holeOffset + d.holeRadius + margin > d.S / 2 - d.t) {
    errors.push('Screw holes intersect the duct wall; reduce wall thickness or screw-hole diameter.');
  }

  const fanY = d.fanInnerY, fanZ = d.fanInnerZ;
  const outY = d.outletInnerY, outZ = d.outletInnerZ;
  // Worst wall angle from the flow axis on each side (offset shifts one side more).
  const wallAngles = [
    Math.atan2(Math.abs((outY / 2 + p.outlet_offset_y_mm) - fanY / 2), d.ductLength),
    Math.atan2(Math.abs((-outY / 2 + p.outlet_offset_y_mm) + fanY / 2), d.ductLength),
    Math.atan2(Math.abs((outZ / 2 + p.outlet_offset_z_mm) - fanZ / 2), d.ductLength),
    Math.atan2(Math.abs((-outZ / 2 + p.outlet_offset_z_mm) + fanZ / 2), d.ductLength),
  ].map(deg);
  const maxWallAngle = Math.max(...wallAngles);
  const fanArea = fanY * fanZ;
  const outletArea = outY * outZ;
  const areaRatio = outletArea / fanArea;

  const outerY = [
    Math.min(-(fanY / 2 + d.t), p.outlet_offset_y_mm - outY / 2 - d.t),
    Math.max(fanY / 2 + d.t, p.outlet_offset_y_mm + outY / 2 + d.t),
  ];
  const outerZ = [
    Math.min(-(fanZ / 2 + d.t), p.outlet_offset_z_mm - outZ / 2 - d.t),
    Math.max(fanZ / 2 + d.t, p.outlet_offset_z_mm + outZ / 2 + d.t),
  ];
  const extentY = outerY[1] - outerY[0];
  const extentZ = outerZ[1] - outerZ[0];

  if (areaRatio > 1 && maxWallAngle > 7) {
    warnings.push(`Expanding duct with ${maxWallAngle.toFixed(1)}° wall angle: diffusers above ~7° half-angle commonly separate. Lengthen the transition.`);
  }
  if (maxWallAngle > 45) {
    warnings.push(`Wall angle ${maxWallAngle.toFixed(1)}° exceeds 45°: printed fan-plate-down, these walls overhang without support.`);
  }
  if (extentZ > ENVELOPE.slot_envelope_thickness_mm) {
    warnings.push(`Shroud is ${extentZ.toFixed(1)} mm thick, ${(extentZ - ENVELOPE.slot_envelope_thickness_mm).toFixed(1)} mm beyond the ${ENVELOPE.slot_envelope_thickness_mm} mm dual-slot envelope; adjacent slot clearance is needed.`);
  }
  if (extentY > ENVELOPE.board_height_mm) {
    warnings.push(`Shroud is ${extentY.toFixed(1)} mm tall, beyond the ${ENVELOPE.board_height_mm} mm full-height card envelope; check case clearance.`);
  }
  if (p.cooler_height_mm === 100) {
    warnings.push('Cooler inlet height is the unmeasured 100 mm placeholder. Measure your card before printing.');
  }

  return {
    errors,
    warnings,
    metrics: {
      fan_end_inner_mm: [fanY, fanZ],
      outlet_inner_mm: [outY, outZ],
      fan_end_area_mm2: fanArea,
      outlet_area_mm2: outletArea,
      area_ratio_outlet_to_fan: areaRatio,
      max_wall_angle_deg: maxWallAngle,
      outer_extent_mm: { length: d.totalLength, height: extentY, thickness: extentZ },
      total_length_with_card_mm: d.totalLength - d.sleeveLength + ENVELOPE.board_length_mm,
    },
  };
}
