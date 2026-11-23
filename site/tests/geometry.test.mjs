import test from 'node:test';
import assert from 'node:assert/strict';
import {
  FAN_SCREW_SPACING_MM, buildShroudMesh, checkWatertight, meshVolume, toBinarySTL, triangulatePolygon,
} from '../js/geometry.js';
import { defaultParameters, normalizeParameters, validateParameters } from '../js/params.js';
import { generateScad } from '../js/scad.js';

function variants() {
  const out = [];
  for (const size of Object.keys(FAN_SCREW_SPACING_MM).map(Number)) {
    for (const count of [1, 2, 3]) {
      for (const axis of ['height', 'thickness']) {
        for (const offset of [0, 7.5]) {
          out.push({ ...defaultParameters(), fan_size_mm: size, fan_count: count, fan_row_axis: axis,
            outlet_offset_y_mm: offset, outlet_offset_z_mm: -offset / 3,
            wall_thickness_mm: size <= 40 ? 1.2 : 2, screw_hole_diameter_mm: size <= 40 ? 3.4 : 4.4 });
        }
      }
    }
  }
  return out;
}

test('every valid parameter combination yields a closed, outward-wound solid', () => {
  let built = 0;
  for (const p of variants()) {
    const { errors } = validateParameters(p);
    if (errors.length) continue;
    const mesh = buildShroudMesh(p);
    const topo = checkWatertight(mesh.positions);
    assert.ok(topo.closed, `${JSON.stringify(p)} → ${JSON.stringify(topo)}`);
    assert.ok(meshVolume(mesh.positions) > 0, 'volume must be positive (outward normals)');
    built += 1;
  }
  assert.ok(built >= 60, `only ${built} variants were valid`);
});

test('default shroud volume matches an independent hand calculation', () => {
  // plate (inner region minus throat & holes) + fan-end wall ring + lofted wall (Simpson, exact for
  // quadratic area) + sleeve. Circles are 64/16-gons in the mesh: ~0.06 % difference.
  const p = defaultParameters();
  const tp = 3, t = 2, L = 60, Ls = 15;
  const throatR = (92 - 4 - 1) / 2, holeR = 2.2;
  const plate = (88 * 88 - Math.PI * throatR ** 2 - 4 * Math.PI * holeR ** 2) * tp;
  const ring = (92 * 92 - 88 * 88) * tp;
  const area = (oy, oz, iy, iz) => oy * oz - iy * iz;
  const a0 = area(92, 92, 88, 88), a1 = area(104.8, 40.8, 100.8, 36.8);
  const am = area((92 + 104.8) / 2, (92 + 40.8) / 2, (88 + 100.8) / 2, (88 + 36.8) / 2);
  const loft = (L / 6) * (a0 + 4 * am + a1);
  const expected = plate + ring + loft + a1 * Ls;
  const actual = meshVolume(buildShroudMesh(p).positions);
  assert.ok(Math.abs(actual - expected) / expected < 1e-3, `${actual} vs ${expected}`);
});

test('triangulation of a concave polygon with collinear vertices covers its area', () => {
  const poly = [[0, 0], [2, 0], [4, 0], [4, 4], [2, 2], [0, 4]];
  const tris = triangulatePolygon(poly);
  const area = tris.reduce((s, [a, b, c]) => s + Math.abs(
    (poly[b][0] - poly[a][0]) * (poly[c][1] - poly[a][1]) - (poly[b][1] - poly[a][1]) * (poly[c][0] - poly[a][0])) / 2, 0);
  assert.equal(tris.length, poly.length - 2);
  assert.ok(Math.abs(area - 12) < 1e-12);
});

test('binary STL has the expected size and triangle count', () => {
  const mesh = buildShroudMesh(defaultParameters());
  const buf = toBinarySTL(mesh.positions);
  assert.equal(buf.byteLength, 84 + 50 * mesh.triangleCount);
  assert.equal(new DataView(buf).getUint32(80, true), mesh.triangleCount);
});

test('validation rejects conflicting fan features and flags envelope overruns', () => {
  const tooBigThroat = validateParameters({ ...defaultParameters(), fan_throat_diameter_mm: 95 });
  assert.ok(tooBigThroat.errors.some((e) => /throat/i.test(e)));
  const holesInWall = validateParameters({ ...defaultParameters(), fan_size_mm: 40, wall_thickness_mm: 3 });
  assert.ok(holesInWall.errors.some((e) => /screw holes/i.test(e)));
  const wide = validateParameters({ ...defaultParameters(), fan_size_mm: 120 });
  assert.equal(wide.errors.length, 0);
  assert.ok(wide.warnings.some((w) => /dual-slot/.test(w)));
  const outOfRange = validateParameters({ ...defaultParameters(), duct_length_mm: 1 });
  assert.ok(outOfRange.errors.length > 0);
});

test('normalizeParameters keeps known keys, coerces types, and drops unknown keys', () => {
  const p = normalizeParameters({ fan_size_mm: '120', fan_count: '2.6', bogus: 1, fan_row_axis: 'nope' });
  assert.equal(p.fan_size_mm, 120);
  assert.equal(p.fan_count, 3);
  assert.equal(p.fan_row_axis, 'height');
  assert.ok(!('bogus' in p));
});

test('generated OpenSCAD declares every parameter with its current value', () => {
  const p = { ...defaultParameters(), fan_size_mm: 120, fan_row_axis: 'thickness' };
  const scad = generateScad(p);
  for (const [k, v] of Object.entries(p)) {
    assert.match(scad, new RegExp(`^${k} = ${typeof v === 'string' ? `"${v}"` : v};`, 'm'));
  }
});
