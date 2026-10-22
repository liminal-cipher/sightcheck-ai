"""Local shape detection + English Tesseract OCR, with explicit abstention."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw

BASE = Path(__file__).resolve().parent


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')


def components(mask):
    contours, _ = cv2.findContours(mask.astype('uint8')*255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return [(cv2.boundingRect(c), cv2.contourArea(c)) for c in contours]


def detect_shapes(rgb):
    """Estimate the modal neutral square size, then reject inconsistent shapes."""
    a = np.asarray(rgb).astype('int16')
    gray = cv2.cvtColor(a.astype('uint8'), cv2.COLOR_RGB2GRAY)
    neutral = (a.max(2)-a.min(2)<20) & (gray>70) & (gray<180)
    candidates = [(b,area) for b,area in components(neutral)
                  if 8 <= b[2] <= rgb.width*.05 and .7 <= b[2]/b[3] <= 1.35 and area/(b[2]*b[3])>.7]
    if not candidates:
        return [], [], [], {'status':'no_square_mode'}
    bins = Counter(round((b[2]+b[3])/4) for b,area in candidates)
    modal_size = bins.most_common(1)[0][0]*2
    size = float(np.median([b[2] for b,area in candidates if abs(b[2]-modal_size)<=4]))
    seats = [b for b,area in candidates if .8*size <= b[2] <= 1.2*size and .8*size <= b[3] <= 1.2*size]
    pale = (a[:,:,2]>a[:,:,0]+10) & (a[:,:,2]>a[:,:,1]+2) & (a[:,:,0]>150) & (a[:,:,2]>200)
    rows = [b for b,area in components(pale) if .7*size<b[2]<1.3*size and .7*size<b[3]<1.3*size and area/(b[2]*b[3])>.55]
    blue = (a[:,:,2]>a[:,:,0]+45) & (a[:,:,2]>a[:,:,1]+15) & (a[:,:,0]>30)
    special = [b for b,area in components(blue) if size*.65<b[2]<size*10
               and size*.65<b[3]<size*1.5 and area/(b[2]*b[3])>.5]
    seats.sort(key=lambda b:(b[1],b[0])); rows.sort(key=lambda b:(b[1],b[0]))
    return seats, rows, special, {'status':'ok','modal_cell_size_px':size,
                                'neutral_mask_threshold':[70,180],'channel_spread_max':20}


def make_mosaics(rgb, boxes, kind, destination):
    """Isolate white-on-gray digits from boxes; preserve row-letter polarity."""
    jobs, mappings = [], []
    tile, columns, chunk = 160, 10, 100
    for start in range(0,len(boxes),chunk):
        subset = boxes[start:start+chunk]
        canvas = Image.new('L',(columns*tile, ((len(subset)+columns-1)//columns)*tile),255)
        mapping = []
        for offset,(x,y,w,h) in enumerate(subset):
            inset = max(2,round(min(w,h)*.07))
            crop = np.array(rgb.crop((x+inset,y+inset,x+w-inset,y+h-inset)).convert('L'))
            if kind == 'numbers':
                crop = np.where(crop>195,0,255).astype('uint8')
            else:
                crop = np.where(crop<160,0,255).astype('uint8')
            crop = Image.fromarray(crop)
            crop.thumbnail((tile-40,tile-40))
            crop = crop.resize((min(tile-40,crop.width*3),min(tile-40,crop.height*3)))
            tx,ty = (offset%columns)*tile,(offset//columns)*tile
            canvas.paste(crop,(tx+(tile-crop.width)//2,ty+(tile-crop.height)//2))
            mapping.append({'index':start+offset,'tile':[tx,ty,tx+tile,ty+tile]})
        image_path = destination/f'{kind}-{start:04}.png'
        output_path = destination/f'{kind}-{start:04}.json'
        canvas.save(image_path)
        jobs.append({'image':str(image_path),'output':str(output_path),'kind':kind,'tiles':mapping})
        mappings.append((output_path,mapping))
    return jobs,mappings


def read_mosaics(mappings):
    found = {}
    for path,mapping in mappings:
        words = json.loads(path.read_text())['words']
        for entry in mapping:
            x0,y0,x1,y1 = entry['tile']
            hits = [w for w in words if x0 <= (w['bbox']['x0']+w['bbox']['x1'])/2 < x1
                    and y0 <= (w['bbox']['y0']+w['bbox']['y1'])/2 < y1]
            found[entry['index']] = {'text':' '.join(w['text'] for w in hits),
                                    'confidence':min((w['confidence'] for w in hits),default=0),
                                    'word_count':len(hits)}
    return found


def assign_identity(box, number, rows, zones, size):
    """Do not infer row names from row order or missing OCR characters."""
    x,y,w,h = box
    cx,cy = x+w/2,y+h/2
    box_zones = [z for z in zones if z['text'].startswith('BOX') and z.get('region_px') and
                 z['region_px'][0]<=cx<=z['region_px'][2] and z['region_px'][1]<=cy<=z['region_px'][3]]
    if len(box_zones)==1:
        return {'block':box_zones[0]['text'],'row':None,'number':number,
                'seat_id':f"{box_zones[0]['text']}:{number}", 'reason':None}
    letters = {r['text'] for r in rows if abs(cy-r['center_px'][1])<size*.55 and r['confidence']>=60
               and re.fullmatch('[A-Z]',r['text'])}
    # A single row marker could label a nearby unrelated zone: require two sides.
    if len(letters)==1 and sum(abs(cy-r['center_px'][1])<size*.55 and r['text'] in letters and r['confidence']>=60 for r in rows)>=2:
        letter = next(iter(letters))
        return {'block':'main','row':letter,'number':number,'seat_id':f'main:{letter}-{number}','reason':None}
    return {'block':None,'row':None,'number':number,'seat_id':None,
            'reason':'conflicting_row_labels' if len(letters)>1 else 'row_or_zone_unresolved'}


def bound_box_zones(zones, boxes, size):
    """Stop a BOX column at the first large vertical gap, before another floor."""
    for zone in zones:
        if not zone['text'].startswith('BOX'):
            continue
        center = (zone['bbox']['x0']+zone['bbox']['x1'])/2
        column = sorted((b for b in boxes if abs(b[0]+b[2]/2-center)<size*.6
                         and b[1]>zone['bbox']['y1']),key=lambda b:b[1])
        run = []
        previous = zone['bbox']['y1']
        for box in column:
            if box[1]-previous>size*1.8:
                break
            run.append(box)
            previous = box[1]+box[3]
        if run:
            zone['region_px'] = [min(b[0] for b in run),run[0][1],
                                 max(b[0]+b[2] for b in run),previous]
    return zones


def gap_candidates(seats, size):
    """Flag one-cell holes only; holes may be deliberate and are never seats."""
    groups = []
    for seat in sorted(seats,key=lambda s:s['center_px'][1]):
        group = next((g for g in groups if abs(g[0]['center_px'][1]-seat['center_px'][1])<size*.4),None)
        if group is None:
            groups.append([seat])
        else:
            group.append(seat)
    gaps = []
    for group in groups:
        ordered = sorted(group,key=lambda s:s['center_px'][0])
        for a,b in zip(ordered,ordered[1:]):
            dx = b['center_px'][0]-a['center_px'][0]
            if 1.7*size < dx < 2.5*size:
                gaps.append({'center_px':[(a['center_px'][0]+b['center_px'][0])/2,
                                          (a['center_px'][1]+b['center_px'][1])/2],
                             'reason':'possible_missing_shape_or_intentional_gap','is_seat':False})
    return gaps


def run(source, destination):
    destination = destination.resolve(); destination.mkdir(parents=True,exist_ok=True)
    with Image.open(source) as image:
        metadata = {'format':image.format,'source_mode':image.mode,'size_px':list(image.size),
                    'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
        rgb = image.convert('RGB')
    rgb.save(destination/'rgb.png')
    boxes,row_boxes,special,parameters = detect_shapes(rgb)
    write_json(destination/'shape-detection.json',{'boxes_xywh_px':boxes,'row_marker_boxes_xywh_px':row_boxes,
                                                  'blue_region_boxes_xywh_px':special,'parameters':parameters})
    jobs,number_maps = make_mosaics(rgb,boxes,'numbers',destination)
    row_jobs,row_maps = make_mosaics(rgb,row_boxes,'letters',destination)
    jobs.extend(row_jobs)
    jobs.append({'image':str(destination/'rgb.png'),'output':str(destination/'page-ocr.json'),'kind':'page'})
    write_json(destination/'ocr-jobs.json',jobs)
    subprocess.run(['node',str(BASE/'local-ocr.mjs'),str(destination/'ocr-jobs.json')],check=True,cwd=BASE.parent.parent)
    numbers, row_text = read_mosaics(number_maps), read_mosaics(row_maps)
    rows = [{'bbox_px':[x,y,x+w,y+h],'center_px':[x+w/2,y+h/2],**row_text[i]}
            for i,(x,y,w,h) in enumerate(row_boxes)]
    page_words = json.loads((destination/'page-ocr.json').read_text())['words']
    zones = [{**w,'text':w['text'].replace('BOX','BOX-').replace('--','-')}
             for w in page_words if re.fullmatch(r'BOX-?\d+|OP',w['text']) and w['confidence']>=60]
    seats = []
    size = parameters.get('modal_cell_size_px',1)
    bound_box_zones(zones,boxes,size)
    for i,box in enumerate(boxes):
        x,y,w,h = box; ocr = numbers[i]
        valid = re.fullmatch(r'\d{1,3}',ocr['text']) and ocr['confidence']>=60 and ocr['word_count']==1
        identity = assign_identity(box,int(ocr['text']),rows,zones,size) if valid else {
            'block':None,'row':None,'number':None,'seat_id':None,'reason':'number_ocr_uncertain'}
        seats.append({'candidate_id':f'shape-{i:04}', 'kind':'regular_seat_shape_candidate',
                      'bbox_px':[x,y,x+w,y+h],'center_px':[x+w/2,y+h/2], 'ocr':ocr,
                      **identity,'review_status':'unreviewed'})
    duplicates = {k for k,v in Counter(s['seat_id'] for s in seats if s['seat_id']).items() if v>1}
    for seat in seats:
        if seat['seat_id'] in duplicates:
            seat['proposed_duplicate_id'] = seat['seat_id']
            seat['seat_id'] = None
            seat['reason'] = 'duplicate_identity'
    accessibility = [{'candidate_id':f'blue-region-{i:03}','kind':'accessibility_or_blue_region',
                      'bbox_px':[x,y,x+w,y+h], 'center_px':[x+w/2,y+h/2],
                      'seat_count':None,'review_status':'unreviewed',
                      'reason':'region_not_individual_wheelchair_seat',
                      'ocr_words':[word for word in page_words if x<=(word['bbox']['x0']+word['bbox']['x1'])/2<=x+w
                                   and y<=(word['bbox']['y0']+word['bbox']['y1'])/2<=y+h]}
                     for i,(x,y,w,h) in enumerate(special)]
    gaps = gap_candidates(seats,size)
    overlay = rgb.copy(); draw = ImageDraw.Draw(overlay)
    for seat in seats:
        color = '#d500f9' if seat['reason']=='duplicate_identity' else '#00aa44' if seat['seat_id'] else '#e33b00'
        draw.rectangle(seat['bbox_px'],outline=color,width=2)
    for region in accessibility:
        draw.rectangle(region['bbox_px'],outline='#0077ff',width=4)
    for gap in gaps:
        x,y = gap['center_px']; draw.ellipse((x-12,y-12,x+12,y+12),outline='#ff9900',width=3)
    overlay.save(destination/'overlay.png')
    with (destination/'seats.csv').open('w',newline='',encoding='utf-8') as stream:
        writer = csv.DictWriter(stream,fieldnames=['candidate_id','seat_id','block','row','number','x_px','y_px','ocr_text','confidence','reason'])
        writer.writeheader()
        for s in seats:
            writer.writerow({**{k:s[k] for k in ['candidate_id','seat_id','block','row','number','reason']},
                             'x_px':s['center_px'][0],'y_px':s['center_px'][1],
                             'ocr_text':s['ocr']['text'],'confidence':s['ocr']['confidence']})
    result = {'source_filename':source.name,**metadata,'parameters':parameters,
              'coordinate_system':'image pixels, top-left origin; no physical scale',
              'seats':seats,'row_markers':rows,'zone_labels':zones,'accessibility_regions':accessibility,
              'gap_candidates':gaps,'summary':{'shape_candidates':len(seats),
              'number_ocr_accepted':sum(s['number'] is not None for s in seats),
              'identity_candidates':sum(s['seat_id'] is not None for s in seats),
              'unmatched':sum(s['seat_id'] is None for s in seats),'duplicate_ids':sorted(duplicates),
              'blue_regions':len(accessibility),'gap_candidates':len(gaps),
              'reasons':dict(Counter(s['reason'] for s in seats if s['reason'])),
              'recognition_accuracy':None,'detection_recall':None,'needs_review':True}}
    write_json(destination/'seats.json',result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image',type=Path); parser.add_argument('--output-dir',type=Path,required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.image,args.output_dir)['summary']))
