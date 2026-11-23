// Writes the OpenSCAD model for given parameter overrides and prints the JS
// mesh volume and bounds. Used by tests/test_site_parity.py.
import fs from 'node:fs';
import { buildShroudMesh, meshVolume } from '../js/geometry.js';
import { defaultParameters } from '../js/params.js';
import { generateScad } from '../js/scad.js';

let input = '';
process.stdin.setEncoding('utf8');
for await (const chunk of process.stdin) input += chunk;
const { overrides, scad_path: scadPath } = JSON.parse(input);
const params = { ...defaultParameters(), ...overrides };
fs.writeFileSync(scadPath, generateScad(params));
const mesh = buildShroudMesh(params);
process.stdout.write(JSON.stringify({ volume_mm3: meshVolume(mesh.positions), bounds: mesh.bounds }));
