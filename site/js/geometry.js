// Parametric MI50 fan-shroud geometry as a single closed triangle mesh.
//
// Pure module: no DOM or three.js dependency, so it runs in Node tests and in
// the browser. Coordinates are millimetres:
//   x — airflow direction / card length (fan plate at x = 0, card beyond the sleeve)
//   y — card height direction
//   z — card thickness (slot) direction
//
// Solid = fan plate (with fan throats and screw holes) + lofted duct wall +
// straight sleeve that slips over the cooler end. The plate and wall share
// vertices, so the result is one watertight, consistently wound shell.

export const FAN_SCREW_SPACING_MM = Object.freeze({
  40: 32, 60: 50, 80: 71.5, 92: 82.5, 120: 105, 140: 124.5,
});

/** Minimum plate material between features (throat, holes, wall). */
export const MIN_WEB_MM = 0.5;
const THROAT_SEGMENTS_PER_OCTANT = 8;
const HOLE_SEGMENTS_PER_HALF = 8;

/** Resolve user parameters into concrete dimensions (no validation). */
export function deriveDimensions(p) {
  const S = p.fan_size_mm;
  const t = p.wall_thickness_mm;
  const spacing = FAN_SCREW_SPACING_MM[S];
  const throat = p.fan_throat_diameter_mm > 0 ? p.fan_throat_diameter_mm : S - 2 * t - 2 * MIN_WEB_MM;
  const alongHeight = p.fan_row_axis !== 'thickness';
  // (u, v): u runs along the fan row, v across it.
  const arrayU = p.fan_count * S;
  const arrayV = S;
  const outletY = p.cooler_height_mm + 2 * p.fit_clearance_mm;
  const outletZ = p.cooler_thickness_mm + 2 * p.fit_clearance_mm;
  return {
    S, t, spacing,
    holeOffset: spacing === undefined ? undefined : spacing / 2,
    holeRadius: p.screw_hole_diameter_mm / 2,
    throatRadius: throat / 2,
    alongHeight,
    arrayU, arrayV,
    plate: p.plate_thickness_mm,
    ductLength: p.duct_length_mm,
    sleeveLength: p.sleeve_length_mm,
    outletInnerY: outletY,
    outletInnerZ: outletZ,
    outletOffsetY: p.outlet_offset_y_mm,
    outletOffsetZ: p.outlet_offset_z_mm,
    // inner (passage) extents at the fan end, in y/z
    fanInnerY: (alongHeight ? arrayU : arrayV) - 2 * t,
    fanInnerZ: (alongHeight ? arrayV : arrayU) - 2 * t,
    totalLength: p.plate_thickness_mm + p.duct_length_mm + p.sleeve_length_mm,
  };
}

// ---------------------------------------------------------------- 2D helpers

function signedArea(poly) {
  let a = 0;
  for (let i = 0; i < poly.length; i++) {
    const [x1, y1] = poly[i];
    const [x2, y2] = poly[(i + 1) % poly.length];
    a += x1 * y2 - x2 * y1;
  }
  return a / 2;
}

function cross(o, a, b) {
  return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
}

function pointInTriangleInclusive(p, a, b, c) {
  const eps = 1e-12;
  const d1 = cross(a, b, p);
  const d2 = cross(b, c, p);
  const d3 = cross(c, a, p);
  return d1 >= -eps && d2 >= -eps && d3 >= -eps;
}

/**
 * Ear-clipping triangulation of a simple polygon. Returns index triples into
 * the input, counter-clockwise. Points lying on a candidate ear's boundary
 * block that ear, so collinear vertices never produce T-junctions.
 */
