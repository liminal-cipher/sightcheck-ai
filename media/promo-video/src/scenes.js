// 장면별 애니메이션. 각 장면은 update(t)에서 시간 t(초)만 보고 상태를 계산한다.
//
// 이징 규칙 (LOOK.md)
//   등장 appear(): cubic-bezier(0, 0, 0, 1), 0.5초 안팎. 화면 밖·투명 상태에서 들어올 때만.
//   이동 move():   cubic-bezier(0.65, 0, 0.35, 1). 이미 보이는 요소의 위치·크기·값, 카메라.
//   퇴장 vanish(): cubic-bezier(0.55, 0, 0.9, 0.45). 끝나는 순간 화면 밖이거나 완전히 투명.
import { lerp, ease, range, appear, vanish, move, bump, style, lines, splitWords, HIDE } from './engine.js';
import * as THREE from 'three';
import { getTargets } from '../../../src/model.js';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const UI_RECTS = await fetch(new URL('../assets/ui/rects.json', import.meta.url)).then(r => r.json());

const clear = ctx => ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
// clip-path: path() 용 둥근 사각형
const rr = ([x, y, w, h], r) => {
  r = Math.min(r, w / 2, h / 2);
  return `M${x + r} ${y}H${x + w - r}A${r} ${r} 0 0 1 ${x + w} ${y + r}V${y + h - r}A${r} ${r} 0 0 1 ${x + w - r} ${y + h}H${x + r}A${r} ${r} 0 0 1 ${x} ${y + h - r}V${y + r}A${r} ${r} 0 0 1 ${x + r} ${y}Z`;
};
const lerp3 = (a, b, t) => new THREE.Vector3(lerp(a.x, b.x, t), lerp(a.y, b.y, t), lerp(a.z, b.z, t));
const bezier3 = (p0, p1, p2, p3, t) => {
  const u = 1 - t;
  return new THREE.Vector3(
    u * u * u * p0.x + 3 * u * u * t * p1.x + 3 * u * t * t * p2.x + t * t * t * p3.x,
    u * u * u * p0.y + 3 * u * u * t * p1.y + 3 * u * t * t * p2.y + t * t * t * p3.y,
    u * u * u * p0.z + 3 * u * u * t * p1.z + 3 * u * t * t * p2.z + t * t * t * p3.z);
};
const V = (x, y, z) => new THREE.Vector3(x, y, z);

// 투명·아래에서 떠오르는 등장
const rise = (el, lt, t0, dy = 20) => { const p = appear(lt, t0); style(el, { y: (1 - p) * dy, opacity: p }); return p; };
// 한 덩어리 마스크 문장(.m > .w): 아래에서 올라오고, t1이 있으면 위로 빠져나간다
const maskLine = (w, lt, t0, t1 = Infinity) => {
  const y = (1 - appear(lt, t0)) * HIDE - (t1 === Infinity ? 0 : vanish(lt, t1)) * HIDE;
  w.style.transform = `translate3d(0, ${y}%, 0)`;
};
// 장면이 끝나기 전에 퇴장이 완전히 끝나도록 퇴장 시작 시각을 계산
const exitBy = (root, tEnd, dOut = 0.4, stagger = 0.06) => tEnd - dOut - stagger * 0.4 * (root.querySelectorAll('.w').length - 1) - 0.02;

// 3D 좌표에 붙는 태그: 점 → 줄기 → 라벨 순으로 등장
function placePin(pin, pt, lt, t0) {
  if (lt < t0) { pin.style.visibility = 'hidden'; return; }
  pin.style.visibility = 'visible';
  pin.style.transform = `translate3d(${pt.x}px, ${pt.y}px, 0)`;
  const tag = $('.tag', pin), stem = $('.stem', pin), dot = $('.dot', pin);
  dot.style.transform = `scale(${appear(lt, t0, 0.4)})`;
  stem.style.transformOrigin = '50% 100%';
  stem.style.transform = `scaleY(${appear(lt, t0 + 0.08, 0.4)})`;
  const q = appear(lt, t0 + 0.14);
  tag.style.opacity = String(q);
  tag.style.transform = `translate(-50%, ${-26 + (1 - q) * 14}px)`;
}

const setNum = (el, v) => { el.textContent = String(Math.round(v)); };

