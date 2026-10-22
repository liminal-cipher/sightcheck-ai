// QC용 정지 프레임 캡처. 사용: node scripts/stills.mjs out/stills 1 2.5 4 ...
import { launch } from './browser.mjs';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { startServer } from './server.mjs';

const [outDir = 'out/stills', ...times] = process.argv.slice(2);
await mkdir(outDir, { recursive: true });
const port = 4300 + Math.floor(Math.random() * 500);
const server = await startServer(port);
const browser = await launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
page.on('console', m => ['error', 'warning'].includes(m.type()) && console.error('[page]', m.text()));
page.on('pageerror', e => console.error('[pageerror]', e.message));
await page.goto(`http://127.0.0.1:${port}/media/promo-video/?render`);
await page.waitForFunction(() => window.__ready === true, null, { timeout: 60000 });
for (const t of times.map(Number)) {
  await page.evaluate(t => window.__seek(t), t);
  const file = path.join(outDir, `t${t.toFixed(2).padStart(6, '0')}.png`);
  await page.locator('#stage').screenshot({ path: file });
  console.log(file);
}
await browser.close();
server.close();
