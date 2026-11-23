// MI50 shroud editor: wires parameters, geometry, simulation, and exports.
import { buildShroudMesh, meshVolume, toBinarySTL } from './geometry.js';
import {
  GROUPS, PARAMETERS, defaultParameters, normalizeParameters, validateParameters,
} from './params.js';
import { generateScad } from './scad.js';
import { FANS } from './fan_data.js';
import {
  CFM_TO_M3_S, acousticBudget, affinityScale, fanCurve, interpolateElectrical, sampleCurves,
  solveOperatingPoint, systemCurve,
} from './solver.js';
import { drawPQChart } from './chart.js';

const STORAGE_KEY = 'mi50-shroud-editor-v1';
const $ = (id) => document.getElementById(id);

const DEFAULT_SIM = {
  fan_id: FANS[0].id, rpm_mode: 'rated', rpm: FANS[0].rpm, system_mode: 'quadratic',
  ref_pressure_mmh2o: 2, ref_flow_cfm: 50, table_text: '', duct_k: 0,
  heat_load_w: 300, density_kg_m3: 1.204, cp_j_kg_k: 1006,
};

const state = { params: defaultParameters(), sim: { ...DEFAULT_SIM }, mesh: null, validation: null, simResult: null };
let viewer = null;

// ------------------------------------------------------------ persistence

function encodeState() {
  const json = JSON.stringify({ params: state.params, sim: state.sim });
  return btoa(unescape(encodeURIComponent(json))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function decodeState(text) {
  const b64 = text.replace(/-/g, '+').replace(/_/g, '/');
  return JSON.parse(decodeURIComponent(escape(atob(b64))));
}

function applyLoaded(data) {
  if (!data || typeof data !== 'object') return;
  state.params = normalizeParameters(data.params || data);
  const sim = { ...DEFAULT_SIM };
  for (const [k, v] of Object.entries(data.sim || {})) {
    if (!(k in DEFAULT_SIM)) continue;
    sim[k] = typeof DEFAULT_SIM[k] === 'number' ? (Number.isFinite(Number(v)) ? Number(v) : DEFAULT_SIM[k]) : String(v);
  }
  if (!FANS.some((f) => f.id === sim.fan_id)) sim.fan_id = DEFAULT_SIM.fan_id;
  state.sim = sim;
}

function save() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ params: state.params, sim: state.sim })); } catch { /* storage unavailable */ }
}

function loadInitial() {
  try {
    if (location.hash.length > 1) { applyLoaded(decodeState(location.hash.slice(1))); return; }
  } catch { /* ignore malformed link */ }
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) applyLoaded(JSON.parse(stored));
  } catch { /* storage unavailable */ }
}

function download(name, data, type) {
  const blob = data instanceof Blob ? data : new Blob([data], { type });
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement('a'), { href: url, download: name });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// --------------------------------------------------------------- controls

function buildControls() {
  const form = $('controls');
  form.replaceChildren();
  for (const group of GROUPS) {
    const fs = document.createElement('fieldset');
    fs.append(Object.assign(document.createElement('legend'), { textContent: group.label }));
    for (const spec of PARAMETERS.filter((s) => s.group === group.id)) {
      const label = document.createElement('label');
      const title = document.createElement('span');
      title.textContent = spec.label;
      if (spec.provenance) {
        const badge = document.createElement('span');
        badge.className = `badge badge-${spec.provenance}`;
        badge.textContent = spec.provenance === 'unmeasured' ? 'UNMEASURED' : 'ESTIMATE';
        title.append(badge);
      }
      label.append(title);
      let input;
      if (spec.type === 'select') {
        input = document.createElement('select');
        for (const opt of spec.options) input.append(new Option(spec.unit ? `${opt} ${spec.unit}` : opt, opt));
      } else {
        input = Object.assign(document.createElement('input'), { type: 'number', min: spec.min, max: spec.max, step: spec.step, inputMode: 'decimal' });
      }
      input.id = `p-${spec.id}`;
      input.name = spec.id;
      input.value = state.params[spec.id];
      if (spec.unit && spec.type !== 'select') {
        const wrap = Object.assign(document.createElement('span'), { className: 'input-unit' });
        wrap.append(input, Object.assign(document.createElement('span'), { textContent: spec.unit }));
        label.append(wrap);
      } else {
        label.append(input);
      }
      if (spec.help) label.append(Object.assign(document.createElement('span'), { className: 'field-note', textContent: spec.help }));
      fs.append(label);
    }
    form.append(fs);
  }
  form.addEventListener('input', onParamInput);
  form.addEventListener('submit', (e) => e.preventDefault());
}