// 로고 락업 (브랜드·엔드카드 공용)
function makeLockup(lock) {
  const tile = $('.tile', lock), eye = $('.eye', lock), pupil = $('.pupil', lock), svg = $('.logo-tile', lock);
  const wordEl = $('.wordmark .w', lock), dot = $('.wordmark .dot', lock);
  const text = wordEl.textContent;
  wordEl.parentElement.outerHTML = [...text].map(ch => `<span class="m"><span class="w">${ch}</span></span>`).join('');
  const chars = $$('.wordmark .w', lock);
  const len = eye.getTotalLength();
  eye.style.strokeDasharray = `${len}`;
  for (const el of [tile, pupil]) { el.style.transformBox = 'fill-box'; el.style.transformOrigin = '50% 50%'; }
  const width = lock.getBoundingClientRect().width;
  return { lock, svg, tile, eye, pupil, chars, dot, len, width };
}
function animateLockup(L, lt, { tileAt = 0, wordAt = 1.0, shift = true, top = 382 } = {}) {
  const left = (1920 - L.width) / 2;
  const pTile = appear(lt, tileAt);                                   // 등장: 투명(크기 0)에서
  L.tile.style.transform = `scale(${pTile}) rotate(${(1 - pTile) * -12}deg)`;
  L.eye.style.strokeDashoffset = String(L.len * (1 - move(lt, tileAt + 0.2, tileAt + 0.95))); // 이동: 선 그리기
  L.pupil.style.transform = `scale(${appear(lt, tileAt + 0.8)})`;
  const pShift = shift ? move(lt, wordAt - 0.15, wordAt + 0.55) : 1;  // 이동: 아이콘이 왼쪽으로 비켜남
  const dx = (L.width - 176) / 2 * (1 - pShift);
  L.lock.style.transform = `translate3d(${left + dx}px, ${top}px, 0)`;
  L.chars.forEach((c, i) => {
    c.style.transform = `translate3d(0, ${(1 - appear(lt, wordAt + i * 0.05)) * HIDE}%, 0)`;
  });
  L.dot.style.transformOrigin = '50% 80%';
  L.dot.style.transform = `scale(${appear(lt, wordAt + 0.3)})`;
}

/* ───────────── 1. 훅 ───────────── */
export function hook(venue, [T0, T1]) {
  const el = $('#s-hook');
  const heads = ['#hk1', '#hk2', '#hk3'].map(s => $(s));
  heads.forEach(splitWords);
  const tks = [$('#tk-a'), $('#tk-b')];
  const inners = tks.map(t => $('.tk-inner', t));
  const ctxs = tks.map(t => $('canvas', t).getContext('2d'));
  const verdicts = tks.map(t => $('.verdict', t));
  const OUT = 5.5;
  let drawn = false;
  return {
    el, t0: T0, t1: T1,
    update(t) {
      const lt = t - T0;
      lines(heads[0], lt, 0.12, 1.72);
      lines(heads[1], lt, 2.25, 3.7);
      lines(heads[2], lt, 4.18, exitBy(heads[2], T1 - T0));
      tks.forEach((tk, i) => {
        const pin = appear(lt, 0.3 + i * 0.1);
        const pout = vanish(lt, OUT + i * 0.06);
        const flip = move(lt, 2.3 + i * 0.16, 3.2 + i * 0.16);
        const lift = bump(lt, 2.3 + i * 0.16, 0.9) * 0.06;
        style(tk, { x: (i ? 1 : -1) * (1 - pin) * 70, y: (1 - pin) * 150 - pout * 90, rot: (i ? 2.5 : -2.5) * (1 - pin), scale: 1 + lift, opacity: pin * (1 - pout) });
        inners[i].style.transform = `rotateY(${flip * 180}deg)`;
        rise(verdicts[i], lt, 4.25 + i * 0.14, 24);
      });
      // 카드 뒷면은 정지 화면: 한 번만 그려 복사한다(WebGL→2D 복사가 비싸서).
      if (lt > 2.3 && !drawn) {
        drawn = true;
        venue.ensure('theatre');
        venue.highlight(-1, null);
        venue.render([
          { rect: [0, 0, 640, 392], pose: venue.seatPose(12) },
          { rect: [640, 0, 640, 392], pose: venue.seatPose(17) },
        ]);
        ctxs[0].drawImage(venue.canvas, 0, 0, 640, 392, 0, 0, 640, 392);
        ctxs[1].drawImage(venue.canvas, 640, 0, 640, 392, 0, 0, 640, 392);
      }
    },
  };
}

