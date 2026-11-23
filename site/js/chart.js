// Minimal SVG pressure–flow chart (no dependencies).
const NS = 'http://www.w3.org/2000/svg';

function el(name, attrs = {}, text) {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text !== undefined) node.textContent = text;
  return node;
}

function niceStep(range, target = 6) {
  const raw = range / target;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  return (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
}

export function drawPQChart(svg, { fanPts, sysPts, point }) {
  svg.replaceChildren(svg.querySelector('title') || el('title', {}, 'Pressure–flow chart'));
  const W = 640, H = 360, m = { l: 56, r: 16, t: 16, b: 44 };
  const maxQ = Math.max(...fanPts.map((p) => p[0]), ...sysPts.map((p) => p[0])) * 1.02;
  const maxP = Math.max(fanPts[0][1], ...sysPts.map((p) => p[1]).filter((p) => p <= fanPts[0][1] * 1.6)) * 1.08;
  const x = (q) => m.l + (q / maxQ) * (W - m.l - m.r);
  const y = (p) => H - m.b - (Math.min(p, maxP) / maxP) * (H - m.t - m.b);

  const grid = el('g', { class: 'grid' });
  const axis = el('g', { class: 'axis' });
  const qs = niceStep(maxQ), ps = niceStep(maxP, 5);
  for (let q = 0; q <= maxQ + 1e-9; q += qs) {
    grid.append(el('line', { x1: x(q), x2: x(q), y1: m.t, y2: H - m.b }));
    axis.append(el('text', { x: x(q), y: H - m.b + 16, 'text-anchor': 'middle' }, +q.toFixed(4)));
  }
  for (let p = 0; p <= maxP + 1e-9; p += ps) {
    grid.append(el('line', { x1: m.l, x2: W - m.r, y1: y(p), y2: y(p) }));
    axis.append(el('text', { x: m.l - 8, y: y(p) + 4, 'text-anchor': 'end' }, +p.toFixed(4)));
  }
  axis.append(el('line', { x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b }));
  axis.append(el('line', { x1: m.l, x2: m.l, y1: m.t, y2: H - m.b }));
  axis.append(el('text', { x: (W + m.l) / 2, y: H - 8, 'text-anchor': 'middle' }, 'Total flow (CFM)'));
  axis.append(el('text', { x: 14, y: (H - m.b + m.t) / 2, 'text-anchor': 'middle', transform: `rotate(-90 14 ${(H - m.b + m.t) / 2})` }, 'Static pressure (mmH₂O)'));
  svg.append(grid, axis);

  const path = (pts) => pts.map(([q, p], i) => `${i ? 'L' : 'M'}${x(q).toFixed(1)},${y(p).toFixed(1)}`).join('');
  const clip = el('clipPath', { id: 'pq-clip' });
  clip.append(el('rect', { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b }));
  svg.append(clip);
  svg.append(el('path', { d: path(sysPts), class: 'system-line', 'clip-path': 'url(#pq-clip)' }));
  svg.append(el('path', { d: path(fanPts), class: 'fan-line' }));
  if (point) {
    svg.append(el('circle', { cx: x(point[0]), cy: y(point[1]), r: 5, class: 'op-point' }));
    const right = x(point[0]) > W * 0.7;
    svg.append(el('text', { x: x(point[0]) + (right ? -10 : 10), y: y(point[1]) - 10, 'text-anchor': right ? 'end' : 'start', class: 'op-label' },
      `${point[0].toFixed(1)} CFM @ ${point[1].toFixed(2)} mmH₂O`));
  }
}