function syncControls() {
  for (const spec of PARAMETERS) $(`p-${spec.id}`).value = state.params[spec.id];
  $('sim-fan').value = state.sim.fan_id;
  $('sim-rpm-mode').value = state.sim.rpm_mode;
  $('sim-rpm').value = state.sim.rpm;
  $('sim-system-mode').value = state.sim.system_mode;
  $('sim-ref-p').value = state.sim.ref_pressure_mmh2o;
  $('sim-ref-q').value = state.sim.ref_flow_cfm;
  $('sim-table-text').value = state.sim.table_text;
  $('sim-duct-k').value = state.sim.duct_k;
  $('sim-heat').value = state.sim.heat_load_w;
  $('sim-rho').value = state.sim.density_kg_m3;
  $('sim-cp').value = state.sim.cp_j_kg_k;
}

let rebuildTimer = 0;
function onParamInput(event) {
  const spec = PARAMETERS.find((s) => s.id === event.target.name);
  if (!spec) return;
  const raw = event.target.value;
  if (spec.type === 'select') {
    state.params[spec.id] = spec.options.find((o) => String(o) === raw);
  } else {
    const n = Number(raw);
    state.params[spec.id] = raw === '' ? NaN : (spec.type === 'int' ? Math.round(n) : n);
  }
  clearTimeout(rebuildTimer);
  rebuildTimer = setTimeout(update, 60);
}

// --------------------------------------------------------------- geometry

const fmt = (v, digits = 1) => (Number.isFinite(v) ? v.toFixed(digits) : '—');

function renderMetrics(target, rows) {
  target.replaceChildren(...rows.map(([k, v]) => {
    const div = document.createElement('div');
    div.append(Object.assign(document.createElement('dt'), { textContent: k }), Object.assign(document.createElement('dd'), { textContent: v }));
    return div;
  }));
}

function updateGeometry() {
  const validation = validateParameters(state.params);
  state.validation = validation;
  const list = $('validation');
  const items = [
    ...validation.errors.map((m) => ['error', m]),
    ...validation.warnings.map((m) => ['warning', m]),
  ];
  if (!items.length) items.push(['ok', 'Geometry is valid and within the dual-slot, full-height envelope.']);
  list.replaceChildren(...items.map(([cls, m]) => Object.assign(document.createElement('li'), { className: cls, textContent: m })));
  for (const spec of PARAMETERS) {
    const v = state.params[spec.id];
    const bad = spec.type !== 'select' && (!Number.isFinite(v) || v < spec.min || v > spec.max);
    $(`p-${spec.id}`).setAttribute('aria-invalid', bad ? 'true' : 'false');
  }

  const message = $('preview-message');
  if (validation.errors.length) {
    state.mesh = null;
    message.hidden = false;
    message.textContent = 'Fix the highlighted parameter errors to rebuild the geometry.';
    $('export-stl').disabled = true;
    $('export-scad').disabled = true;
    renderMetrics($('geometry-metrics'), []);
    return;
  }
  try {
    state.mesh = buildShroudMesh(state.params);
  } catch (err) {
    state.mesh = null;
    message.hidden = false;
    message.textContent = `Geometry could not be built: ${err.message}`;
    $('export-stl').disabled = true;
    return;
  }
  $('export-stl').disabled = false;
  $('export-scad').disabled = false;
  const m = validation.metrics;
  const volumeCm3 = meshVolume(state.mesh.positions) / 1000;
  renderMetrics($('geometry-metrics'), [
    ['Outer size (L × H × T)', `${fmt(m.outer_extent_mm.length)} × ${fmt(m.outer_extent_mm.height)} × ${fmt(m.outer_extent_mm.thickness)} mm`],
    ['Sleeve inner opening', `${fmt(m.outlet_inner_mm[0])} × ${fmt(m.outlet_inner_mm[1])} mm`],
    ['Outlet / fan-end area', `${fmt(m.area_ratio_outlet_to_fan, 2)}`],
    ['Steepest wall angle', `${fmt(m.max_wall_angle_deg)}°`],
    ['Card + shroud length', `${fmt(m.total_length_with_card_mm)} mm`],
    ['Solid volume', `${fmt(volumeCm3)} cm³`],
  ]);
  $('export-summary').textContent = `${state.mesh.triangleCount.toLocaleString()} triangles, closed and consistently wound. OpenSCAD model renders to the same solid.`;
  if (viewer) {
    message.hidden = true;
    viewer.update(state.mesh, state.mesh.dimensions, state.params);
  }
}

