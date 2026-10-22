// 영상 페이지 부트스트랩. window.__seek(t)로 특정 시각의 프레임을 결정적으로 그린다.
import timeline from './timeline.json' with { type: 'json' };
import { Venue } from './venue.js';
import * as S from './scenes.js';

const params = new URLSearchParams(location.search);
const stage = document.getElementById('stage');

await document.fonts.load('700 50px Pretendard');
await document.fonts.load('500 20px Pretendard');
await document.fonts.ready;
await Promise.all([...document.images].map(img => img.decode().catch(() => {})));

const venue = new Venue(timeline.width, timeline.height);
const order = ['hook', 'brand', 'ui', 'pov', 'compare', 'samples', 'layout', 'ocr', 'calibrate', 'trust', 'end'];
const scenes = order.map(id => S[id](venue, timeline.scenes[id]));

function seek(t) {
  for (const s of scenes) {
    const active = t >= s.t0 && t < s.t1;
    s.el.style.visibility = active ? 'visible' : 'hidden';
    if (active) s.update(t);
  }
}

window.__duration = timeline.duration;
window.__seek = t => { seek(t); return true; };
window.__ready = true;

// ── 미리보기 ──
if (!params.has('render')) {
  document.body.classList.add('preview');
  const fit = () => { const k = Math.min(innerWidth / 1920, innerHeight / 1080); stage.style.transform = `translate(${(innerWidth - 1920 * k) / 2}px, ${(innerHeight - 1080 * k) / 2}px) scale(${k})`; };
  addEventListener('resize', fit); fit();
  const slider = document.getElementById('hud-t'), label = document.getElementById('hud-v'), btn = document.getElementById('hud-play');
  slider.max = String(timeline.duration);
  let playing = params.has('play'), t = Number(params.get('t') || 0), last = performance.now();
  const audio = new Audio('assets/audio/soundtrack.wav');
  const show = () => { seek(t); slider.value = String(t); label.textContent = `${t.toFixed(2)}s`; };
  slider.addEventListener('input', () => { t = Number(slider.value); audio.currentTime = t; show(); });
  btn.addEventListener('click', () => { playing = !playing; last = performance.now(); if (playing) { audio.currentTime = t; audio.play().catch(() => {}); } else audio.pause(); });
  const loop = now => {
    if (playing) { t += (now - last) / 1000; if (t >= timeline.duration) t = 0; show(); }
    last = now; requestAnimationFrame(loop);
  };
  show(); requestAnimationFrame(loop);
}