export function triangulatePolygon(poly) {
  const n = poly.length;
  if (n < 3) throw new Error('polygon needs at least 3 vertices');
  let idx = [...Array(n).keys()];
  if (signedArea(poly) < 0) idx.reverse();
  const tris = [];
  let guard = 0;
  while (idx.length > 3) {
    if (++guard > 10 * n * n) throw new Error('triangulation failed (polygon not simple?)');
    let clipped = false;
    for (let k = 0; k < idx.length; k++) {
      const ia = idx[(k + idx.length - 1) % idx.length];
      const ib = idx[k];
      const ic = idx[(k + 1) % idx.length];
      const a = poly[ia], b = poly[ib], c = poly[ic];
      if (cross(a, b, c) <= 1e-12) continue; // reflex or collinear
      let blocked = false;
      for (const j of idx) {
        if (j === ia || j === ib || j === ic) continue;
        const q = poly[j];
        if ((q[0] === a[0] && q[1] === a[1]) || (q[0] === b[0] && q[1] === b[1]) || (q[0] === c[0] && q[1] === c[1])) continue;
        if (pointInTriangleInclusive(q, a, b, c)) { blocked = true; break; }
      }
      if (blocked) continue;
      tris.push([ia, ib, ic]);
      idx.splice(k, 1);
      clipped = true;
      break;
    }
    if (!clipped) throw new Error('triangulation failed: no ear found');
  }
  if (cross(poly[idx[0]], poly[idx[1]], poly[idx[2]]) <= 1e-12) {
    throw new Error('triangulation failed: degenerate final triangle');
  }
  tris.push([idx[0], idx[1], idx[2]]);
  return tris;
}

// ------------------------------------------------------------ plate regions

/**
 * Build the plate face as polygons in (u, v). Each fan cell is split into
 * eight octants along its axes and diagonals; each octant contains a 45° arc
 * of the fan throat and half of one screw hole, so no polygon has interior
 * holes. Edge tags: 'throat' | 'hole' | 'rim' (meets the duct wall) | 'internal'.
 */
export function plateOctants(d) {
  const { S, t, fanCount } = d;
  const r = d.throatRadius;
  const h = d.holeOffset;
  const rh = d.holeRadius;
  const s2 = Math.SQRT1_2;

  // Base arc points for angle 0..45° and half hole arc, in the ++ quadrant,
  // for the octant below the diagonal (v <= u).
  const throatArc = [];
  for (let i = 0; i <= THROAT_SEGMENTS_PER_OCTANT; i++) {
    if (i === THROAT_SEGMENTS_PER_OCTANT) { throatArc.push([r * s2, r * s2]); break; }
    const a = (Math.PI / 4) * (i / THROAT_SEGMENTS_PER_OCTANT);
    throatArc.push([r * Math.cos(a), r * Math.sin(a)]);
  }
  const holeArc = []; // from near diagonal point, around the v<u side, to far point
  for (let i = 0; i <= HOLE_SEGMENTS_PER_HALF; i++) {
    if (i === 0) { holeArc.push([h - rh * s2, h - rh * s2]); continue; }
    if (i === HOLE_SEGMENTS_PER_HALF) { holeArc.push([h + rh * s2, h + rh * s2]); continue; }
    const a = -0.75 * Math.PI + Math.PI * (i / HOLE_SEGMENTS_PER_HALF);
    holeArc.push([h + rh * Math.cos(a), h + rh * Math.sin(a)]);
  }

  // One octant: returns [{p:[u,v], tag-of-edge-from-this-vertex}]
  function octant(cornerU, cornerV, uBoundary) {
    const verts = [];
    for (let i = 0; i < throatArc.length; i++) {
      verts.push({ p: throatArc[i], tag: i < throatArc.length - 1 ? 'throat' : 'internal' });
    }
    for (let i = 0; i < holeArc.length; i++) {
      verts.push({ p: holeArc[i], tag: i < holeArc.length - 1 ? 'hole' : 'internal' });
    }
    verts.push({ p: [cornerU, cornerV], tag: uBoundary ? 'rim' : 'internal' });
    verts.push({ p: [cornerU, 0], tag: 'internal' });
    return verts;
  }

  const polys = [];
  for (let cell = 0; cell < fanCount; cell++) {
    const cu = -d.arrayU / 2 + S / 2 + cell * S;
    for (const su of [1, -1]) {
      for (const sv of [1, -1]) {
        const uBoundary = su > 0 ? cell === fanCount - 1 : cell === 0;
        const vBoundary = true; // single row: both v sides meet the wall
        const cornerU = uBoundary ? S / 2 - t : S / 2;
        const cornerV = vBoundary ? S / 2 - t : S / 2;
        // octant below diagonal (adjacent to the u axis)
        const a = octant(cornerU, cornerV, uBoundary);
        // octant above diagonal: mirror of an octant whose corner is swapped
        const bSrc = octant(cornerV, cornerU, vBoundary);
        const b = bSrc.map(({ p }) => ({ p: [p[1], p[0]] }));
        // mirroring reverses traversal; re-tag edges for the reversed order
        const bTagged = [];
        for (let i = b.length - 1; i >= 0; i--) {
          const prev = (i + b.length - 1) % b.length;
          bTagged.push({ p: b[i].p, tag: bSrc[prev].tag });
        }
        for (const poly of [a, bTagged]) {
          polys.push(poly.map(({ p, tag }) => ({ p: [cu + su * p[0], sv * p[1]], tag })));
        }
      }
    }
  }
  return polys;
}