/* ───────────── 2. 브랜드 ───────────── */
export function brand(venue, [T0, T1]) {
  const el = $('#s-brand');
  el.style.visibility = 'visible';
  const L = makeLockup($('#br-lockup'));
  el.style.visibility = '';
  const tag = $('#br-tag'); splitWords(tag); tag.style.top = '618px';
  const OUT = 3.5;
  return {
    el, t0: T0, t1: T1,
    update(t) {
      const lt = t - T0;
      animateLockup(L, lt, { tileAt: 0.02, wordAt: 1.05, top: 380 });
      lines(tag, lt, 1.7, OUT - 0.05);
      const out = vanish(lt, OUT, 0.42);
      L.lock.style.opacity = String(1 - out);
      L.lock.style.transform += ` translateY(${-out * 40}px)`;
    },
  };
}

/* ───────────── 3. 제품 공개 ───────────── */
export function ui(venue, [T0, T1]) {
  const el = $('#s-ui');
  const cap = $('#ui-cap'); splitWords(cap);
  const rig = $('#ui-rig'), browser = $('#ui-browser');
  const imgC = $('#ui-c3');
  const cursor = $('#ui-cursor'), ripple = $('#ui-ripple');
  const k = 1560 / 1440, bx = 180, by = 170 + 44;
  const R = UI_RECTS['ui-a3'];
  const toScreen = (x, y) => ({ x: bx + x * k, y: by + y * k });
  const seat = toScreen(R.seatC3.x + R.seatC3.w / 2, R.seatC3.y + R.seatC3.h / 2);
  const f = R.sceneFrame;
  const frame = { ...toScreen(f.x, f.y), w: f.w * k, h: f.h * k };
  const fc = { x: frame.x + frame.w / 2, y: frame.y + frame.h / 2 };
  const S = Math.max(1920 / frame.w, 1080 / frame.h);
  const CLICK = 2.16;
  return {
    el, t0: T0, t1: T1,
    update(t) {
      const lt = t - T0;
      lines(cap, lt, 0.3, 2.5);
      // 브라우저: 화면 아래 밖에서 투명하게 등장
      const pin = appear(lt, 0.0, 0.55);
      style(browser, { y: (1 - pin) * 620, rx: (1 - pin) * 22, scale: lerp(0.9, 1, pin), opacity: pin });
      // 커서: 화면 오른쪽 아래 밖에서 등장해 C3에 멈춘다
      const pc = appear(lt, 1.35, 0.6);
      const p0 = { x: 2060, y: 1240 }, p1 = { x: 1000, y: 1160 };
      const u = 1 - pc;
      const cx = u * u * p0.x + 2 * u * pc * p1.x + pc * pc * seat.x;
      const cy = u * u * p0.y + 2 * u * pc * p1.y + pc * pc * seat.y;
      const press = 1 - 0.14 * bump(lt, CLICK - 0.04, 0.24);
      const cOut = vanish(lt, 2.5, 0.3);
      style(cursor, { x: cx - 6, y: cy - 4, scale: press, opacity: lt < 1.35 ? 0 : 1 - cOut });
      // 클릭 파문: 퍼지며(등장) 완전히 사라진다(퇴장)
      ripple.style.left = `${seat.x}px`; ripple.style.top = `${seat.y}px`;
      style(ripple, { scale: 1 + appear(lt, CLICK, 0.6) * 4.5, opacity: lt < CLICK ? 0 : 0.9 * (1 - vanish(lt, CLICK + 0.05, 0.55)) });
      imgC.style.opacity = lt >= CLICK + 0.05 ? '1' : '0'; // 실제 앱처럼 클릭 즉시 C3 상태로 전환(겹쳐 보이는 크로스페이드 없음)
      // 3D 뷰로 줌인 (이동)
      const pz = move(lt, 2.75, 3.95);
      const s = Math.pow(S, pz);
      const c = { x: lerp(960, fc.x, pz), y: lerp(540, fc.y, pz) };
      rig.style.transform = `translate3d(${960 - c.x * s}px, ${540 - c.y * s}px, 0) scale(${s})`;
    },
  };
}

