// Browser port of analysis/fan_operating_point.py plus the editor's
// geometry coupling (duct loss) and acoustic budget. Pure module.
//
// solveOperatingPoint() reproduces the Python bisection exactly (same bounds,
// iteration cap, and tolerance) so results can be cross-checked against the
// reference implementation; tests/test_site_parity.py does that via Node.

export const CFM_TO_M3_S = 0.00047194745;
export const PA_PER_MMH2O = 9.80665;

function validatePoints(points, label, direction) {
  if (!Array.isArray(points) || points.length < 2) throw new Error(`${label}: at least two curve points are required`);
  points.forEach(([q, p], i) => {
    if (!Number.isFinite(q) || !Number.isFinite(p)) throw new Error(`${label}: point ${i + 1} contains a non-finite value`);
    if (q < 0 || p < 0) throw new Error(`${label}: flow and pressure must be non-negative`);
    if (i > 0) {
      const [q0, p0] = points[i - 1];
      if (q <= q0) throw new Error(`${label}: flow values must be strictly increasing`);
      if (direction === 'decreasing' && p > p0 + 1e-6) throw new Error(`${label}: pressure must be non-increasing with flow`);
      if (direction === 'increasing' && p < p0 - 1e-6) throw new Error(`${label}: pressure must be non-decreasing with flow`);
    }
  });
  if (Math.abs(points[0][0]) > 1e-9) throw new Error(`${label}: first point must be at 0 CFM`);
  if (direction === 'decreasing') {
    if (points[0][1] <= 0) throw new Error(`${label}: shutoff pressure must be greater than 0`);
    if (Math.abs(points[points.length - 1][1]) > 1e-6) throw new Error(`${label}: last point must be at 0 mmH2O (free-air point)`);
  } else {
    if (Math.abs(points[0][1]) > 1e-6) throw new Error(`${label}: system curve must start at 0 mmH2O`);
    if (points[points.length - 1][1] <= 0) throw new Error(`${label}: system curve must contain a positive pressure drop`);
  }
  return points.map(([q, p]) => [q, p]);
}

export class PiecewiseCurve {
  constructor(points, { kind, source = 'unspecified' }) {
    this.kind = kind; // 'fan curve' | 'system curve'
    this.points = validatePoints(points, source, kind === 'fan curve' ? 'decreasing' : 'increasing');
    this.flows = this.points.map(([q]) => q);
    this.source = source;
  }
  get maxFlow() { return this.points[this.points.length - 1][0]; }
  pressureAt(flow) {
    if (!Number.isFinite(flow)) throw new Error('flow must be finite');
    const pts = this.points;
    const low = pts[0][0], high = pts[pts.length - 1][0];
    const tol = 1e-10 * Math.max(1, high);
    if (flow < low - tol || flow > high + tol) {
      throw new Error(`flow ${flow.toPrecision(6)} CFM is outside the supplied ${this.kind}; extrapolation is disabled`);
    }
    flow = Math.min(Math.max(flow, low), high);
    // first index >= 1 whose flow >= query (bisect_left), matching the Python
    let lo = 1, hi = pts.length;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (this.flows[mid] < flow) lo = mid + 1; else hi = mid; }
    if (lo >= pts.length) return pts[pts.length - 1][1];
    const [q0, p0] = pts[lo - 1];
    const [q1, p1] = pts[lo];
    return p0 + ((flow - q0) / (q1 - q0)) * (p1 - p0);
  }
}

export const fanCurve = (points, source) => new PiecewiseCurve(points, { kind: 'fan curve', source });
export const systemCurve = (points, source) => new PiecewiseCurve(points, { kind: 'system curve', source });

/** Affinity-law scaling (Q ~ N, p ~ N^2): an explicit model assumption, not a measured curve. */
export function affinityScale(points, ratio) {
  if (!(ratio > 0) || !Number.isFinite(ratio)) throw new Error('RPM ratio must be positive');
  return points.map(([q, p]) => [q * ratio, p * ratio * ratio]);
}