// ------------------------------------------------------------- mesh builder

class MeshBuilder {
  constructor() { this.tris = []; }
  /** Add triangle a,b,c (3D points), flipped if needed so its normal points along `dir`. */
  add(a, b, c, dir) {
    const ux = b[0] - a[0], uy = b[1] - a[1], uz = b[2] - a[2];
    const vx = c[0] - a[0], vy = c[1] - a[1], vz = c[2] - a[2];
    const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    const dot = nx * dir[0] + ny * dir[1] + nz * dir[2];
    if (dot >= 0) this.tris.push(a, b, c); else this.tris.push(a, c, b);
  }
  quad(a, b, c, d, dir) { this.add(a, b, c, dir); this.add(a, c, d, dir); }
  toFloat32() {
    const out = new Float32Array(this.tris.length * 3);
    this.tris.forEach((p, i) => { out[3 * i] = p[0]; out[3 * i + 1] = p[1]; out[3 * i + 2] = p[2]; });
    return out;
  }
}

const key2 = ([u, v]) => `${Math.round(u * 1e6)},${Math.round(v * 1e6)}`;

/** Chain 'rim' edges into one closed loop, counter-clockwise in (u, v). */
function rimLoop(polys) {
  const next = new Map();
  const pts = new Map();
  for (const poly of polys) {
    for (let i = 0; i < poly.length; i++) {
      if (poly[i].tag !== 'rim') continue;
      const a = poly[i].p, b = poly[(i + 1) % poly.length].p;
      // orient each rim edge CCW around the origin of the array
      const ccw = a[0] * b[1] - a[1] * b[0] > 0;
      const [s, e] = ccw ? [a, b] : [b, a];
      next.set(key2(s), key2(e));
      pts.set(key2(s), s);
      pts.set(key2(e), e);
    }
  }
  const start = next.keys().next().value;
  const loop = [];
  let k = start;
  do {
    loop.push(pts.get(k));
    k = next.get(k);
    if (k === undefined) throw new Error('rim loop is not closed');
    if (loop.length > next.size + 1) throw new Error('rim loop does not terminate');
  } while (k !== start);
  if (loop.length !== next.size) throw new Error('rim edges do not form a single loop');
  // rotate so the loop starts at a corner (max u, max v)
  let best = 0;
  loop.forEach((p, i) => { if (p[0] + p[1] > loop[best][0] + loop[best][1] + 1e-9) best = i; });
  return loop.slice(best).concat(loop.slice(0, best));
}

/**
 * Triangulate the ring between an outer axis-aligned rectangle (4 corners) and
 * an inner rectangle loop whose sides may carry extra collinear vertices.
 * Both are given in (u, v); `lift` maps to 3D.
 */
