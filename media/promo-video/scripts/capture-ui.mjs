// 실제 시야체크 앱(빌드본)을 띄워 영상에 쓸 고해상도 UI 캡처를 만든다.
// 사용: 루트에서 `npm run build` 후 `npm run capture-ui` (media/promo-video/ 폴더)
import { chromium } from 'playwright-core';
import { spawn } from 'node:child_process';
import path from 'node:path';
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, '../../..');
const out = path.resolve(here, '../assets/ui');
const port = 4199;

const server = spawn(process.execPath, [path.join(repo, 'scripts/serve.mjs')], { env: { ...process.env, SIGHTCHECK_PORT: String(port) }, stdio: 'inherit' });
await new Promise(r => setTimeout(r, 800));

const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 2 });
// Google Fonts 요청을 로컬 Noto Sans KR(@fontsource-variable)로 대체해 앱과 같은 글꼴로 캡처한다.
const fontDir = path.resolve(here, '../node_modules/@fontsource-variable/noto-sans-kr');
const fontCss = (await readFile(path.join(fontDir, 'index.css'), 'utf8'))
  .replaceAll("'Noto Sans KR Variable'", "'Noto Sans KR'")
  .replaceAll('url(./files/', 'url(https://local-fonts.invalid/files/');
await context.route('https://fonts.googleapis.com/**', route => route.fulfill({ contentType: 'text/css', body: fontCss }));
await context.route('https://local-fonts.invalid/files/**', async route => {
  const file = path.join(fontDir, 'files', path.basename(new URL(route.request().url()).pathname));
  route.fulfill({ contentType: 'font/woff2', body: await readFile(file) });
});
const page = await context.newPage();
page.on('console', m => m.type() === 'error' && console.error('[page]', m.text()));
await page.goto(`http://127.0.0.1:${port}/`);
await page.evaluate(() => document.fonts.ready);
await page.waitForFunction(() => Number(document.querySelector('#scene canvas')?.dataset.renderCount || 0) > 0);
const settle = () => page.waitForTimeout(600);
const rects = {};
// 영상에서 커서·줌 위치를 맞추기 위해 주요 요소의 CSS 픽셀 좌표를 함께 저장한다.
const measure = () => page.evaluate(() => Object.fromEntries(Object.entries({
  seatC3: '[data-seat="12"]', seatA3: '[data-seat="2"]', sceneFrame: '.scene-frame', seatPanel: '.seat-panel', detailPanel: '.detail-panel',
}).map(([key, sel]) => { const r = document.querySelector(sel)?.getBoundingClientRect(); return [key, r && { x: r.x, y: r.y, w: r.width, h: r.height }]; })));
const shot = async name => { await settle(); rects[name] = await measure(); await page.screenshot({ path: path.join(out, `${name}.png`) }); console.log('saved', name); };

// 1) A3를 고른 상태 → 커서가 C3를 누르기 전 화면
await page.click('[data-seat="2"]');
await shot('ui-a3');
// 2) 기본 C3 선택 화면
await page.click('[data-seat="12"]');
await shot('ui-c3');
await writeFile(path.join(out, 'rects.json'), JSON.stringify(rects, null, 2));
await browser.close();
server.kill();
