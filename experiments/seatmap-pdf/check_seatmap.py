"""Flag seat readings that contradict the plan's own structure, without ground truth.

A seat map constrains itself: within a row the printed numbers run in order
along the row, one cell has one ID, every cell of a row sits on the same line,
row letters run in order down the page, and the legend states how many seats
exist. A misread digit or row letter usually breaks one of these rules, so a
reviewer only needs to look at the flagged cells.

Cell positions always come from the CV shape detection in
<theatre>/seats.json; only gray seat cells are checked, not blue wheelchair
regions. Readings come from one or more sources in priority order: a folder of
model readings (result-*.json, e.g. an API run), "ocr" (the OCR text in
seats.json), "labels", or a map-review export (*.json, from
make_map_review.py). The first source that has a reading for a cell wins.

For an unseen plan the primary source is a full model reading. "labels" here
means the experiment's human labels; in a review workflow the reviewer's
corrections take that place: pass the map-review export first and re-run.

--compare SOURCE reads a second, independent reader (normally "ocr") and flags
cells where both readers answered and disagree.

With --inject N the script also measures the structural checks: it plants N
realistic errors (look-alike digits, neighboring numbers, neighboring row
letters) one at a time and reports how many raise a flag on the planted cell.
The comparison reader is left out of this measurement.
"""
from collections import Counter, defaultdict
from pathlib import Path
import argparse
import json
import random
import re

from compare_readings import load_model
from score_readers import queue_truth

BASE = Path(__file__).resolve().parent
LOOKALIKES = {'6': '9', '9': '6', '1': '7', '7': '1', '3': '8', '8': '3', '5': '6', '0': '8'}
SEVERE = {'duplicate_id', 'out_of_order', 'adjacent_jump', 'row_misaligned', 'not_a_seat', 'row_letter_order',
          'reader_disagreement'}


def norm(reading):
    """Shared shape for every source: is_seat, zone, row, number (digits only)."""
    if reading is None:
        return None
    digits = re.findall(r'\d+', str(reading.get('number') or ''))
    return {'is_seat': reading.get('is_seat', 'yes'), 'zone': reading.get('zone') or reading.get('block'),
            'row': (reading.get('row') or '').strip().upper(), 'number': digits[0] if len(digits) == 1 else None}


def ocr_readings(seats):
    return {s['candidate_id']: norm({'zone': s['block'], 'row': s['row'], 'number': s['number']})
            for s in seats if s['seat_id']}


def label_readings(out):
    labels = {}
    for name in ('blind-review-result.json', 'blind2-review-result.json'):
        path = out/name
        if path.exists():
            for s in json.loads(path.read_text(encoding='utf-8'))['samples']:
                if s['label'].get('is_seat'):
                    labels[s['sample_id']] = s['label']
    path = out/'queue-review-result.json'
    if path.exists():
        for item in json.loads(path.read_text(encoding='utf-8'))['items']:
            truth = queue_truth(item)
            if truth is not None:
                labels.setdefault(item['sample_id'], truth)
    return labels


def correction_readings(path):
    """Reviewed cells from a map-review export (same sample/label layout as the blind pages)."""
    samples = json.loads(path.read_text(encoding='utf-8'))['samples']
    return {s['sample_id']: s['label'] for s in samples
            if s.get('label', {}).get('status') == 'reviewed' and s['label'].get('is_seat')}


def collect(out, theatre, sources, seats):
    """Merge sources for one theatre into {candidate_id: reading}, recording which source won."""
    merged, origin = {}, {}
    for source in sources:
        if source == 'ocr':
            found = ocr_readings(seats)
        else:
            if source == 'labels':
                raw = label_readings(out)
            elif source.endswith('.json'):
                raw = correction_readings(out/source)
            else:
                raw = load_model(out/source)
            prefix = f'{theatre}--'
            found = {k[len(prefix):]: norm(v) for k, v in raw.items() if k.startswith(prefix)}
        for cid, reading in found.items():
            if cid not in merged and reading is not None:
                merged[cid], origin[cid] = reading, source
    return merged, origin


def longest_run(values):
    """Indices of the longest strictly increasing subsequence (patience sorting)."""
    tails, prev, idx = [], [None] * len(values), []
    for i, v in enumerate(values):
        lo, hi = 0, len(tails)
        while lo < hi:
            mid = (lo + hi) // 2
            if values[tails[mid]] < v:
                lo = mid + 1
            else:
                hi = mid
        prev[i] = tails[lo - 1] if lo else None
        if lo == len(tails):
            tails.append(i)
        else:
            tails[lo] = i
    i = tails[-1] if tails else None
    while i is not None:
        idx.append(i)
        i = prev[i]
    return set(idx)


