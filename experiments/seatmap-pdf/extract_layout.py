"""Conservative vector-boundary matching; original extract_seats is preserved."""
from collections import Counter
from pathlib import Path
import argparse
import json

import fitz
from extract_seats import BLOCK_PATTERN, SEAT_PATTERN, REPORTED_COUNT_PATTERN, render_preview


def connected_rules(page):
    """Connect thin vector rectangles/lines by contact, not by seat numbering."""
    rules = []
    for drawing in page.get_drawings():
        for item in drawing['items']:
            if item[0] == 're':
                r = fitz.Rect(item[1])
                if min(r.width, r.height) > 3:
                    rules.extend([fitz.Rect(r.x0, r.y0, r.x1, r.y0),
                                  fitz.Rect(r.x0, r.y1, r.x1, r.y1),
                                  fitz.Rect(r.x0, r.y0, r.x0, r.y1),
                                  fitz.Rect(r.x1, r.y0, r.x1, r.y1)])
                else:
                    rules.append(r)
            elif item[0] == 'l':
                a, b = item[1:3]
                rules.append(fitz.Rect(min(a.x,b.x), min(a.y,b.y), max(a.x,b.x), max(a.y,b.y)))
    rules = [r for r in rules if min(r.width,r.height) <= 3 and max(r.width,r.height) >= 5]
    groups = []
    for r in rules:
        hits = [i for i,g in enumerate(groups) if any(
            r.x0 <= s.x1+1 and r.x1 >= s.x0-1 and r.y0 <= s.y1+1 and r.y1 >= s.y0-1 for s in g)]
        group = [r]
        for i in reversed(hits):
            group.extend(groups.pop(i))
        groups.append(group)
    return groups


def find_regions(page):
    groups = connected_rules(page)
    regions, errors = [], []
    labels = []
    for block in page.get_text('dict')['blocks']:
        for line in block.get('lines', []):
            for span in line['spans']:
                label = span['text'].strip()
                if BLOCK_PATTERN.fullmatch(label) or label == 'FOH\uc11d':
                    labels.append((label, fitz.Rect(span['bbox']), line['dir']))
    for label, box, direction in labels:
        horizontal = abs(direction[0]) > .9
        if not horizontal and abs(direction[1]) < .9:
            errors.append({'header':label, 'reason':'unsupported_oblique_label'})
            continue
        cx, cy = (box.x0+box.x1)/2, (box.y0+box.y1)/2
        thickness = box.height if horizontal else box.width
        candidates = []
        for index, group in enumerate(groups):
            for r in group:
                if horizontal and r.width > r.height and r.x0 <= cx <= r.x1:
                    distance = max(r.y0-box.y1, box.y0-r.y1, 0)
                elif not horizontal and r.height > r.width and r.y0 <= cy <= r.y1:
                    distance = max(r.x0-box.x1, box.x0-r.x1, 0)
                else:
                    continue
                if distance <= thickness * 1.5:
                    candidates.append((distance,index,r))
        if not candidates:
            errors.append({'header':label, 'reason':'adjacent_vector_boundary_not_found'})
            continue
        candidates.sort(key=lambda x:(x[0],-max(x[2].width,x[2].height)))
        distance, index, rule = candidates[0]
        if any(i != index and abs(d-distance)<.5 for d,i,r in candidates[1:]):
            errors.append({'header':label,'reason':'ambiguous_boundary'})
            continue
        group = groups[index]
        extent = fitz.Rect(min(r.x0 for r in group),min(r.y0 for r in group),
                           max(r.x1 for r in group),max(r.y1 for r in group))
        if horizontal:
            extent.x0, extent.x1 = rule.x0, rule.x1
        else:
            extent.y0, extent.y1 = rule.y0, rule.y1
        evidence = 'connected_vector_grid'
        if min(extent.width, extent.height) <= 3:
            evidence = 'bounded_border_only'
            if horizontal and cy < rule.y0:
                extent.y1 += thickness * 3
            else:
                errors.append({'header':label,'reason':'insufficient_boundary_geometry'})
                continue
        regions.append({'block':label[0] if BLOCK_PATTERN.fullmatch(label) else 'FOH',
                        'bbox_pt':list(extent), 'label_bbox_pt':list(box),
                        'text_direction':list(direction), 'boundary_pt':list(rule),
                        'evidence':evidence})
    return regions, errors


def extract(pdf_path):
    pdf_path = Path(pdf_path)
    with fitz.open(pdf_path) as doc:
        if len(doc) != 1:
            raise ValueError(f'Expected a one-page plan, found {len(doc)} pages')
        page = doc[0]
        regions, errors = find_regions(page)
        words = [w for w in page.get_text('words') if SEAT_PATTERN.fullmatch(w[4])]
        seats, unmatched = [], []
        for word in words:
            point = [(word[0]+word[2])/2, (word[1]+word[3])/2]
            matches = [r for r in regions if fitz.Point(*point) in fitz.Rect(r['bbox_pt'])]
            if len(matches) != 1:
                unmatched.append({'text':word[4], 'bbox_pt':list(word[:4]),
                                  'reason':'block_ambiguous' if matches else 'no_vector_region'})
                continue
            region = matches[0]
            match = SEAT_PATTERN.fullmatch(word[4])
            row, number = int(match['row']), int(match['number'])
            seats.append({'seat_id':f"{region['block']}:{row}-{number}", 'block':region['block'],
                          'row':row, 'number':number, 'label':word[4], 'text_bbox_pt':list(word[:4]),
                          'text_center_pt':point, 'review_status':'unreviewed', 'evidence':region['evidence']})
        duplicates = sorted(k for k,v in Counter(s['seat_id'] for s in seats).items() if v>1)
        for seat in seats[:]:
            if seat['seat_id'] in duplicates:
                seats.remove(seat)
                unmatched.append({'text':seat['label'],'bbox_pt':seat['text_bbox_pt'], 'reason':'duplicate_identity'})
        reported_match = REPORTED_COUNT_PATTERN.search(page.get_text())
        reported = int(reported_match[1]) if reported_match else None
        return {'source_filename':pdf_path.name,'page_count':1,'page_size_pt':list(page.rect[2:]),
                'coordinate_system':'PDF text centers in page points; not physical seat centers or meters',
                'block_regions':regions,'header_errors':errors,'duplicate_ids':duplicates,
                'seats':sorted(seats,key=lambda s:(s['block'],s['row'],s['number'])), 'unmatched':unmatched,
                'summary':{'seat_tokens':len(words),'matched':len(seats),'unmatched':len(unmatched),
                           'duplicate_id_count':len(duplicates),'reported_seat_count':reported,
                           'token_count_equals_reported':reported == len(words), 'needs_review':True,
                           'recognition_accuracy':None,
                           'automatic_checks_passed':bool(regions) and not errors and not unmatched
                           and not duplicates and reported == len(seats)}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf',type=Path)
    parser.add_argument('--output-dir',type=Path,required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    result = extract(args.pdf)
    (args.output_dir/'seats.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    render_preview(args.pdf,result,args.output_dir/'overlay.png')
    print(json.dumps(result['summary']))