function ringFaces(mb, outerHalfU, outerHalfV, outerCU, outerCV, innerLoop, lift, dir) {
  const isCorner = (p, loop) => {
    const us = loop.map((q) => q[0]), vs = loop.map((q) => q[1]);
    const eps = 1e-7;
    const onU = Math.abs(p[0] - Math.max(...us)) < eps || Math.abs(p[0] - Math.min(...us)) < eps;
    const onV = Math.abs(p[1] - Math.max(...vs)) < eps || Math.abs(p[1] - Math.min(...vs)) < eps;
    return onU && onV;
  };
  const cornerIdx = innerLoop.map((p, i) => (isCorner(p, innerLoop) ? i : -1)).filter((i) => i >= 0);
  if (cornerIdx.length !== 4) throw new Error('inner loop must have exactly four corners');
  const outer = (p) => [
    outerCU + Math.sign(p[0] - innerCentre(innerLoop)[0]) * outerHalfU,
    outerCV + Math.sign(p[1] - innerCentre(innerLoop)[1]) * outerHalfV,
  ];
  for (let c = 0; c < 4; c++) {
    const i0 = cornerIdx[c];
    const i1 = cornerIdx[(c + 1) % 4];
    const O0 = outer(innerLoop[i0]);
    const O1 = outer(innerLoop[i1]);
    const side = [];
    for (let i = i0; ; i = (i + 1) % innerLoop.length) { side.push(innerLoop[i]); if (i === i1) break; }
    for (let j = 0; j < side.length - 1; j++) mb.add(lift(O0), lift(side[j]), lift(side[j + 1]), dir);
    mb.add(lift(O0), lift(side[side.length - 1]), lift(O1), dir);
  }
}

function innerCentre(loop) {
  const us = loop.map((q) => q[0]), vs = loop.map((q) => q[1]);
  return [(Math.max(...us) + Math.min(...us)) / 2, (Math.max(...vs) + Math.min(...vs)) / 2];
}

/**
 * Build the shroud mesh. Returns { positions: Float32Array (9 per triangle),
 * triangleCount, bounds }. Throws if the parameters cannot form valid geometry;
 * call validateParameters() first for user-facing messages.
 */