// -------------------------------------------------------------- simulation

function parseTable(text) {
  const rows = text.split(/\r?\n/).map((l) => l.trim()).filter((l) => l && !l.startsWith('#') && !/^[a-z_]/i.test(l));
  return rows.map((line, i) => {
    const parts = line.split(/[,;\s\t]+/).filter(Boolean).map(Number);
    if (parts.length !== 2 || !parts.every(Number.isFinite)) throw new Error(`table line ${i + 1}: expected two numbers`);
    return parts;
  });
}

function currentFan() { return FANS.find((f) => f.id === state.sim.fan_id) || FANS[0]; }

function buildSimInputs() {
  const s = state.sim;
  const fanData = currentFan();
  const ratio = s.rpm_mode === 'affinity' ? s.rpm / fanData.rpm : 1;
  const points = ratio === 1 ? fanData.points : affinityScale(fanData.points, ratio);
  const fan = fanCurve(points, fanData.label);
  const system = s.system_mode === 'table'
    ? { type: 'table', curve: systemCurve(parseTable(s.table_text), 'entered system table') }
    : { type: 'quadratic', pressureMmH2O: s.ref_pressure_mmh2o, flowCfm: s.ref_flow_cfm };
  const m = state.validation?.metrics;
  const areaM2 = m ? (m.outlet_inner_mm[0] * m.outlet_inner_mm[1]) / 1e6 : NaN;
  const ductLoss = s.duct_k > 0 ? { k: s.duct_k, areaM2 } : null;
  return { fanData, ratio, fan, system, ductLoss, areaM2 };
}