/* ───────────── 4. 좌석 시점 ───────────── */
export function pov(venue, [T0, T1]) {
  const el = $('#s-pov');
  const slot = $('.slot3d', el);
  const h1 = $('#pov1'), h2 = $('#pov2'); splitWords(h1); splitWords(h2);
  const eb = $('.eyebrow', el), pin = $('#pov-pin');
  return {
    el, t0: T0 - 0.4, t1: T1,
    update(t) {
      const lt = t - T0;
      el.style.opacity = String(appear(lt, -0.4, 0.4)); // 줌인 끝에 3D 화면이 투명에서 등장
      venue.ensure('theatre');
      venue.highlight(12, null);
      let pose;
      if (lt < 2.3) {
        const p = move(lt, 0, 2.3);
        pose = venue.seatPose(12, { yaw: -0.07 * p, pitch: -0.01 * p, fov: lerp(60, 57, p) });
      } else {
        const p = move(lt, 2.3, 5.9);
        const from = venue.seatPose(12, { yaw: -0.07, pitch: -0.01, fov: 57 });
        const pos = bezier3(from.pos, V(0.2, 5.6, 9.3), V(4.6, 9.4, 14.8), V(4.2, 8.6, 15.6), p);
        pose = { pos, look: lerp3(from.look, V(-0.3, 1.2, 3.2), p), fov: lerp(57, 44, p) };
      }
      const view = { rect: [0, 0, 1920, 1080], pose };
      venue.mount(slot);
      venue.render([view]);
      const s = venue.seats[12];
      placePin(pin, venue.project([s.x, s.floor + 1.0, s.z + 0.2], view), lt, 4.4);
      rise(eb, lt, 0.1, 16);
      lines(h1, lt, 0.15, 2.4);
      lines(h2, lt, 2.95);
    },
  };
}

/* ───────────── 5. 나란히 비교 ───────────── */
export function compare(venue, [T0, T1]) {
  const el = $('#s-compare');
  const slot = $('.slot3d', el);
  const h1 = $('#cmp1'), h2 = $('#cmp2'); splitWords(h1); splitWords(h2);
  const eb = $('.eyebrow', el);
  const chipA = $('#cmp-chip-a'), chipB = $('#cmp-chip-b');
  const statA = $('#cmp-a'), statB = $('#cmp-b');
  const numA = $('#cmp-a .num b'), numB = $('#cmp-b .num b');
  const flagA = $('#cmp-a .flag'), flagB = $('#cmp-b .flag');
  const note = $('.cmp-note', el), pin = $('#cmp-pin');
  let res;
  return {
    el, t0: T0, t1: T1,
    update(t) {
      const lt = t - T0;
      venue.ensure('theatre');
      venue.highlight(-1, null);
      res ??= { a: venue.analyze(12), b: venue.analyze(17) };
      $('#cmp-lower').textContent = res.a.lowerVisible;
      const pa = move(lt, 0, 0.9);                    // 이동: 전체 화면 → 왼쪽 패널
      const rectA = [lerp(0, 40, pa), lerp(0, 196, pa), lerp(1920, 900, pa), lerp(1080, 506, pa)];
      const pb = appear(lt, 0.35, 0.55);              // 등장: 오른쪽 화면 밖에서
      const rectB = [lerp(1960, 980, pb), 196, 900, 506];
      const yaw = range(lt, 0, 6, -0.015, 0.015, ease.move);
      const tint = move(lt, 3.45, 3.95);
      const vA = { rect: rectA, pose: venue.seatPose(12, { yaw }), before: () => venue.setRailTint(tint) };
      const vB = { rect: rectB, pose: venue.seatPose(17, { yaw }), before: () => venue.setRailTint(0) };
      venue.mount(slot, `path('${rr(rectA, lerp(0, 20, pa))} ${rr(rectB, 20)}')`);
      venue.render([vA, vB]);
      style(chipA, { x: rectA[0] + 22, y: rectA[1] + 22, opacity: appear(lt, 0.85) });
      style(chipB, { x: rectB[0] + 22, y: rectB[1] + 22, opacity: appear(lt, 1.0) });
      rise(eb, lt, 0.55, 14);
      lines(h1, lt, 0.65, 2.95);
      lines(h2, lt, 3.45);
      rise(statA, lt, 1.1, 30);
      rise(statB, lt, 1.25, 30);
      setNum(numA, range(lt, 1.15, 2.2, 0, res.a.visible, ease.move));
      setNum(numB, range(lt, 1.3, 2.35, 0, res.b.visible, ease.move));
      const fA = appear(lt, 2.2), fB = appear(lt, 2.35);
      style(flagA, { x: (1 - fA) * 20, opacity: fA });
      style(flagB, { x: (1 - fB) * 20, opacity: fB });
      style(note, { opacity: appear(lt, 1.6) });
      const pt = venue.project([0, venue.model.balconyHeight + venue.model.railHeight, 5.5 + venue.model.rowSpacing * 1.55], vA);
      placePin(pin, { x: pt.x - 150, y: pt.y }, lt, 3.6);
    },
  };
}

