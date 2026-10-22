// 결정적(deterministic) 타임라인 도우미. 모든 장면은 시간 t만으로 상태를 계산한다.
export const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
export const lerp = (a, b, t) => a + (b - a) * t;

// CSS cubic-bezier()와 같은 계산(WebKit UnitBezier 방식: 뉴턴법 + 이분법).
export function cubicBezier(x1, y1, x2, y2) {
  const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx;
  const cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
  const sx = t => ((ax * t + bx) * t + cx) * t;
  const sy = t => ((ay * t + by) * t + cy) * t;
  const dx = t => (3 * ax * t + 2 * bx) * t + cx;
  const solve = x => {
    let t = x;
    for (let i = 0; i < 8; i++) {
      const err = sx(t) - x;
      if (Math.abs(err) < 1e-7) return t;
      const d = dx(t);
      if (Math.abs(d) < 1e-6) break;
      t -= err / d;
    }
    let lo = 0, hi = 1;
    t = x;
    for (let i = 0; i < 60; i++) {
      const v = sx(t);
      if (Math.abs(v - x) < 1e-7) break;
      if (x > v) lo = t; else hi = t;
      t = (lo + hi) / 2;
    }
    return t;
  };
  return x => (x <= 0 ? 0 : x >= 1 ? 1 : sy(solve(x)));
}

// 영상 전체에서 쓰는 이징은 이 세 가지뿐이다(LOOK.md 참고).
export const ease = {
  linear: t => t,
  enter: cubicBezier(0, 0, 0, 1),        // 등장: 화면 밖·투명 상태에서 들어올 때만, 0.5초 안팎
  move: cubicBezier(0.65, 0, 0.35, 1),   // 이동: 보이는 요소의 위치·크기·값·카메라 변화
  exit: cubicBezier(0.55, 0, 0.9, 0.45), // 퇴장: 화면 밖으로 나가거나 완전히 사라지며 끝남
};
export const ENTER = 0.5;

// t가 [t0, t1] 구간에서 0→1로 진행하는 비율
export const prog = (t, t0, t1, fn = ease.linear) => fn(clamp((t - t0) / (t1 - t0)));
// 값 보간
export const range = (t, t0, t1, v0, v1, fn = ease.linear) => lerp(v0, v1, prog(t, t0, t1, fn));
// 등장 진행(0→1, 0.5초, 등장 곡선)
export const appear = (t, t0, d = ENTER) => prog(t, t0, t0 + d, ease.enter);
// 퇴장 진행(0→1, 퇴장 곡선). 1이 되는 순간 요소는 완전히 사라져 있어야 한다.
export const vanish = (t, t0, d = 0.4) => prog(t, t0, t0 + d, ease.exit);
// 이동 진행(0→1, 이동 곡선)
export const move = (t, t0, t1) => prog(t, t0, t1, ease.move);
// 갔다가 돌아오는 이동(0→1→0): 앞 절반과 뒤 절반을 각각 이동 곡선으로
export const bump = (t, t0, d) => move(t, t0, t0 + d / 2) - move(t, t0 + d / 2, t0 + d);

// 요소 스타일을 한 번에 지정
export function style(el, { x = 0, y = 0, scale = 1, sx, sy, rot = 0, rx = 0, opacity, clip, origin } = {}) {
  if (!el) return;
  const s = sx != null || sy != null ? `scale(${sx ?? scale}, ${sy ?? scale})` : `scale(${scale})`;
  el.style.transform = `translate3d(${x}px, ${y}px, 0) ${rx ? `perspective(1800px) rotateX(${rx}deg)` : ''} rotate(${rot}deg) ${s}`;
  if (opacity != null) el.style.opacity = String(clamp(opacity));
  if (clip != null) el.style.clipPath = clip;
  if (origin != null) el.style.transformOrigin = origin;
}

// 줄 마스크 슬라이드업: 단어가 마스크 아래에서 올라오고(등장), 위로 빠져나간다(퇴장).
export const HIDE = 125; // 마스크 밖으로 숨기는 거리(%)

export function lines(root, t, t0, t1 = Infinity, { stagger = 0.06, dIn = ENTER, dOut = 0.4 } = {}) {
  if (!root) return;
  const items = root.querySelectorAll('.w');
  const visible = t >= t0 - 0.01 && (t1 === Infinity || t < t1 + dOut + stagger * items.length);
  root.style.visibility = visible ? 'visible' : 'hidden';
  if (!visible) return;
  items.forEach((w, i) => {
    const pin = appear(t, t0 + i * stagger, dIn);
    const pout = t1 === Infinity ? 0 : vanish(t, t1 + i * stagger * 0.4, dOut);
    const y = (1 - pin) * HIDE - pout * HIDE;
    w.style.transform = `translate3d(0, ${y}%, 0)`;
  });
}

// "같은 층, 같은 가격." → 단어마다 마스크 구조를 만든다. \n은 줄바꿈.
export function splitWords(el) {
  const text = (el.dataset.text ?? el.textContent).replace(/\\n/g, '\n');
  el.dataset.text = text;
  // *강조*는 여러 단어에 걸칠 수 있다.
  let inEm = false;
  const word = w => {
    let out = '';
    for (const part of w.split(/(\*)/)) {
      if (part === '*') { inEm = !inEm; continue; }
      if (part) out += inEm ? `<em>${part}</em>` : part;
    }
    return `<span class="m"><span class="w">${out}</span></span>`;
  };
  el.innerHTML = text.split('\n').map(line => `<span class="line">${line.split(' ').map(word).join(' ')}</span>`).join('');
}