def same(a, b):
    if a['is_seat'] != 'yes' or b['is_seat'] != 'yes':
        return a['is_seat'] == b['is_seat']
    return (a['zone'], a['row'], a['number']) == (b['zone'], b['row'], b['number'])


def check(seats, readings, cell, expect=None, compare=None):
    """Return {'flags': {candidate_id: [reasons]}, 'rows': [...], 'summary': {...}}.

    compare holds a second reader's answers for cells it read independently of
    the primary reading; a different answer flags reader_disagreement.
    """
    geometry = {s['candidate_id']: s['center_px'] for s in seats}
    flags = defaultdict(list)
    for cid, other in (compare or {}).items():
        if cid in geometry and cid in readings and not same(readings[cid], other):
            flags[cid].append('reader_disagreement')
    for cid in geometry:
        if cid not in readings:
            flags[cid].append('unread')
    seat_cells = {}
    for cid, r in readings.items():
        if cid not in geometry:
            continue
        if r['is_seat'] != 'yes':
            flags[cid].append('not_a_seat')
        elif r['number'] is None or not r['zone']:
            flags[cid].append('incomplete')
        else:
            seat_cells[cid] = r
    ids = Counter((r['zone'], r['row'], r['number']) for r in seat_cells.values())
    groups = defaultdict(list)
    for cid, r in seat_cells.items():
        if ids[(r['zone'], r['row'], r['number'])] > 1:
            flags[cid].append('duplicate_id')
        groups[(r['zone'], r['row'])].append(cid)
    rows = []
    for (zone, row), cids in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        vertical = zone.startswith('BOX')
        along, across = (1, 0) if vertical else (0, 1)
        cids.sort(key=lambda c: geometry[c][along])
        line = sorted(geometry[c][across] for c in cids)[len(cids) // 2]
        for c in cids:
            if abs(geometry[c][across] - line) > cell * 0.5:
                flags[c].append('row_misaligned')
        numbers = [int(seat_cells[c]['number']) for c in cids]
        # Touching cells usually differ by the row's usual step (1, or 2 where odd and even sides split).
        touching = [(a, b) for a, b in zip(range(len(cids)), range(1, len(cids)))
                    if geometry[cids[b]][along] - geometry[cids[a]][along] < cell * 1.5]
        steps = Counter(abs(numbers[b] - numbers[a]) for a, b in touching)
        if steps:
            step = steps.most_common(1)[0][0]
            for a, b in touching:
                if abs(numbers[b] - numbers[a]) != step:
                    flags[cids[a]].append('adjacent_jump')
                    flags[cids[b]].append('adjacent_jump')
        forward, backward = longest_run(numbers), longest_run([-n for n in numbers])
        keep = forward if len(forward) >= len(backward) else backward
        for i, c in enumerate(cids):
            if i not in keep:
                flags[c].append('out_of_order')
        kept = sorted(numbers[i] for i in keep)
        missing = sorted(set(range(kept[0], kept[-1] + 1)) - set(kept)) if kept else []
        rows.append({'zone': zone, 'row': row, 'cells': len(cids), 'line_px': line,
                     'numbers': [numbers[i] for i in range(len(cids))], 'missing_numbers': missing})
    lettered = sorted((r for r in rows if r['zone'] == 'main' and re.fullmatch('[A-Z]', r['row'])),
                      key=lambda r: r['line_px'])
    letters = [r['row'] for r in lettered]
    keep = longest_run([ord(x) for x in letters])
    bad_rows = {letters[i] for i in range(len(letters)) if i not in keep}
    for cid, r in seat_cells.items():
        if r['zone'] == 'main' and r['row'] in bad_rows:
            flags[cid].append('row_letter_order')
    counts = {'cells': len(geometry), 'read_as_seat': len(seat_cells),
              'by_zone': dict(Counter(r['zone'] for r in seat_cells.values()))}
    mismatches = []
    for key, value in (expect or {}).items():
        actual = counts['read_as_seat'] if key == 'total' else counts['by_zone'].get(key, 0)
        if actual != value:
            mismatches.append({'key': key, 'expected': value, 'actual': actual})
    flagged = {c: f for c, f in flags.items() if f}
    summary = {'cells': len(geometry), 'read': len(readings), 'read_as_seat': len(seat_cells),
               'flagged_cells': len(flagged),
               'severe_cells': sum(bool(SEVERE & set(f)) for f in flagged.values()),
               'by_reason': dict(Counter(x for f in flagged.values() for x in f)),
               'rows_with_missing_numbers': sum(bool(r['missing_numbers']) for r in rows),
               'count_mismatches': mismatches}
    return {'flags': flagged, 'rows': rows, 'counts': counts, 'summary': summary}


def plant(readings, rng, all_rows, cells):
    """Return (cid, kind, corrupted copy) for one realistic misreading of a random checked seat cell."""
    seat_ids = sorted(c for c, r in readings.items() if c in cells and r['is_seat'] == 'yes' and r['number'])
    while True:
        cid = rng.choice(seat_ids)
        r = dict(readings[cid])
        kind = rng.choice(['lookalike_digit', 'neighbor_number', 'neighbor_row'])
        if kind == 'lookalike_digit':
            spots = [i for i, ch in enumerate(r['number']) if ch in LOOKALIKES]
            if not spots:
                continue
            i = rng.choice(spots)
            r['number'] = r['number'][:i] + LOOKALIKES[r['number'][i]] + r['number'][i + 1:]
        elif kind == 'neighbor_number':
            r['number'] = str(int(r['number']) + rng.choice([-1, 1]))
            if r['number'] == '0':
                continue
        else:
            if r['zone'] != 'main' or r['row'] not in all_rows:
                continue
            i = all_rows.index(r['row'])
            options = [all_rows[j] for j in (i - 1, i + 1) if 0 <= j < len(all_rows)]
            r['row'] = rng.choice(options)
        copy = dict(readings)
        copy[cid] = r
        return cid, kind, copy


def measure(seats, readings, cell, n, seed):
    """Plant n single errors, one at a time, and count which ones raise a severe flag on that cell."""
    rng = random.Random(seed)
    base = check(seats, readings, cell)['flags']
    rows = sorted({r['row'] for r in readings.values() if r['zone'] == 'main' and re.fullmatch('[A-Z]', r['row'])})
    caught, by_kind = 0, defaultdict(lambda: [0, 0])
    for _ in range(n):
        cid, kind, copy = plant(readings, rng, rows, {s['candidate_id'] for s in seats})
        new = set(check(seats, copy, cell)['flags'].get(cid, [])) - set(base.get(cid, []))
        hit = bool(new & SEVERE)
        caught += hit
        by_kind[kind][0] += hit
        by_kind[kind][1] += 1
    return {'planted': n, 'caught': caught, 'by_kind': {k: {'caught': v[0], 'planted': v[1]} for k, v in by_kind.items()}}


def parse_expect(pairs):
    expect = defaultdict(dict)
    for pair in pairs or []:
        theatre, rest = pair.split(':', 1)
        key, value = rest.split('=', 1)
        expect[theatre][key] = int(value)
    return expect


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output-dir', type=Path, default=BASE/'output/phase-abc')
    parser.add_argument('--theatre', action='append', help='Theatre folder; default: theatre-2 and theatre-3')
    parser.add_argument('--source', action='append',
                        help='"labels", "ocr" or a reading folder; repeatable, first wins (default: ocr)')
    parser.add_argument('--compare', help='Second reader to cross-check, normally "ocr"')
    parser.add_argument('--expect', action='append', metavar='THEATRE:KEY=N',
                        help='Legend count, e.g. theatre-2:total=506 or theatre-2:OP=40 (gray seat cells only)')
    parser.add_argument('--inject', type=int, default=0, help='Plant this many errors to measure the checks')
    parser.add_argument('--seed', type=int, default=20261116)
    parser.add_argument('--name', default='structure-check', help='Output file stem')
    args = parser.parse_args()
    out, sources = args.output_dir, args.source or ['ocr']
    expect = parse_expect(args.expect)
    report = {'sources': sources, 'compare': args.compare, 'theatres': {}}
    for theatre in args.theatre or ['theatre-2', 'theatre-3']:
        data = json.loads((out/theatre/'seats.json').read_text(encoding='utf-8'))
        seats, cell = data['seats'], data['parameters']['modal_cell_size_px']
        readings, origin = collect(out, theatre, sources, seats)
        compare = None
        if args.compare:
            second, _ = collect(out, theatre, [args.compare], seats)
            compare = {c: r for c, r in second.items() if origin.get(c) != args.compare}
        result = check(seats, readings, cell, expect.get(theatre), compare)
        result['summary']['readings_by_source'] = dict(Counter(origin.values()))
        if compare is not None:
            result['summary']['compared_cells'] = sum(c in readings for c in compare)
        if args.inject:
            result['injection'] = measure(seats, readings, cell, args.inject, args.seed)
        report['theatres'][theatre] = result
        s = result['summary']
        print(f"{theatre}: {s['read_as_seat']}/{s['cells']} cells read as seats, {s['flagged_cells']} flagged "
              f"({s['severe_cells']} severe) {s['by_reason']}; count mismatches {s['count_mismatches']}")
        if args.inject:
            m = result['injection']
            print(f"  planted errors caught: {m['caught']}/{m['planted']} {m['by_kind']}")
    (out/f'{args.name}.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
