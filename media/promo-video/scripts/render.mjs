// 프레임 단위 렌더러: 영상 페이지를 여러 브라우저 페이지로 나눠 캡처하고 ffmpeg로 인코딩한다.
// 사용: node scripts/render.mjs [--fps 60] [--workers 4] [--from 0] [--to 54] [--out out/sightcheck-promo.mp4] [--crf 18] [--scale 1]
import { launch } from './browser.mjs';
import { spawn } from 'node:child_process';
import { mkdir, writeFile, rm, access } from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { startServer } from './server.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');
const arg = (name, def) => { const i = process.argv.indexOf(`--${name}`); return i > 0 ? process.argv[i + 1] : def; };
const fps = Number(arg('fps', 60));
const workers = Number(arg('workers', 2)); // SwiftShader가 이미 모든 코어를 쓰므로 2개면 충분하다
const crf = String(arg('crf', 18));
const scale = Number(arg('scale', 1));
const out = path.resolve(root, arg('out', 'out/sightcheck-promo.mp4'));
const audio = path.resolve(root, arg('audio', 'out/soundtrack.wav'));
const segDir = path.resolve(root, 'out/segments');
await mkdir(segDir, { recursive: true });
await mkdir(path.dirname(out), { recursive: true });

const port = 4800 + Math.floor(Math.random() * 400);
const server = await startServer(port);
const browser = await launch();

const probe = await browser.newPage();
await probe.goto(`http://127.0.0.1:${port}/media/promo-video/?render`);
await probe.waitForFunction(() => window.__ready === true, null, { timeout: 60000 });
const duration = await probe.evaluate(() => window.__duration);
await probe.close();
const from = Number(arg('from', 0)), to = Math.min(Number(arg('to', duration)), duration);
const first = Math.round(from * fps), last = Math.round(to * fps); // [first, last)
const total = last - first;
console.log(`렌더: ${total}프레임 (${from}s–${to}s @${fps}fps), 작업자 ${workers}개`);

const vf = scale !== 1 ? ['-vf', `scale=${Math.round(1920 * scale)}:${Math.round(1080 * scale)}:flags=lanczos`] : [];
const started = Date.now();
let done = 0;
async function work(w) {
  const a = first + Math.floor(total * w / workers), b = first + Math.floor(total * (w + 1) / workers);
  const seg = path.join(segDir, `seg-${String(w).padStart(2, '0')}.mp4`);
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  page.on('pageerror', e => console.error(`[w${w}]`, e.message));
  await page.goto(`http://127.0.0.1:${port}/media/promo-video/?render`);
  await page.waitForFunction(() => window.__ready === true, null, { timeout: 60000 });
  const cdp = await page.context().newCDPSession(page);
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'png', '-i', '-',
    ...vf, '-c:v', 'libx264', '-preset', 'slow', '-crf', crf, '-pix_fmt', 'yuv420p', '-profile:v', 'high',
    '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-movflags', '+faststart', seg], { stdio: ['pipe', 'inherit', 'inherit'] });
  const ffDone = new Promise((res, rej) => ff.on('close', c => (c === 0 ? res() : rej(new Error(`ffmpeg ${c}`)))));
  for (let f = a; f < b; f++) {
    await page.evaluate(t => window.__seek(t), f / fps);
    const { data } = await cdp.send('Page.captureScreenshot', { format: 'png', clip: { x: 0, y: 0, width: 1920, height: 1080, scale: 1 }, optimizeForSpeed: true });
    const buf = Buffer.from(data, 'base64');
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    done++;
    if (done % 60 === 0) {
      const el = (Date.now() - started) / 1000;
      console.log(`  ${done}/${total}  ${(done / el).toFixed(1)} fps  남은 시간 ~${Math.round((total - done) / (done / el))}s`);
    }
  }
  ff.stdin.end();
  await ffDone;
  await page.close();
  return seg;
}
const segs = await Promise.all(Array.from({ length: workers }, (_, w) => work(w)));
await browser.close();
server.close();

const list = path.join(segDir, 'list.txt');
await writeFile(list, segs.map(s => `file '${s}'`).join('\n'));
let hasAudio = true;
try { await access(audio); } catch { hasAudio = false; }
const args = ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', list];
if (hasAudio) args.push('-ss', String(from), '-t', String(to - from), '-i', audio, '-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-b:a', '192k', '-shortest');
args.push('-c:v', 'copy', '-movflags', '+faststart', out);
await new Promise((res, rej) => spawn('ffmpeg', args, { stdio: 'inherit' }).on('close', c => (c === 0 ? res() : rej(new Error(`ffmpeg concat ${c}`)))));
await rm(segDir, { recursive: true, force: true });
console.log(`완료: ${out} (${((Date.now() - started) / 1000).toFixed(0)}s${hasAudio ? ', 오디오 포함' : ', 오디오 없음'})`);
