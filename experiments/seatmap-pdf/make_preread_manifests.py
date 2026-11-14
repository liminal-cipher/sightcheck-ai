"""Split JPEG review samples into model pre-read manifests and render the reader prompt.

Reproduces the 2026-11-14 pre-read: JPEG samples sorted by sample_id, shuffled
with random.Random(seed), then dealt into parts (part k takes every n-th item
starting at k). Each part gets manifest-NN.json and prompt-NN.txt, the prompt
rendered from prompts/seat-reader.md.
"""
from pathlib import Path
import argparse
import json
import random
import re

BASE = Path(__file__).resolve().parent
TEMPLATE = BASE/'prompts/seat-reader.md'


def split(review, parts, seed, only=None):
    ids = sorted(s['sample_id'] for s in review['samples'] if s['unit'] == 'px' and (only is None or s['sample_id'] in only))
    if only is not None and len(ids) != len(only):
        raise ValueError(f'{len(only) - len(ids)} requested sample IDs are not JPEG review samples')
    random.Random(seed).shuffle(ids)
    return [ids[k::parts] for k in range(parts)]


def load_template(path=TEMPLATE):
    match = re.search(r'```text\n(.*?)\n```', path.read_text(encoding='utf-8'), re.S)
    if not match:
        raise ValueError(f'No ```text block in {path}')
    return match.group(1)


def render(template, manifest_path, result_path):
    return template.replace('{manifest_path}', str(manifest_path)).replace('{result_path}', str(result_path))


def write_parts(review, output_dir, dest, parts, seed, template, only=None):
    crops = {s['sample_id']: s['crop'] for s in review['samples']}
    dest.mkdir(parents=True, exist_ok=True)
    for k, ids in enumerate(split(review, parts, seed, only), start=1):
        items = [{'sample_id': sid, 'context_image': str(output_dir/'review-contexts'/f'{sid}.png'),
                  'crop_image': str(output_dir/crops[sid])} for sid in ids]
        manifest = dest/f'manifest-{k:02d}.json'
        manifest.write_text(json.dumps({'part': k, 'items': items}, indent=1), encoding='utf-8')
        (dest/f'prompt-{k:02d}.txt').write_text(render(template, manifest, dest/f'result-{k:02d}.json'), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=BASE/'output/phase-abc')
    parser.add_argument('--dest', type=Path, default=None, help='Defaults to <output-dir>/subagent-preread')
    parser.add_argument('--parts', type=int, default=10)
    parser.add_argument('--seed', type=int, default=7)
    parser.add_argument('--only', type=Path, default=None, help='Text file of sample IDs (one per line) to restrict the split to')
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    dest = (args.dest or output_dir/'subagent-preread').resolve()
    review = json.loads((output_dir/'review-template.json').read_text(encoding='utf-8'))
    only = set(args.only.read_text(encoding='utf-8').split()) if args.only else None
    write_parts(review, output_dir, dest, args.parts, args.seed, load_template(), only)
    print(args.parts, dest)


if __name__ == '__main__':
    main()
