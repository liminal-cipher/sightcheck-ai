// Independent local experiment. No product parser or remote language downloads.
import { createWorker, PSM } from 'tesseract.js';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const jobs = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
const worker = await createWorker('eng', 1, {
  langPath: path.join(root, 'public/ocr'), cacheMethod: 'none',
  corePath: path.join(root, 'node_modules/tesseract.js-core'),
  workerPath: path.join(root, 'node_modules/tesseract.js/src/worker-script/node/index.js'),
});
try {
  for (const job of jobs) {
    await worker.setParameters({
      tessedit_pageseg_mode: PSM.SPARSE_TEXT,
      tessedit_char_whitelist: job.kind === 'numbers' ? '0123456789' :
        job.kind === 'letters' ? 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' : 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-',
      user_defined_dpi: '300',
    });
    const { data } = await worker.recognize(job.image, {}, { text: true, blocks: true });
    let words = (data.blocks ?? []).flatMap(b => b.paragraphs ?? [])
      .flatMap(p => p.lines ?? []).flatMap(l => l.words ?? [])
      .map(w => ({ text: w.text, confidence: w.confidence, bbox: w.bbox }));
    const sparseText = data.text;
    for (const entry of job.tiles ?? []) {
      const [x0, y0, x1, y1] = entry.tile;
      const inside = w => (w.bbox.x0 + w.bbox.x1) / 2 >= x0 &&
        (w.bbox.x0 + w.bbox.x1) / 2 < x1 &&
        (w.bbox.y0 + w.bbox.y1) / 2 >= y0 && (w.bbox.y0 + w.bbox.y1) / 2 < y1;
      if (words.filter(inside).some(w => w.confidence >= 60)) continue;
      await worker.setParameters({ tessedit_pageseg_mode:
        job.kind === 'letters' ? PSM.SINGLE_CHAR : PSM.SINGLE_LINE });
      const { data: retry } = await worker.recognize(job.image, {
        rectangle: { left: x0, top: y0, width: x1 - x0, height: y1 - y0 },
      }, { text: true, blocks: true });
      const replacement = (retry.blocks ?? []).flatMap(b => b.paragraphs ?? [])
        .flatMap(p => p.lines ?? []).flatMap(l => l.words ?? [])
        .map(w => ({ text: w.text, confidence: w.confidence, bbox: w.bbox, fallback: true }));
      if (replacement.length) words = [...words.filter(w => !inside(w)), ...replacement];
    }
    await fs.writeFile(job.output, JSON.stringify({ sparseText, words }, null, 2));
    console.log(`${path.basename(job.image)}: ${words.length} OCR words`);
  }
} finally { await worker.terminate(); }