/* ───────────── 6. 가림 계산 ───────────── */
export function samples(venue, [T0, T1]) {
  const el = $('#s-samples');
  const slot = $('.slot3d', el);
  const dots = $('#smp-dots').getContext('2d');
  const h1 = $('#smp1'); splitWords(h1);
  const eb = $('.eyebrow', el), sub = $('#smp-sub .w');
  const card = $('#smp-card');
  const nBlocked = $('#smp-blocked'), nVisible = $('#smp-visible');
  const svg = $('#smp-svg');
  let res, rays, targets;
  // 측면 단면도(중앙 열): 눈 → 난간 → 무대 표본 13개. 좌표는 모델 치수에서 계산.
  function buildSection(model, seat) {
    const zMin = -1.6, zMax = 10.4, yMin = -0.2, yMax = 4.6;
    const W = 536, H = 250;
    const X = z => (z - zMin) / (zMax - zMin) * W;
    const Y = y => H - (y - yMin) / (yMax - yMin) * H;
    const eye = { z: seat.z, y: seat.floor + 1.2 };
    const railZ = 5.5 + model.rowSpacing * 1.55, railTop = model.balconyHeight + model.railHeight;
    const rows = 13, ts = Array.from({ length: rows }, (_, r) => 0.68 + r / (rows - 1) * 2.4);
    let s = '';
    s += `<path d="M${X(zMin)} ${Y(0)} H${X(zMax)}" stroke="rgba(255,255,255,.18)" stroke-width="2"/>`;
    s += `<rect x="${X(-model.stageDepth + 0.4)}" y="${Y(0.6)}" width="${X(0.4) - X(-model.stageDepth + 0.4)}" height="${Y(0) - Y(0.6)}" fill="rgba(255,255,255,.10)"/>`;
    s += `<path d="M${X(-0.25)} ${Y(0.68)} V${Y(3.08)}" stroke="rgba(255,255,255,.35)" stroke-width="2" stroke-dasharray="4 5"/>`;
    s += `<path d="M${X(railZ - 0.35)} ${Y(model.balconyHeight)} H${X(zMax)} V${Y(0)}" fill="none" stroke="rgba(255,255,255,.18)" stroke-width="2"/>`;
    s += `<rect x="${X(railZ) - 3}" y="${Y(railTop)}" width="6" height="${Y(model.balconyHeight) - Y(railTop)}" rx="2" fill="#ffae79"/>`;
    s += `<text x="${X(railZ) - 12}" y="${Y(model.balconyHeight) + 22}" fill="#ffae79" font-size="15" font-weight="600" font-family="Pretendard" text-anchor="middle">난간</text>`;
    s += `<text x="${X(-0.25) - 6}" y="${Y(3.08) - 12}" fill="rgba(255,255,255,.55)" font-size="15" font-weight="600" font-family="Pretendard" text-anchor="middle">무대 전면</text>`;
    const blockedRows = [];
    ts.forEach((ty, i) => {
      const f = (eye.z - railZ) / (eye.z + 0.25);
      const yAtRail = eye.y + (ty - eye.y) * f;
      const blocked = yAtRail < railTop && yAtRail > model.balconyHeight - 0.05;
      const endZ = blocked ? railZ : -0.25, endY = blocked ? yAtRail : ty;
      s += `<line class="ray" data-i="${i}" x1="${X(eye.z)}" y1="${Y(eye.y)}" x2="${X(endZ)}" y2="${Y(endY)}" stroke="${blocked ? '#ffae79' : 'rgba(199,239,123,.7)'}" stroke-width="${blocked ? 2 : 1.4}"/>`;
      s += `<circle class="tgt" data-i="${i}" cx="${X(-0.25)}" cy="${Y(ty)}" r="4" fill="${blocked ? '#ffae79' : '#c7ef7b'}"/>`;
      blockedRows.push(blocked);
    });
    s += `<circle cx="${X(eye.z)}" cy="${Y(eye.y)}" r="8" fill="#c7ef7b"/><circle cx="${X(eye.z)}" cy="${Y(eye.y)}" r="15" fill="none" stroke="rgba(199,239,123,.35)" stroke-width="2"/>`;
    s += `<text x="${X(eye.z)}" y="${Y(eye.y) - 26}" fill="#c7ef7b" font-size="15" font-weight="600" font-family="Pretendard" text-anchor="middle">C3 눈높이</text>`;
    svg.innerHTML = s;
    return $$('line.ray', svg).map((line, i) => {
      const len = Math.hypot(line.x2.baseVal.value - line.x1.baseVal.value, line.y2.baseVal.value - line.y1.baseVal.value);
      line.style.strokeDasharray = `${len}`;
      return { line, len, dot: $(`circle.tgt[data-i="${i}"]`, svg), blocked: blockedRows[i] };
    });
  }
  return {
    el, t0: T0, t1: T1,
    update(t) {
      const lt = t - T0;
      venue.ensure('theatre');
      venue.highlight(-1, null);
      if (!res) {
        res = venue.analyze(12);
        targets = getTargets(venue.model);
        rays = buildSection(venue.model, venue.seats[12]);
      }
      const yaw = range(lt, 0, 5, 0.01, -0.01, ease.move);
      const view = { rect: [0, 0, 1920, 1080], pose: venue.seatPose(12, { yaw, fov: 58 }), shiftX: 0.15 };
      venue.mount(slot);
      venue.render([view]);
      // 표본 점: 왼쪽 열부터 등장 → 판정(이동)으로 색이 바뀐다
      clear(dots);
      let judgedBlocked = 0;
      res.samples.forEach((sm, i) => {
        const tp = targets[i];
        const t0 = 0.45 + tp.column * 0.03 + tp.row * 0.012;
        const pa = appear(lt, t0, 0.45);
        if (lt < t0) return;
        const judge = 1.75 + tp.column * 0.028;
        const pj = move(lt, judge, judge + 0.25);
        if (pj >= 1 && sm.blocked) judgedBlocked++;
        const p = venue.project([sm.x, sm.y, sm.z], view);
        const r = 4.2 * pa * (sm.blocked ? 1 + 0.35 * pj : 1);
        let col;
        if (pj <= 0) col = `rgba(255,255,255,${0.75 * pa})`;
        else if (sm.blocked) col = `rgba(255,${Math.round(lerp(255, 174, pj))},${Math.round(lerp(255, 121, pj))},${lerp(0.75, 1, pj)})`;
        else col = `rgba(${Math.round(lerp(255, 199, pj))},${Math.round(lerp(255, 239, pj))},${Math.round(lerp(255, 123, pj))},${lerp(0.75, 0.9, pj)})`;
        dots.fillStyle = col;
        dots.beginPath(); dots.arc(p.x, p.y, r, 0, Math.PI * 2); dots.fill();
      });
      nBlocked.textContent = String(judgedBlocked);
      nVisible.innerHTML = `${Math.round(range(lt, 1.8, 2.8, 0, res.visible, ease.move))}<small>%</small>`;
      rays.forEach((r, i) => {
        r.line.style.strokeDashoffset = String(r.len * (1 - move(lt, 1.55 + i * 0.07, 1.9 + i * 0.07)));
        r.dot.style.opacity = String(appear(lt, 1.8 + i * 0.07, 0.3));
      });
      const pc = appear(lt, 0.25);
      style(card, { x: (1 - pc) * 60, opacity: pc });
      rise(eb, lt, 0.1, 16);
      lines(h1, lt, 0.2);
      maskLine(sub, lt, 0.6);
    },
  };
}