/** Duct loss Δp = K · ½ρv² at the outlet area, converted to mmH2O, for total flow in CFM. */
export function ductLossMmH2O(totalFlowCfm, kLoss, areaM2, densityKgM3) {
  if (!(kLoss > 0)) return 0;
  const v = (totalFlowCfm * CFM_TO_M3_S) / areaM2;
  return (kLoss * 0.5 * densityKgM3 * v * v) / PA_PER_MMH2O;
}

/**
 * Solve N identical parallel fans against a system model.
 * options.system: { type: 'quadratic', pressureMmH2O, flowCfm } | { type: 'table', curve: PiecewiseCurve }
 * options.ductLoss (optional): { k, areaM2 } adds K·½ρv² in series.
 */
export function solveOperatingPoint({
  fan, fanCount, system, heatLoadW = 300, densityKgM3 = 1.204, cpJkgK = 1006, ductLoss = null,
}) {
  if (!Number.isInteger(fanCount) || fanCount < 1) throw new Error('fan_count must be a positive integer');
  for (const [name, v] of [['heat_load_w', heatLoadW], ['air_density_kg_m3', densityKgM3], ['air_specific_heat_j_kg_k', cpJkgK]]) {
    if (!Number.isFinite(v)) throw new Error(`${name} must be finite`);
  }
  if (heatLoadW < 0) throw new Error('heat_load_w must be non-negative');
  if (densityKgM3 <= 0 || cpJkgK <= 0) throw new Error('air density and specific heat must be greater than 0');

  const freeAir = fan.points[fan.points.length - 1][0];
  let base, upper, resistanceK = null, systemModel;
  if (system.type === 'table') {
    systemModel = 'measured/digitized piecewise-linear system curve';
    upper = Math.min(fanCount * freeAir, system.curve.maxFlow);
    base = (q) => system.curve.pressureAt(q);
  } else {
    const { pressureMmH2O: p, flowCfm: q0 } = system;
    if (!Number.isFinite(p) || !Number.isFinite(q0)) throw new Error('quadratic reference values must be finite');
    if (p <= 0 || q0 <= 0) throw new Error('system reference pressure and flow must both be greater than 0');
    resistanceK = p / (q0 ** 2);
    systemModel = 'quadratic approximation fitted from one reference point';
    upper = fanCount * freeAir;
    base = (q) => resistanceK * q ** 2;
  }
  const useDuct = ductLoss && ductLoss.k > 0;
  if (useDuct && !(ductLoss.areaM2 > 0)) throw new Error('duct outlet area must be positive');
  const systemAt = useDuct ? (q) => base(q) + ductLossMmH2O(q, ductLoss.k, ductLoss.areaM2, densityKgM3) : base;
  const residual = (q) => fan.pressureAt(q / fanCount) - systemAt(q);

  let lower = 0;
  const fLower = residual(lower);
  const fUpper = residual(upper);
  if (fLower <= 0) throw new Error('No positive-flow operating point: system pressure meets/exceeds fan shutoff pressure');
  let total;
  if (fUpper > 0) {
    if (system.type === 'table' && system.curve.maxFlow < fanCount * freeAir) {
      throw new Error(`No intersection within supplied system-curve range (0–${system.curve.maxFlow} CFM); add higher-flow system measurements. Extrapolation is disabled.`);
    }
    throw new Error('Could not bracket a fan/system operating point; check the curve data');
  }
  if (fUpper === 0) {
    total = upper;
  } else {
    for (let i = 0; i < 120; i++) {
      const mid = (lower + upper) / 2;
      if (residual(mid) > 0) lower = mid; else upper = mid;
      if (upper - lower <= 1e-9 * Math.max(1, upper)) break;
    }
    total = (lower + upper) / 2;
  }
  const perFan = total / fanCount;
  const flowM3s = total * CFM_TO_M3_S;
  if (flowM3s <= 0) throw new Error('Solved operating point has zero flow');
  const ductPart = useDuct ? ductLossMmH2O(total, ductLoss.k, ductLoss.areaM2, densityKgM3) : 0;
  return {
    fan_count_parallel: fanCount,
    total_flow_cfm: total,
    per_fan_flow_cfm: perFan,
    fan_static_pressure_mmh2o: fan.pressureAt(perFan),
    system_pressure_drop_mmh2o: systemAt(total),
    duct_loss_mmh2o: ductPart,
    system_resistance_k_mmh2o_per_cfm2: resistanceK,
    heat_load_w: heatLoadW,
    ideal_bulk_air_temperature_rise_c: heatLoadW / (densityKgM3 * cpJkgK * flowM3s),
    system_model: systemModel + (useDuct ? ' + duct loss K·½ρv²' : ''),
  };
}