function updateSimulation() {
  const s = state.sim;
  const fanData = currentFan();
  $('sim-rpm-row').hidden = s.rpm_mode !== 'affinity';
  $('sim-quadratic').hidden = s.system_mode !== 'quadratic';
  $('sim-table').hidden = s.system_mode !== 'table';
  const note = $('sim-fan-note');
  const mismatch = fanData.frame_mm !== state.params.fan_size_mm;
  note.textContent = `${fanData.frame_mm} mm frame, rated ${fanData.rpm} RPM. ${fanData.provenance}`;
  if (mismatch) {
    const btn = Object.assign(document.createElement('button'), { type: 'button', className: 'btn btn-quiet', textContent: `Use ${fanData.frame_mm} mm shroud` });
    btn.addEventListener('click', () => { state.params.fan_size_mm = fanData.frame_mm; syncControls(); update(); });
    note.append(document.createElement('br'), `Shroud is set to ${state.params.fan_size_mm} mm fans. `, btn);
  }

  const status = $('sim-status');
  const metrics = $('sim-metrics');
  let inputs;
  try {
    inputs = buildSimInputs();
    if (!state.validation || state.validation.errors.length) throw new Error('Fix the geometry errors first; the shroud outlet area is needed.');
    const fanCount = state.params.fan_count;
    const common = { fan: inputs.fan, system: inputs.system, heatLoadW: s.heat_load_w, densityKgM3: s.density_kg_m3, cpJkgK: s.cp_j_kg_k, ductLoss: inputs.ductLoss };
    const r = solveOperatingPoint({ ...common, fanCount });
    state.simResult = { ...r, rpm: fanData.rpm * inputs.ratio, rpm_mode: s.rpm_mode, fan_id: fanData.id };
    const velocity = (r.total_flow_cfm * CFM_TO_M3_S) / inputs.areaM2;
    const elec = fanData.electrical ? interpolateElectrical(fanData.electrical.points, fanData.rpm * inputs.ratio) : null;
    const rows = [
      ['Total airflow', `${fmt(r.total_flow_cfm)} CFM (${fmt(r.total_flow_cfm * CFM_TO_M3_S * 3600, 0)} m³/h)`],
      ['Per fan', `${fmt(r.per_fan_flow_cfm)} CFM`],
      ['Static pressure', `${fmt(r.fan_static_pressure_mmh2o, 2)} mmH₂O`],
      ['of which shroud loss', `${fmt(r.duct_loss_mmh2o, 3)} mmH₂O`],
      ['Bulk-air ΔT', `${fmt(r.ideal_bulk_air_temperature_rise_c)} °C`],
      ['Mean sleeve velocity', `${fmt(velocity, 2)} m/s`],
    ];
    if (elec) rows.push(['Fan electrical (12 V)', `${fmt(elec.power_w * fanCount, 2)} W, ${fmt(elec.current_a * fanCount, 2)} A total`]);
    else if (fanData.electrical) rows.push(['Fan electrical', 'outside measured RPM range']);
    renderMetrics(metrics, rows);
    const flags = [];
    if (mismatch) flags.push(`fan curve frame (${fanData.frame_mm} mm) differs from the shroud (${state.params.fan_size_mm} mm)`);
    if (s.rpm_mode === 'affinity' && inputs.ratio !== 1) flags.push('fan curve is affinity-law scaled, not measured at this speed');
    if (s.system_mode === 'quadratic') flags.push('system resistance is a one-point quadratic, hypothetical unless measured');
    status.className = `sim-status ${flags.length ? 'warning' : 'ok'}`;
    status.textContent = flags.length ? `Solved, with caveats: ${flags.join('; ')}.` : 'Solved with tabulated system data.';
    const curves = sampleCurves({ ...common, fanCount });
    drawPQChart($('pq-chart'), { ...curves, point: [r.total_flow_cfm, r.fan_static_pressure_mmh2o] });

    const body = $('sweep-body');
    body.replaceChildren(...[1, 2, 3, 4].map((n) => {
      const tr = document.createElement('tr');
      if (n === fanCount) tr.className = 'current';
      let cells;
      try {
        const x = solveOperatingPoint({ ...common, fanCount: n });
        cells = [n, `${fmt(x.total_flow_cfm)} CFM`, `${fmt(x.fan_static_pressure_mmh2o, 2)} mmH₂O`, `${fmt(x.ideal_bulk_air_temperature_rise_c)} °C`];
      } catch (e) {
        cells = [n, '—', '—', e.message.split(';')[0]];
      }
      tr.append(...cells.map((c) => Object.assign(document.createElement('td'), { textContent: c })));
      return tr;
    }));
  } catch (err) {
    state.simResult = null;
    status.className = 'sim-status error';
    status.textContent = err.message;
    renderMetrics(metrics, []);
    $('sweep-body').replaceChildren();
    if (inputs) {
      try { drawPQChart($('pq-chart'), sampleCurves({ fan: inputs.fan, fanCount: state.params.fan_count, system: inputs.system, densityKgM3: s.density_kg_m3, ductLoss: inputs.ductLoss })); } catch { /* nothing drawable */ }
    }
  }
}

function bindSimControls() {
  const select = $('sim-fan');
  for (const f of FANS) select.append(new Option(f.label, f.id));
  const map = {
    'sim-fan': ['fan_id', String], 'sim-rpm-mode': ['rpm_mode', String], 'sim-rpm': ['rpm', Number],
    'sim-system-mode': ['system_mode', String], 'sim-ref-p': ['ref_pressure_mmh2o', Number], 'sim-ref-q': ['ref_flow_cfm', Number],
    'sim-table-text': ['table_text', String], 'sim-duct-k': ['duct_k', Number], 'sim-heat': ['heat_load_w', Number],
    'sim-rho': ['density_kg_m3', Number], 'sim-cp': ['cp_j_kg_k', Number],
  };
  $('sim-controls').addEventListener('input', (e) => {
    const entry = map[e.target.id];
    if (!entry) return;
    state.sim[entry[0]] = entry[1](e.target.value);
    if (e.target.id === 'sim-fan') { state.sim.rpm = currentFan().rpm; $('sim-rpm').value = state.sim.rpm; }
    updateSimulation();
    save();
  });
  $('sim-controls').addEventListener('submit', (e) => e.preventDefault());
}

// -------------------------------------------------------------- acoustics