/* ───────────── 7. 공연별 무대 ───────────── */
export function layout(venue, [T0, T1]) {
  const el = $('#s-layout');
  const slot = $('.slot3d', el);
  const h1 = $('#ly1'); splitWords(h1);
  const eb = $('.eyebrow', el), sub = $('#ly-sub .w');
  const seg = $('#ly-seg'), knob = $('.knob', seg), opts = $$('.opt', seg);
  const stat = $('#ly-stat'), num = $('#ly-stat .num b'), pin = $('#ly-pin');
  const SWITCH = 1.5;
  let before, after;
  return {
    el, t0: T0, t1: T1,
    update(t) {
      const lt = t - T0;
      const concert = lt >= SWITCH;
      venue.ensure(concert ? 'concert' : 'theatre');
      venue.highlight(-1, null);
      before ??= venue.analyze(1, {}, 'theatre').visible;
      if (concert) {
        after ??= venue.analyze(1, {}, 'concert').visible;
        venue.setTowerRise(appear(lt, SWITCH + 0.05, 0.6)); // 등장: 바닥 아래(보이지 않는 곳)에서 올라옴
      }
      const pose = venue.seatPose(1, { yaw: range(lt, 0, 5, 0.035, -0.02, ease.move), fov: range(lt, 0, 5, 61, 57, ease.move) });
      const view = { rect: [0, 0, 1920, 1080], pose };
      venue.mount(slot);
      venue.render([view]);
      const pk = move(lt, SWITCH - 0.15, SWITCH + 0.25);
      knob.style.transform = `translateX(${pk * 184}px)`;
      opts[0].classList.toggle('on', pk < 0.5); opts[1].classList.toggle('on', pk >= 0.5);
      rise(seg, lt, 0.15, -20);
      rise(stat, lt, 0.4, 30);
      setNum(num, concert ? range(lt, SWITCH + 0.1, SWITCH + 1.0, before, after ?? before, ease.move) : before);
      if (concert) {
        const tw = venue.tower[0];
        placePin(pin, venue.project([tw.position.x, tw.position.y + 1.5, tw.position.z], view), lt, SWITCH + 0.75);
      } else placePin(pin, { x: 0, y: 0 }, lt, Infinity);
      rise(eb, lt, 0.1, 16);
      lines(h1, lt, 0.2);
      maskLine(sub, lt, 0.55);
    },
  };
}

