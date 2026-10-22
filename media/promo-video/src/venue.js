// 앱의 실제 3D 공연장(src/scene.js)을 영상용으로 구동한다.
// VenueViewer의 자동 렌더링을 끄고, 프레임마다 카메라와 뷰포트를 직접 지정해 결정적으로 그린다.
import * as THREE from 'three';
import { VenueViewer } from '../../../src/scene.js';
import { DEFAULT_MODEL, eyePosition, getObstacles, analyzeSightline } from '../../../src/model.js';

const near = (a, b) => Math.abs(a - b) < 1e-4;

export class Venue {
  constructor(width, height) {
    this.W = width; this.H = height;
    const host = document.createElement('div');
    host.style.cssText = `position:absolute;left:-${width + 100}px;top:0;width:${width}px;height:${height}px;overflow:hidden;`;
    document.body.append(host);
    this.viewer = new VenueViewer(host, () => {});
    this.viewer.schedule = () => {}; // requestAnimationFrame 렌더링 차단 — 캡처 사이에 화면이 바뀌지 않게
    this.renderer = this.viewer.renderer;
    this.renderer.setPixelRatio(1);
    this.renderer.setSize(width, height, false);
    this.canvas = this.renderer.domElement;
    this.cam = new THREE.PerspectiveCamera(60, width / height, 0.05, 90);
    this.baseModel = structuredClone(DEFAULT_MODEL);
    this.key = '';
    this.colorKey = '';
    this.railTint = 0;
  }

  // 모델·무대 배치가 바뀔 때만 다시 만든다.
  ensure(layout = 'theatre', overrides = {}) {
    const model = { ...this.baseModel, ...overrides };
    const key = JSON.stringify([layout, overrides]);
    if (key === this.key) return;
    this.key = key; this.colorKey = '';
    this.model = model; this.layout = layout;
    this.viewer.rebuild(model, layout);
    this.seats = this.viewer.seats;
    // 난간·촬영 타워 메시를 찾아 애니메이션에 쓴다(가림 계산과 같은 위치·크기).
    const obstacles = getObstacles(model, layout);
    const rail = obstacles.find(o => o.id === 'rail');
    const tower = obstacles.find(o => o.id === 'tower');
    this.rail = null; this.tower = [];
    this.viewer.root.traverse(obj => {
      if (!obj.isMesh || obj.isInstancedMesh) return;
      const p = obj.position;
      if (near(p.x, rail.position[0]) && near(p.y, rail.position[1]) && near(p.z, rail.position[2])) this.rail = obj;
      if (tower && near(p.x, tower.position[0]) && near(p.z, tower.position[2]) && (near(p.y, tower.position[1]) || near(p.y, 3.2))) this.tower.push(obj);
    });
    if (this.rail) {
      this.railBase = { y: this.rail.position.y, h: rail.size[1] };
      this.rail.material = this.rail.material.clone();
      this.railColor = this.rail.material.color.clone();
    }
    this.towerBase = this.tower.map(m => m.position.y);
  }

  highlight(selected = 12, comparison = null) {
    const key = `${selected}:${comparison}:${this.key}`;
    if (key === this.colorKey) return;
    this.colorKey = key;
    this.viewer.view.overlay = false;
    this.viewer.setView({ selected, comparison, mode: 'seat', overlay: false });
  }

  // 난간 높이(m)를 시각적으로 바꾼다. 가림 계산은 analyze()에 같은 값을 넘긴다.
  setRailHeight(h) {
    if (!this.rail) return;
    this.rail.scale.y = h / this.railBase.h;
    this.rail.position.y = this.model.balconyHeight + h / 2;
  }
  // 난간 강조(0~1): 주황 발광
  setRailTint(v) {
    if (!this.rail) return;
    const m = this.rail.material;
    m.color.copy(this.railColor).lerp(new THREE.Color('#c98a5f'), v * 0.42);
    m.emissive = new THREE.Color('#ff9a5c');
    m.emissiveIntensity = v * 0.08;
  }
  // 촬영 타워 상승(0: 바닥 아래, 1: 제자리)
  setTowerRise(p) {
    this.tower.forEach((m, i) => { m.position.y = this.towerBase[i] - (1 - p) * 3.6; });
  }

  analyze(seatId, overrides = {}, layout = this.layout, eyeHeight = 1.2) {
    const model = { ...this.model, ...overrides };
    return analyzeSightline(model, this.seats[seatId], layout, eyeHeight);
  }

  // 좌석 눈높이 시점. 앱의 positionCamera와 같은 규칙(무대 중앙 1.88m를 바라봄) + yaw/pitch.
  seatPose(seatId, { eyeHeight = 1.2, yaw = 0, pitch = 0, fov = 60 } = {}) {
    const pos = eyePosition(this.seats[seatId], eyeHeight);
    const dir = new THREE.Vector3(this.model.stageOffset, 1.88, -0.25).sub(pos).normalize();
    dir.applyAxisAngle(new THREE.Vector3(0, 1, 0), yaw);
    dir.y += pitch;
    return { pos, look: pos.clone().add(dir), fov };
  }

  applyCam(cam, pose, aspect, shiftX = 0) {
    cam.position.copy(pose.pos);
    cam.fov = pose.fov ?? 60;
    cam.aspect = aspect;
    cam.lookAt(pose.look);
    if (shiftX) cam.setViewOffset(1000, 1000 / aspect, shiftX * 1000, 0, 1000, 1000 / aspect);
    else cam.clearViewOffset();
    cam.updateProjectionMatrix();
    cam.updateMatrixWorld();
  }

  // WebGL 캔버스를 장면의 슬롯에 직접 붙인다. (2D 캔버스로 복사하면 SwiftShader 읽기 때문에 프레임당 ~400ms가 든다)
  mount(slot, clip = null) {
    if (this.canvas.parentElement !== slot) slot.append(this.canvas);
    this.canvas.style.clipPath = clip || '';
  }

  // views: [{ rect:[x,y,w,h](좌상단 기준 px), pose, shiftX }]
  render(views) {
    const r = this.renderer;
    r.setScissorTest(true);
    r.setClearColor('#151922', 1);
    r.setViewport(0, 0, this.W, this.H); r.setScissor(0, 0, this.W, this.H); r.clear();
    this.viewer.overlay.visible = false;
    for (const v of views) {
      const [x, y, w, h] = v.rect.map(Math.round);
      if (w < 2 || h < 2) continue;
      const gy = this.H - y - h;
      r.setViewport(x, gy, w, h); r.setScissor(x, gy, w, h);
      v.before?.();
      this.applyCam(this.cam, v.pose, w / h, v.shiftX || 0);
      r.render(this.viewer.scene, this.cam);
      v.camera = this.cam.clone();
    }
    r.setScissorTest(false);
  }

  // 3D 좌표 → 뷰 rect 안의 화면 좌표(px)
  project(point, view) {
    const v = new THREE.Vector3(...(Array.isArray(point) ? point : [point.x, point.y, point.z])).project(view.camera);
    const [x, y, w, h] = view.rect;
    return { x: x + (v.x + 1) / 2 * w, y: y + (1 - v.y) / 2 * h, behind: v.z > 1 };
  }
}
