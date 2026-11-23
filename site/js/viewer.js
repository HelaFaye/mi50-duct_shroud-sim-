// three.js preview of the shroud mesh with optional fan and cooler context.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { ENVELOPE } from './params.js';

const FAN_DEPTH_MM = 25;

function cssColor(name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return new THREE.Color(value || fallback);
}

export class ShroudViewer {
  constructor(canvas) {
    this.canvas = canvas;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.scene = new THREE.Scene();
    // z-up world: map model (x flow, y height, z thickness) so height is vertical
    this.root = new THREE.Group();
    this.root.rotation.x = 0; // model y is up already in three's default y-up frame
    this.scene.add(this.root);
    this.camera = new THREE.PerspectiveCamera(35, 1, 1, 5000);
    this.camera.position.set(-260, 160, 300);
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x445566, 1.6));
    const key = new THREE.DirectionalLight(0xffffff, 1.6);
    key.position.set(-200, 300, 250);
    this.scene.add(key);
    const fill = new THREE.DirectionalLight(0xffffff, 0.6);
    fill.position.set(300, -100, -200);
    this.scene.add(fill);

    this.shroudMaterial = new THREE.MeshStandardMaterial({ color: 0xb8c4cf, metalness: 0.05, roughness: 0.55, flatShading: true });
    this.edgeMaterial = new THREE.LineBasicMaterial({ color: 0x23303b, transparent: true, opacity: 0.55 });
    this.context = new THREE.Group();
    this.root.add(this.context);
    this.framed = false;

    new ResizeObserver(() => this.resize()).observe(canvas);
    this.resize();
    const loop = () => { this.controls.update(); this.renderer.render(this.scene, this.camera); requestAnimationFrame(loop); };
    requestAnimationFrame(loop);
  }

  resize() {
    const { clientWidth: w, clientHeight: h } = this.canvas;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  setContextVisible(visible) { this.context.visible = visible; }

  update(mesh, dims, params) {
    for (const obj of [this.shroud, this.edges]) {
      if (obj) { this.root.remove(obj); obj.geometry.dispose(); }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(mesh.positions, 3));
    geometry.computeVertexNormals();
    this.shroudMaterial.color = cssColor('--muted', '#9aa8b5').lerp(new THREE.Color(0xffffff), 0.35);
    this.shroud = new THREE.Mesh(geometry, this.shroudMaterial);
    this.edges = new THREE.LineSegments(new THREE.EdgesGeometry(geometry, 25), this.edgeMaterial);
    this.root.add(this.shroud, this.edges);
    this.buildContext(dims, params);
    if (!this.framed) { this.frame(mesh.bounds); this.framed = true; }
  }

  buildContext(d, p) {
    for (const child of [...this.context.children]) {
      this.context.remove(child);
      child.geometry?.dispose();
    }
    const fanColor = cssColor('--fan', '#0f6fb8');
    const fanMat = new THREE.MeshStandardMaterial({ color: fanColor, transparent: true, opacity: 0.28, depthWrite: false });
    for (let i = 0; i < p.fan_count; i++) {
      const u = -d.arrayU / 2 + d.S / 2 + i * d.S;
      const box = new THREE.Mesh(new THREE.BoxGeometry(FAN_DEPTH_MM, d.S, d.S), fanMat);
      const [y, z] = d.alongHeight ? [u, 0] : [0, u];
      box.position.set(-FAN_DEPTH_MM / 2 - 0.5, y, z);
      this.context.add(box);
      const hub = new THREE.Mesh(new THREE.CylinderGeometry(d.S * 0.18, d.S * 0.18, FAN_DEPTH_MM + 1, 24), fanMat);
      hub.rotation.z = Math.PI / 2;
      hub.position.copy(box.position);
      this.context.add(hub);
    }
    const coolerMat = new THREE.MeshStandardMaterial({ color: 0x8a96a3, transparent: true, opacity: 0.22, depthWrite: false });
    const xCard = d.plate + d.ductLength;
    const cooler = new THREE.Mesh(new THREE.BoxGeometry(ENVELOPE.board_length_mm, p.cooler_height_mm, p.cooler_thickness_mm), coolerMat);
    cooler.position.set(xCard + ENVELOPE.board_length_mm / 2, d.outletOffsetY, d.outletOffsetZ);
    this.context.add(cooler);
    const outline = new THREE.LineSegments(new THREE.EdgesGeometry(cooler.geometry), new THREE.LineBasicMaterial({ color: 0x8a96a3 }));
    outline.position.copy(cooler.position);
    this.context.add(outline);
    const arrow = new THREE.ArrowHelper(new THREE.Vector3(1, 0, 0), new THREE.Vector3(-FAN_DEPTH_MM - 50, 0, 0), 40, fanColor.getHex(), 10, 6);
    this.context.add(arrow);
  }

  frame(bounds) {
    const c = new THREE.Vector3(
      (bounds.min[0] + bounds.max[0]) / 2 + 60, (bounds.min[1] + bounds.max[1]) / 2, (bounds.min[2] + bounds.max[2]) / 2,
    );
    this.controls.target.copy(c);
    this.camera.position.set(c.x - 230, c.y + 170, c.z + 320);
    this.controls.update();
  }
}