/* ───────────── 8. AI 도면 인식 ───────────── */
export function ocr(venue, [T0, T1]) {
  const el = $('#s-ocr');
  const h1 = $('#ocr1'); splitWords(h1);
  const eb = $('#ocr-eb'), sub = $('#ocr-sub'), safe = $('#ocr-safe');
  const card = $('#ocr-card'), scan = $('#ocr-scan'), boxesEl = $('#ocr-boxes'), status = $('#ocr-status');
  const chipsEl = $('#ocr-chips'), count = $('#ocr-count b'), countWrap = $('#ocr-count');
  const k = 0.9, labels = Array.from({ length: 20 }, (_, i) => `${'ABCD'[Math.floor(i / 5)]}${i % 5 + 1}`);
  boxesEl.innerHTML = labels.map((_, i) => {
    const r = Math.floor(i / 5), c = i % 5;
    const x = (40 + c * 180 - 6) * k, y = (50 + r * 145 - 6) * k, w = (135 + 12) * k, h = (80 + 12) * k;
    return `<div class="box" style="left:${x}px;top:${y}px;width:${w}px;height:${h}px"></div>`;
  }).join('');
  chipsEl.innerHTML = labels.map(l => `<div class="c">${l}</div>`).join('');
  const boxes = $$('.box', boxesEl), chips = $$('.c', chipsEl);
  const SCAN0 = 0.95, SCAN1 = 2.55;
  const scanY = lt => lerp(-130, 600, move(lt, SCAN0, SCAN1));
  // 스캔선 아래 끝이 행 중앙을 지나는 시각
  const rowTime = r => {
    const target = (90 + r * 145) * k;
    let lo = SCAN0, hi = SCAN1;
    for (let i = 0; i < 30; i++) { const mid = (lo + hi) / 2; if (scanY(mid) + 120 < target) lo = mid; else hi = mid; }
    return hi;
  };
  const hit = labels.map((_, i) => rowTime(Math.floor(i / 5)) + (i % 5) * 0.045);
  return {
    el, t0: T0, t1: T1,
    update(t) {
      const lt = t - T0;
      rise(eb, lt, 0.1, 16);
      lines(h1, lt, 0.2, Infinity, { stagger: 0.07 });
      rise(sub, lt, 0.7, 24);
      rise(safe, lt, 1.05, 20);
      const pc = appear(lt, 0.0, 0.55);
      style(card, { x: (1 - pc) * 90, opacity: pc });
      // 스캔선: 투명에서 등장 → 이동 → 완전히 사라짐
      style(scan, { y: scanY(lt), opacity: appear(lt, SCAN0 - 0.15, 0.3) * (1 - vanish(lt, SCAN1 - 0.1, 0.35)) });
      let n = 0;
      boxes.forEach((b, i) => {
        const p = appear(lt, hit[i], 0.4);
        if (lt >= hit[i]) n++;
        style(b, { scale: lerp(1.25, 1, p), opacity: p });
        chips[i].classList.toggle('on', lt >= hit[i] + 0.08);
        const pch = appear(lt, 0.9 + i * 0.012);
        const pop = bump(lt, hit[i] + 0.08, 0.3) * 0.12;
        style(chips[i], { y: (1 - pch) * 16 - pop * 40, scale: 1 + pop, opacity: pch });
      });
      count.textContent = String(n);
      style(countWrap, { opacity: appear(lt, 1.1) });
      status.textContent = n >= 20 ? '후보 20개 · 확인 대기' : '인식 중…';
    },
  };
}

