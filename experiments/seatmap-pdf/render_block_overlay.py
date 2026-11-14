"""Render block-colored review overlays from saved PDF layout results.

Each seat text box is filled with its assigned block's color and each block
region is outlined in the same color, so a reviewer can scan one image per
layout for seats whose color differs from their visual block. The input PDF
is opened read-only; drawing happens on an in-memory page.
"""
from collections import Counter
from pathlib import Path
import argparse
import json

import fitz

BASE = Path(__file__).resolve().parent
# Twelve hues chosen to stay distinct when neighboring blocks are adjacent letters.
PALETTE = [
    (0.90, 0.10, 0.29), (0.00, 0.51, 0.78), (0.24, 0.71, 0.29), (0.96, 0.51, 0.19),
    (0.57, 0.12, 0.71), (0.00, 0.62, 0.62), (0.94, 0.20, 0.90), (0.60, 0.39, 0.14),
    (0.10, 0.10, 0.55), (0.75, 0.68, 0.00), (0.50, 0.50, 0.50), (0.00, 0.35, 0.20),
]


def block_colors(blocks):
    return {block: PALETTE[i % len(PALETTE)] for i, block in enumerate(sorted(blocks))}


def render(pdf_path, layout, output_path, scale):
    seats = layout['seats']
    colors = block_colors({s['block'] for s in seats} | {r['block'] for r in layout['block_regions']})
    with fitz.open(pdf_path) as document:
        page = document[0]
        for region in layout['block_regions']:
            color = colors[region['block']]
            page.draw_rect(fitz.Rect(region['bbox_pt']), color=color, width=1.6, dashes='[4 2] 0', overlay=True)
            page.draw_rect(fitz.Rect(region['label_bbox_pt']), color=color, fill=color,
                           fill_opacity=0.25, width=1.2, overlay=True)
        for seat in seats:
            color = colors[seat['block']]
            page.draw_rect(fitz.Rect(seat['text_bbox_pt']), color=color, fill=color,
                           fill_opacity=0.45, width=0.4, overlay=True)
        for missing in layout['unmatched']:
            page.draw_rect(fitz.Rect(missing['bbox_pt']), color=(1, 0, 0), width=2.0, overlay=True)
        page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).save(output_path)
    return Counter(s['block'] for s in seats)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, default=BASE/'input/theatre-1')
    parser.add_argument('--layout-dir', type=Path, default=BASE/'output/phase-abc/theatre-1',
                        help='Folder holding <layout>/seats.json from extract_layout.py')
    parser.add_argument('--output-dir', type=Path, default=BASE/'output/phase-abc/block-overlays')
    parser.add_argument('--scale', type=float, default=3.0)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary = {}
    for pdf_path in sorted(args.input_dir.glob('*.pdf')):
        layout_path = args.layout_dir/pdf_path.stem/'seats.json'
        layout = json.loads(layout_path.read_text(encoding='utf-8'))
        counts = render(pdf_path, layout, args.output_dir/f'{pdf_path.stem}.png', args.scale)
        summary[pdf_path.stem] = {'seats': sum(counts.values()), 'unmatched': len(layout['unmatched']),
                                  'blocks': dict(sorted(counts.items()))}
    (args.output_dir/'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