export function buildShroudMesh(p) {
  const d = deriveDimensions(p);
  d.fanCount = p.fan_count;
  const mb = new MeshBuilder();

  // (u, v) -> (y, z) at the fan end
  const toYZ = (u, v) => (d.alongHeight ? [u, v] : [v, u]);
  const lift = (x) => ([u, v]) => { const [y, z] = toYZ(u, v); return [x, y, z]; };
  const xPlate = d.plate;
  const xOutlet = d.plate + d.ductLength;
  const xEnd = xOutlet + d.sleeveLength;

  // ---- plate faces (top at x = plate, bottom at x = 0) and hole walls
  const polys = plateOctants(d);
  for (const poly of polys) {
    const pts = poly.map((v) => v.p);
    for (const [i, j, k] of triangulatePolygon(pts)) {
      mb.add(lift(xPlate)(pts[i]), lift(xPlate)(pts[j]), lift(xPlate)(pts[k]), [1, 0, 0]);
      mb.add(lift(0)(pts[i]), lift(0)(pts[j]), lift(0)(pts[k]), [-1, 0, 0]);
    }
    for (let i = 0; i < poly.length; i++) {
      const tag = poly[i].tag;
      if (tag !== 'throat' && tag !== 'hole') continue;
      const a = pts[i], b = pts[(i + 1) % pts.length];
      // outward from the solid = towards the hole/throat centre
      let centre;
      if (tag === 'throat') {
        const cell = Math.floor((a[0] + d.arrayU / 2) / d.S);
        centre = [-d.arrayU / 2 + d.S / 2 + Math.min(cell, d.fanCount - 1) * d.S, 0];
      } else {
        const cellCu = -d.arrayU / 2 + d.S / 2 + Math.min(Math.floor((a[0] + d.arrayU / 2) / d.S), d.fanCount - 1) * d.S;
        centre = [cellCu + Math.sign(a[0] - cellCu) * d.holeOffset, Math.sign(a[1]) * d.holeOffset];
      }
      const mid = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
      const [dy, dz] = toYZ(centre[0] - mid[0], centre[1] - mid[1]);
      mb.quad(lift(0)(a), lift(0)(b), lift(xPlate)(b), lift(xPlate)(a), [0, dy, dz]);
    }
  }

  // ---- duct wall
  const loop = rimLoop(polys); // inner rectangle at the fan end, CCW in (u, v)
  const halfU = d.arrayU / 2 - d.t;
  const halfV = d.arrayV / 2 - d.t;
  // outlet inner rectangle in (u, v) and its centre offset
  const outHalfY = d.outletInnerY / 2, outHalfZ = d.outletInnerZ / 2;
  const [outHalfU, outHalfV] = d.alongHeight ? [outHalfY, outHalfZ] : [outHalfZ, outHalfY];
  const [offU, offV] = d.alongHeight ? [d.outletOffsetY, d.outletOffsetZ] : [d.outletOffsetZ, d.outletOffsetY];
  const outletLoop = loop.map(([u, v]) => [offU + (u / halfU) * outHalfU, offV + (v / halfV) * outHalfV]);

  // inner wall: fan end (x = plate) -> outlet -> sleeve end; normals point into the passage
  const innerSections = [[xPlate, loop, [0, 0]], [xOutlet, outletLoop, [offU, offV]], [xEnd, outletLoop, [offU, offV]]];
  for (let s = 0; s < innerSections.length - 1; s++) {
    const [xa, la, ca] = innerSections[s];
    const [xb, lb, cb] = innerSections[s + 1];
    for (let i = 0; i < la.length; i++) {
      const j = (i + 1) % la.length;
      const mid = [(la[i][0] + la[j][0]) / 2 - ca[0], (la[i][1] + la[j][1]) / 2 - ca[1]];
      const inward = sideNormal(mid, la, ca).map((c) => -c);
      const [dy, dz] = toYZ(inward[0], inward[1]);
      mb.quad(lift(xa)(la[i]), lift(xa)(la[j]), lift(xb)(lb[j]), lift(xb)(lb[i]), [0, dy, dz]);
    }
  }

  // outer wall: 4-corner rectangles at x = 0, plate, outlet, end
  const outerRect = (cu, cv, hu, hv) => [[cu + hu, cv + hv], [cu - hu, cv + hv], [cu - hu, cv - hv], [cu + hu, cv - hv]];
  const fanOuter = outerRect(0, 0, d.arrayU / 2, d.arrayV / 2);
  const outletOuter = outerRect(offU, offV, outHalfU + d.t, outHalfV + d.t);
  const outerSections = [[0, fanOuter], [xPlate, fanOuter], [xOutlet, outletOuter], [xEnd, outletOuter]];
  const sideDirs = [[0, 1], [-1, 0], [0, -1], [1, 0]]; // outward normal of edge i -> i+1
  for (let s = 0; s < outerSections.length - 1; s++) {
    const [xa, ra] = outerSections[s];
    const [xb, rb] = outerSections[s + 1];
    for (let i = 0; i < 4; i++) {
      const j = (i + 1) % 4;
      const [dy, dz] = toYZ(...sideDirs[i]);
      mb.quad(lift(xa)(ra[i]), lift(xa)(ra[j]), lift(xb)(rb[j]), lift(xb)(rb[i]), [0, dy, dz]);
    }
  }

  // end rings: x = 0 (fan face, between outer frame and plate rim) and x = end
  ringFaces(mb, d.arrayU / 2, d.arrayV / 2, 0, 0, loop, lift(0), [-1, 0, 0]);
  ringFaces(mb, outHalfU + d.t, outHalfV + d.t, offU, offV, outletLoop, lift(xEnd), [1, 0, 0]);

  const positions = mb.toFloat32();
  return { positions, triangleCount: positions.length / 9, bounds: meshBounds(positions), dimensions: d };
}