/* ───────────── 9. 치수 보정 ───────────── */
export function calibrate(venue, [T0, T1]) {
  const el = $('#s-cal');
  const slot = $('.slot3d', el);
  const h1 = $('#cal1'); splitWords(h1);
  const eb = $('.eyebrow', el);
  const ctrl = $('#cal-ctrl'), val = $('#cal-ctrl .val b'), fill = $('#cal-ctrl .fill'), knob = $('#cal-ctrl .knob');
  const stat = $('#cal-stat'), num = $('#cal-stat .num b');
  const H0 = 1.0, H1 = 0.4, M0 = 1.1, M1 = 2.5;
  const railAt = lt => lerp(H0, H1, move(lt, M0, M1));
  return {
    el, t0: T0, t1: T1,
    update(t) {
      const lt = t - T0;
      venue.ensure('theatre');
      venue.highlight(-1, null);
      const h = railAt(lt);
      venue.setRailHeight(h);
      const view = { rect: [0, 0, 1920, 1080], pose: venue.seatPose(12, { yaw: range(lt, 0, 4, 0.02, -0.02, ease.move), pitch: -0.035, fov: 60 }) };
      venue.mount(slot);
      venue.render([view]);
      venue.setRailHeight(venue.model.railHeight);
      const f = (h - 0.4) / 1.1;
      fill.style.width = `${f * 100}%`; knob.style.left = `${f * 100}%`;
      val.textContent = h.toFixed(2);
      rise(ctrl, lt, 0.2, -24);
      rise(stat, lt, 0.45, 30);
      // 난간 높이별 실제 표본 계산값(69 → 77 → 92 → 100%)을 그대로 보여준다.
      setNum(num, venue.analyze(12, { railHeight: h }).visible);
      rise(eb, lt, 0.1, 16);
      lines(h1, lt, 0.2);
    },
  };
}

/* ───────────── 10. 신뢰 ───────────── */
export function trust(venue, [T0, T1]) {
  const el = $('#s-trust');
  const head = $('#tr-head'); splitWords(head);
  const badges = $$('.badge', el);
  const END = T1 - T0;
  return {
    el, t0: T0, t1: T1,
    update(t) {
      const lt = t - T0;
      lines(head, lt, 0.08, exitBy(head, END));
      badges.forEach((b, i) => {
        const p = appear(lt, 0.35 + i * 0.12);
        const o = vanish(lt, END - 0.46 + i * 0.02);   // 장면이 끝나기 전에 완전히 사라진다
        style(b, { y: (1 - p) * 70 - o * 60, opacity: p * (1 - o) });
      });
    },
  };
}

/* ───────────── 11. 엔드카드 ───────────── */
export function end(venue, [T0, T1]) {
  const el = $('#s-end');
  el.style.visibility = 'visible';
  const L = makeLockup($('#end-lockup'));
  el.style.visibility = '';
  const tag = $('#end-tag'); splitWords(tag);
  const feats = $$('#end-feats span'), disc = $('#end-disc');
  return {
    el, t0: T0, t1: T1 + 1,
    update(t) {
      const lt = t - T0;
      animateLockup(L, lt, { tileAt: 0.05, wordAt: 0.45, shift: false, top: 372 });
      lines(tag, lt, 1.0);
      feats.forEach((f, i) => rise(f, lt, 1.45 + i * 0.08, 20));
      style(disc, { opacity: appear(lt, 2.0) });
    },
  };
}