/** Sample both curves for plotting: fan array curve and total system curve. */
export function sampleCurves({ fan, fanCount, system, densityKgM3 = 1.204, ductLoss = null, samples = 80 }) {
  const freeAir = fan.points[fan.points.length - 1][0] * fanCount;
  const fanPts = fan.points.map(([q, p]) => [q * fanCount, p]);
  const sysMax = system.type === 'table' ? system.curve.maxFlow : freeAir;
  const sysPts = [];
  for (let i = 0; i <= samples; i++) {
    const q = (sysMax * i) / samples;
    let p = system.type === 'table' ? system.curve.pressureAt(q) : (system.pressureMmH2O / system.flowCfm ** 2) * q * q;
    if (ductLoss && ductLoss.k > 0) p += ductLossMmH2O(q, ductLoss.k, ductLoss.areaM2, densityKgM3);
    sysPts.push([q, p]);
  }
  return { fanPts, sysPts, maxFlow: Math.max(freeAir, sysMax) };
}

/** Bounded linear interpolation of electrical telemetry vs RPM (no extrapolation). */
export function interpolateElectrical(points, rpm) {
  const lo = points[0].rpm, hi = points[points.length - 1].rpm;
  if (!(rpm >= lo && rpm <= hi)) return null;
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i], b = points[i + 1];
    if (rpm === a.rpm) return { current_a: a.current_a, power_w: a.power_w };
    if (rpm < b.rpm) {
      const f = (rpm - a.rpm) / (b.rpm - a.rpm);
      return { current_a: a.current_a + f * (b.current_a - a.current_a), power_w: a.power_w + f * (b.power_w - a.power_w) };
    }
  }
  const last = points[points.length - 1];
  return { current_a: last.current_a, power_w: last.power_w };
}

// ------------------------------------------------------------- acoustics

const dbSum = (levels) => 10 * Math.log10(levels.reduce((s, l) => s + 10 ** (l / 10), 0));

/**
 * First-order SPL budget: identical uncorrelated point sources, free-field
 * inverse-square distance loss, energy summation. Not an acoustic simulation.
 */
export function acousticBudget({ fanCount, fanSplDb, refDistanceM, listenerDistanceM, targetDb, ambientDb = 0, systemDb = null }) {
  if (!(fanCount >= 1) || !(refDistanceM > 0) || !(listenerDistanceM > 0) || !Number.isFinite(fanSplDb)) return null;
  const distanceCorrection = -20 * Math.log10(listenerDistanceM / refDistanceM);
  const oneFan = fanSplDb + distanceCorrection;
  const fans = oneFan + 10 * Math.log10(fanCount);
  const others = [];
  if (ambientDb > 0) others.push(ambientDb);
  if (systemDb !== null && Number.isFinite(systemDb) && systemDb > 0) others.push(systemDb);
  const total = dbSum([fans, ...others]);
  const otherEnergy = others.reduce((s, l) => s + 10 ** (l / 10), 0);
  const remaining = 10 ** (targetDb / 10) - otherEnergy;
  const maxOneFanAtRef = remaining > 0 ? 10 * Math.log10(remaining) - 10 * Math.log10(fanCount) - distanceCorrection : null;
  return {
    distance_correction_db: distanceCorrection,
    fans_only_db: fans,
    total_db: total,
    margin_db: targetDb - total,
    max_one_fan_spl_at_ref_db: maxOneFanAtRef,
    within_target: total <= targetDb,
  };
}