function sideNormal(mid, loop, centre) {
  // outward normal of the rectangle side containing `mid` (relative to centre)
  const us = loop.map((q) => q[0] - centre[0]), vs = loop.map((q) => q[1] - centre[1]);
  const hu = Math.max(...us), hv = Math.max(...vs);
  const du = Math.abs(Math.abs(mid[0]) - hu), dv = Math.abs(Math.abs(mid[1]) - hv);
  return du < dv ? [Math.sign(mid[0]), 0] : [0, Math.sign(mid[1])];
}

export function meshBounds(positions) {
  const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < positions.length; i += 3) {
    for (let a = 0; a < 3; a++) {
      if (positions[i + a] < min[a]) min[a] = positions[i + a];
      if (positions[i + a] > max[a]) max[a] = positions[i + a];
    }
  }
  return { min, max };
}

/** Signed volume (mm³) by the divergence theorem; positive for outward winding. */
export function meshVolume(positions) {
  let v = 0;
  for (let i = 0; i < positions.length; i += 9) {
    const ax = positions[i], ay = positions[i + 1], az = positions[i + 2];
    const bx = positions[i + 3], by = positions[i + 4], bz = positions[i + 5];
    const cx = positions[i + 6], cy = positions[i + 7], cz = positions[i + 8];
    v += ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx);
  }
  return v / 6;
}

/**
 * Topology check: every undirected edge must be used by exactly two triangles
 * with opposite directions. Returns { closed, boundaryEdges, nonManifoldEdges, flippedEdges }.
 */
export function checkWatertight(positions) {
  const q = (i) => `${Math.round(positions[i] * 1e4)},${Math.round(positions[i + 1] * 1e4)},${Math.round(positions[i + 2] * 1e4)}`;
  const directed = new Map();
  for (let i = 0; i < positions.length; i += 9) {
    const v = [q(i), q(i + 3), q(i + 6)];
    for (let e = 0; e < 3; e++) {
      const k = `${v[e]}|${v[(e + 1) % 3]}`;
      directed.set(k, (directed.get(k) || 0) + 1);
    }
  }
  let boundaryEdges = 0, nonManifoldEdges = 0, flippedEdges = 0;
  for (const [k, n] of directed) {
    const [a, b] = k.split('|');
    const back = directed.get(`${b}|${a}`) || 0;
    if (n > 1) flippedEdges += 1;
    if (back === 0) boundaryEdges += 1;
    else if (n + back > 2) nonManifoldEdges += 1;
  }
  return { closed: boundaryEdges === 0 && nonManifoldEdges === 0 && flippedEdges === 0, boundaryEdges, nonManifoldEdges, flippedEdges };
}

/** Binary STL (little-endian) from a positions array. */
export function toBinarySTL(positions, header = 'MI50 shroud') {
  const count = positions.length / 9;
  const buffer = new ArrayBuffer(84 + 50 * count);
  const view = new DataView(buffer);
  const text = header.slice(0, 80);
  for (let i = 0; i < text.length; i++) view.setUint8(i, text.charCodeAt(i) & 0x7f);
  view.setUint32(80, count, true);
  let o = 84;
  for (let t = 0; t < count; t++) {
    const i = 9 * t;
    const ux = positions[i + 3] - positions[i], uy = positions[i + 4] - positions[i + 1], uz = positions[i + 5] - positions[i + 2];
    const vx = positions[i + 6] - positions[i], vy = positions[i + 7] - positions[i + 1], vz = positions[i + 8] - positions[i + 2];
    let nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    const len = Math.hypot(nx, ny, nz) || 1;
    nx /= len; ny /= len; nz /= len;
    for (const value of [nx, ny, nz]) { view.setFloat32(o, value, true); o += 4; }
    for (let k = 0; k < 9; k++) { view.setFloat32(o, positions[i + k], true); o += 4; }
    view.setUint16(o, 0, true); o += 2;
  }
  return buffer;
}
