import test from 'node:test';
import assert from 'node:assert/strict';
import { FANS } from '../js/fan_data.js';
import {
  acousticBudget, affinityScale, ductLossMmH2O, fanCurve, interpolateElectrical, solveOperatingPoint, systemCurve,
} from '../js/solver.js';

const fan = fanCurve([[0, 10], [50, 5], [100, 0]], 'synthetic');

test('analytic intersection: linear fan against quadratic system', () => {
  // fan p = 10 - 0.1 q ; system p = 0.001 q^2 → q = (-0.1 + sqrt(0.01 + 0.04)) / 0.002
  const r = solveOperatingPoint({ fan, fanCount: 1, system: { type: 'quadratic', pressureMmH2O: 2.5, flowCfm: 50 } });
  const exact = (-0.1 + Math.sqrt(0.01 + 0.04)) / 0.002;
  assert.ok(Math.abs(r.total_flow_cfm - exact) < 1e-6);
});

test('duct loss in series equals a quadratic with the combined resistance', () => {
  const area = 0.004; // m²
  const k = 1.5;
  const extraK = ductLossMmH2O(1, k, area, 1.204); // mmH2O per CFM² (loss is ∝ Q²)
  const a = solveOperatingPoint({ fan, fanCount: 2, system: { type: 'quadratic', pressureMmH2O: 2, flowCfm: 50 }, ductLoss: { k, areaM2: area } });
  const b = solveOperatingPoint({ fan, fanCount: 2, system: { type: 'quadratic', pressureMmH2O: 2 + extraK * 2500, flowCfm: 50 } });
  assert.ok(Math.abs(a.total_flow_cfm - b.total_flow_cfm) < 1e-6);
  assert.ok(a.duct_loss_mmh2o > 0);
});

test('tabulated system curve too short is reported, not extrapolated', () => {
  assert.throws(() => solveOperatingPoint({ fan, fanCount: 1, system: { type: 'table', curve: systemCurve([[0, 0], [10, 0.5]]) } }),
    /No intersection within supplied system-curve range/);
});

test('affinity scaling follows Q∝N and p∝N²', () => {
  assert.deepEqual(affinityScale([[0, 4], [10, 0]], 0.5), [[0, 1], [5, 0]]);
});

test('embedded fan data loads as valid fan curves', () => {
  assert.ok(FANS.length >= 3);
  for (const f of FANS) {
    const c = fanCurve(f.points, f.id);
    assert.equal(c.points[c.points.length - 1][1], 0);
    assert.match(f.sha256, /^[0-9a-f]{64}$/);
  }
});

test('electrical interpolation is bounded and exact at table points', () => {
  const pts = FANS.find((f) => f.electrical).electrical.points;
  const last = pts[pts.length - 1];
  assert.deepEqual(interpolateElectrical(pts, last.rpm), { current_a: last.current_a, power_w: last.power_w });
  assert.equal(interpolateElectrical(pts, last.rpm + 1), null);
});

test('acoustic budget: doubling identical fans adds ~3 dB; distance doubling subtracts ~6 dB', () => {
  const one = acousticBudget({ fanCount: 1, fanSplDb: 30, refDistanceM: 1, listenerDistanceM: 1, targetDb: 40 });
  const two = acousticBudget({ fanCount: 2, fanSplDb: 30, refDistanceM: 1, listenerDistanceM: 1, targetDb: 40 });
  assert.ok(Math.abs(two.fans_only_db - one.fans_only_db - 3.0103) < 1e-3);
  const far = acousticBudget({ fanCount: 1, fanSplDb: 30, refDistanceM: 1, listenerDistanceM: 2, targetDb: 40 });
  assert.ok(Math.abs(one.fans_only_db - far.fans_only_db - 6.0206) < 1e-3);
  // max one-fan SPL reproduces the target exactly when substituted back
  const b = acousticBudget({ fanCount: 3, fanSplDb: 30, refDistanceM: 1, listenerDistanceM: 0.5, targetDb: 35, ambientDb: 25 });
  const check = acousticBudget({ fanCount: 3, fanSplDb: b.max_one_fan_spl_at_ref_db, refDistanceM: 1, listenerDistanceM: 0.5, targetDb: 35, ambientDb: 25 });
  assert.ok(Math.abs(check.total_db - 35) < 1e-9);
});
