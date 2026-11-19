"""Build the reader images for every gray seat cell of the JPEG plans.

A full-map reading needs a context image and a crop for each CV-detected cell,
not only for the review samples. The images are drawn exactly like the review
samples (run_experiment.py), so a reader sees the same kind of input that the
blind experiment measured. Cells that are already review samples reuse their
saved images; --verify redraws those and checks that the pixels match.

Writes <output-dir>/cell-items.json ({"samples": [{sample_id, context, crop}]},
paths relative to the output folder) for claude_preread.py --cells. New images
go to cell-contexts/ and cell-crops/ in the Git-ignored output folder.
"""
from pathlib import Path
import argparse
import json
import tempfile

import numpy as np
from PIL import Image

from run_experiment import jpeg_context, seat_crop_bounds, write_seat_crop

BASE = Path(__file__).resolve().parent
THEATRES = ['theatre-2', 'theatre-3']


def draw_cell(source, bbox, context_path, crop_path):
    """Write one cell's context and crop with the review-sample drawing."""
    jpeg_context(source, bbox).save(context_path, compress_level=1)
    write_seat_crop(source, bbox, 1, seat_crop_bounds(bbox, 1, source.size, 'px'), 'px', crop_path)


def review_samples(out):
    path = out/'review-template.json'
    if not path.exists():
        return {}
    return {s['sample_id']: s for s in json.loads(path.read_text(encoding='utf-8'))['samples'] if s['unit'] == 'px'}


def build(out, theatres=THEATRES):
    """Return the item list, drawing images only for cells without saved review images."""
    samples = review_samples(out)
    (out/'cell-contexts').mkdir(exist_ok=True)
    (out/'cell-crops').mkdir(exist_ok=True)
    items, drawn = [], 0
    for theatre in theatres:
        cells = json.loads((out/theatre/'seats.json').read_text(encoding='utf-8'))['seats']
        with Image.open(out/theatre/'rgb.png') as source:
            source = source.convert('RGB')
            for cell in cells:
                sid = f"{theatre}--{cell['candidate_id']}"
                saved = samples.get(sid)
                if saved and (out/f'review-contexts/{sid}.png').exists() and (out/saved['crop']).exists():
                    items.append({'sample_id': sid, 'context': f'review-contexts/{sid}.png', 'crop': saved['crop']})
                    continue
                context, crop = f'cell-contexts/{sid}.png', f'cell-crops/{sid}.png'
                if not ((out/context).exists() and (out/crop).exists()):
                    draw_cell(source, cell['bbox_px'], out/context, out/crop)
                    drawn += 1
                items.append({'sample_id': sid, 'context': context, 'crop': crop})
    return items, drawn


def verify(out, items):
    """Redraw reused review-sample images and count pixel mismatches."""
    reused = [it for it in items if it['context'].startswith('review-contexts/')]
    by_theatre = {}
    for it in reused:
        by_theatre.setdefault(it['sample_id'].split('--')[0], []).append(it)
    mismatched = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for theatre, group in by_theatre.items():
            cells = {c['candidate_id']: c for c in
                     json.loads((out/theatre/'seats.json').read_text(encoding='utf-8'))['seats']}
            with Image.open(out/theatre/'rgb.png') as source:
                source = source.convert('RGB')
                for it in group:
                    draw_cell(source, cells[it['sample_id'].split('--', 1)[1]]['bbox_px'],
                              tmp/'context.png', tmp/'crop.png')
                    for fresh, saved in ((tmp/'context.png', out/it['context']), (tmp/'crop.png', out/it['crop'])):
                        with Image.open(fresh) as a, Image.open(saved) as b:
                            if a.size != b.size or not np.array_equal(np.asarray(a.convert('RGB')),
                                                                      np.asarray(b.convert('RGB'))):
                                mismatched.append(saved.relative_to(out).as_posix())
    return len(reused), mismatched


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output-dir', type=Path, default=BASE/'output/phase-abc')
    parser.add_argument('--theatre', action='append', help='Theatre folder; default: theatre-2 and theatre-3')
    parser.add_argument('--verify', action='store_true',
                        help='Redraw the reused review-sample images and require identical pixels')
    args = parser.parse_args()
    out = args.output_dir
    items, drawn = build(out, args.theatre or THEATRES)
    (out/'cell-items.json').write_text(json.dumps({'samples': items}, indent=1), encoding='utf-8')
    reused = sum(it['context'].startswith('review-contexts/') for it in items)
    print(f'{len(items)} cells: {reused} reuse review-sample images, {len(items) - reused} in cell-*/ '
          f'({drawn} drawn now); wrote cell-items.json')
    if args.verify:
        checked, mismatched = verify(out, items)
        print(f'Verified {checked} reused cells: {len(mismatched)} image mismatches')
        if mismatched:
            raise SystemExit('Mismatch: ' + ', '.join(mismatched[:10]))


if __name__ == '__main__':
    main()