function updateAcoustics() {
  const num = (id) => { const v = $(id).value; return v === '' ? null : Number(v); };
  const r = acousticBudget({
    fanCount: num('noise-fan-count') ?? 1, fanSplDb: num('noise-fan-spl'), refDistanceM: num('noise-ref-distance'),
    listenerDistanceM: num('noise-listener-distance'), targetDb: num('noise-target') ?? 0,
    ambientDb: num('noise-ambient') ?? 0, systemDb: num('noise-system'),
  });
  const status = $('noise-status');
  if (!r) {
    for (const id of ['noise-fans', 'noise-margin', 'noise-max', 'noise-distance']) $(id).textContent = '—';
    $('noise-total').textContent = 'Enter fan SPL';
    status.className = 'noise-status';
    status.textContent = "Enter the fan's published or measured SPL.";
    return;
  }
  $('noise-total').textContent = `${fmt(r.total_db)} dBA`;
  $('noise-fans').textContent = `${fmt(r.fans_only_db)} dBA`;
  $('noise-margin').textContent = `${r.margin_db >= 0 ? '+' : ''}${fmt(r.margin_db)} dB`;
  $('noise-max').textContent = r.max_one_fan_spl_at_ref_db === null ? 'none' : `${fmt(r.max_one_fan_spl_at_ref_db)} dBA`;
  $('noise-distance').textContent = `${r.distance_correction_db >= 0 ? '+' : ''}${fmt(r.distance_correction_db)} dB`;
  status.className = `noise-status ${r.within_target ? 'ok' : 'error'}`;
  status.textContent = r.max_one_fan_spl_at_ref_db === null
    ? 'Background noise alone already reaches the target.'
    : r.within_target ? 'Within the target.' : 'Over the target: use quieter or slower fans, fewer fans, or more distance.';
}

// ---------------------------------------------------------------- exports

function bindActions() {
  $('export-stl').addEventListener('click', () => {
    if (!state.mesh) return;
    download('mi50_shroud.stl', new Blob([toBinarySTL(state.mesh.positions, 'MI50 shroud (mm)')], { type: 'model/stl' }));
  });
  $('export-scad').addEventListener('click', () => download('mi50_shroud.scad', generateScad(state.params), 'text/plain'));
  $('save-preset').addEventListener('click', () => {
    const report = {
      format: 'mi50-shroud-preset', version: 1, params: state.params, sim: state.sim,
      geometry_metrics: state.validation?.metrics ?? null,
      simulation_result: state.simResult,
      fan_curve_source: { path: currentFan().source, sha256: currentFan().sha256 },
    };
    download('mi50_shroud_preset.json', JSON.stringify(report, null, 2), 'application/json');
  });
  $('load-preset').addEventListener('change', async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      applyLoaded(JSON.parse(await file.text()));
      syncControls();
      update();
    } catch (err) {
      alert(`Could not load preset: ${err.message}`);
    }
    e.target.value = '';
  });
  $('copy-link').addEventListener('click', async () => {
    const url = `${location.origin}${location.pathname}#${encodeState()}`;
    history.replaceState(null, '', url);
    try { await navigator.clipboard.writeText(url); $('copy-link').textContent = 'Link copied'; } catch { $('copy-link').textContent = 'Link in address bar'; }
    setTimeout(() => { $('copy-link').textContent = 'Copy link'; }, 2000);
  });
  $('reset').addEventListener('click', () => {
    state.params = defaultParameters();
    state.sim = { ...DEFAULT_SIM };
    history.replaceState(null, '', location.pathname);
    syncControls();
    update();
  });
  $('show-context').addEventListener('change', (e) => viewer?.setContextVisible(e.target.checked));
  $('noise-form').addEventListener('input', updateAcoustics);
  $('noise-form').addEventListener('submit', (e) => e.preventDefault());
}

function update() {
  updateGeometry();
  updateSimulation();
  save();
}

async function init() {
  loadInitial();
  buildControls();
  bindSimControls();
  syncControls();
  bindActions();
  try {
    const { ShroudViewer } = await import('./viewer.js');
    viewer = new ShroudViewer($('preview'));
  } catch (err) {
    const message = $('preview-message');
    message.hidden = false;
    message.textContent = `3D preview unavailable (${err.message}). Exports and simulation still work.`;
  }
  update();
  updateAcoustics();
}

init();
