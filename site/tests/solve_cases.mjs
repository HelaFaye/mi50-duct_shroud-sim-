// Reads solver cases (JSON array) on stdin and prints JS solver results as JSON.
// Used by tests/test_site_parity.py to compare against analysis/fan_operating_point.py.
import { fanCurve, systemCurve, solveOperatingPoint } from '../js/solver.js';

let input = '';
process.stdin.setEncoding('utf8');
for await (const chunk of process.stdin) input += chunk;
const results = JSON.parse(input).map((c) => {
  try {
    const system = c.system.type === 'table'
      ? { type: 'table', curve: systemCurve(c.system.points, 'case system') }
      : c.system;
    return { ok: solveOperatingPoint({
      fan: fanCurve(c.fan_points, 'case fan'), fanCount: c.fan_count, system,
      heatLoadW: c.heat_load_w, ductLoss: c.duct_loss || null,
    }) };
  } catch (e) {
    return { error: e.message };
  }
});
process.stdout.write(JSON.stringify(results));
