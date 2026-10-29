// 레포 루트를 정적으로 서비스한다. 영상 페이지: http://127.0.0.1:4300/media/promo-video/
// (영상 모듈이 저장소 루트의 src/scene.js와 node_modules/three를 불러오기 때문에 루트를 연다)
import http from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const mime = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.woff2': 'font/woff2', '.wav': 'audio/wav', '.mp3': 'audio/mpeg', '.mp4': 'video/mp4' };

export function startServer(port = Number(process.env.PORT || 4300)) {
  const server = http.createServer(async (req, res) => {
    try {
      let pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
      if (pathname.endsWith('/')) pathname += 'index.html';
      const file = path.resolve(root, `.${pathname}`);
      if (path.relative(root, file).startsWith('..')) { res.writeHead(403); res.end(); return; }
      if (!(await stat(file)).isFile()) throw new Error('not file');
      const data = await readFile(file);
      res.writeHead(200, { 'Content-Type': mime[path.extname(file)] || 'application/octet-stream', 'Cache-Control': 'no-cache' });
      res.end(data);
    } catch { res.writeHead(404); res.end('Not found'); }
  });
  return new Promise(resolve => server.listen(port, '127.0.0.1', () => resolve(server)));
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const port = Number(process.env.PORT || 4300);
  await startServer(port);
  console.log(`미리보기: http://127.0.0.1:${port}/media/promo-video/  (?t=12.5 특정 시점, ?play 재생)`);
}
