"""Run improved extraction and review preparation without repeating the saved baseline."""
import argparse
from collections import defaultdict, Counter
import csv
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import platform

import cv2
import fitz
import numpy as np
from PIL import Image, ImageDraw, __version__ as pillow_version

from extract_layout import extract
from image_baseline import run as run_image, write_json
from evaluate_review import evaluate

BASE = Path(__file__).resolve().parent


def key(seat):
    return (seat['seat_id'],tuple(round(v,3) for v in seat['text_center_pt']))


def representative_indices(items):
    """Cover all four spatial extremes plus a central candidate, deterministically."""
    if not items:
        return []
    cx = sum(s['center'][0] for s in items)/len(items)
    cy = sum(s['center'][1] for s in items)/len(items)
    indices = {min(range(len(items)),key=lambda i:(items[i]['center'][0]-cx)**2+(items[i]['center'][1]-cy)**2)}
    for axis in [0,1]:
        indices.add(min(range(len(items)),key=lambda i:items[i]['center'][axis]))
        indices.add(max(range(len(items)),key=lambda i:items[i]['center'][axis]))
    # Corners catch partial last rows that a simple min/max can miss.
    for sx,sy in [(-1,-1),(-1,1),(1,-1),(1,1)]:
        indices.add(max(range(len(items)),key=lambda i:sx*items[i]['center'][0]+sy*items[i]['center'][1]))
    return sorted(indices)


def sample_document(name, candidates, image, scale, output, samples, unit, source_hash):
    groups = defaultdict(list)
    for candidate in candidates:
        groups[candidate['stratum']].append(candidate)
    chosen = {}
    for group in groups.values():
        for index in representative_indices(group):
            candidate = group[index]
            chosen[candidate['candidate_id']] = candidate
    for candidate in chosen.values():
        sample_id = f"{name}--{candidate['candidate_id']}"
        box = candidate['bbox']
        padding = 48 if unit=='pt' else 100
        bounds = [max(0,int((box[0]-padding)*scale)),max(0,int((box[1]-padding)*scale)),
                  min(image.width,int((box[2]+padding)*scale)),min(image.height,int((box[3]+padding)*scale))]
        crop = image.crop(bounds)
        draw = ImageDraw.Draw(crop)
        draw.rectangle([box[0]*scale-bounds[0],box[1]*scale-bounds[1],
                        box[2]*scale-bounds[0],box[3]*scale-bounds[1]],outline='#ff3300',width=2)
        relative = f'review-crops/{sample_id}.png'
        crop.save(output/relative)
        samples.append({'sample_id':sample_id,'document':name,'source_sha256':source_hash,
                        'unit':unit,'position_anchor':'text_center' if unit=='pt' else 'shape_center',
                        'shape_detection_attempted':candidate['kind']=='regular_seat_shape_candidate',
                        'stratum':candidate['stratum'],'kind':candidate['kind'],
                        'crop':relative,'crop_origin':[bounds[0]/scale,bounds[1]/scale],
                        'render_scale':scale,'prediction':candidate,
                        'review':{'status':'pending','shape_correct':None,'text_correct':None,
                                  'identity_correct':None,'expected_center':None,'correction':None,'notes':''}})


def write_review_ui(output, review):
    payload = json.dumps(review).replace('<','\\u003c')
    template = '''<!doctype html><meta charset="utf-8"><title>Seat map manual review</title>
<style>body{font:16px system-ui;max-width:1200px;margin:24px auto}button,select,input{padding:8px;margin:5px}img{max-width:100%;cursor:crosshair;border:1px solid #bbb}pre{white-space:pre-wrap}label{display:block}textarea{width:90%;height:65px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}</style>
<h1>Manual review — unreviewed accuracy is unmeasured</h1>
<p>Red box = candidate. Click the intended center to record position in original page points or pixels.
PDF anchors are text centers; individual PDF seat shapes were not detected. Blue regions are not individual wheelchair seats.
Leave unsupported fields blank. Purposive samples cannot establish full-map recall.</p>
<button id="prev">Previous</button><button id="next">Next</button><select id="pick"></select>
<button id="export">Export review JSON</button><label>Resume exported review <input id="import" type="file" accept=".json"></label>
<div class="grid"><div><img id="crop"><pre id="info"></pre></div><div>
<label>Status <select id="status"><option>pending</option><option>reviewed</option><option>uncertain</option></select></label>
<label>Shape detection correct <select id="shape_correct"></select></label>
<label>Seat text correct <select id="text_correct"></select></label>
<label>Block/row/number connection correct <select id="identity_correct"></select></label>
<p>Corrections (optional; keep canonical labels visible in the source):</p>
<label>Block <input id="block"></label><label>Row <input id="row"></label><label>Number <input id="number"></label><label>Text <input id="text"></label>
<label>Notes <textarea id="notes"></textarea></label><button id="clear">Clear position annotation</button>
<p id="position"></p></div></div>
<h2>Missed objects</h2><p>Add independently observed missed seats below, with document, kind, center, unit and notes. This is an issue inventory, not a recall denominator. Inspect the full overlay linked in the report as well as candidate crops.</p>
<textarea id="missed" placeholder="[]"></textarea><p id="error" role="alert"></p>
<script>
let data = __DATA__, index=0;
const $=id=>document.getElementById(id);
for(const f of ['shape_correct','text_correct','identity_correct']) $(''+f).innerHTML='<option value="">Unmeasured / not applicable</option><option value="true">Yes</option><option value="false">No</option>';
function save(){let r=data.samples[index].review;r.status=$('status').value;for(const f of ['shape_correct','text_correct','identity_correct'])r[f]=$(f).value===''?null:$(f).value==='true';r.notes=$('notes').value;const c={};for(const f of ['block','row','number','text'])if($(f).value!=='')c[f]=$(f).value;r.correction=Object.keys(c).length?c:null;}
function show(){const s=data.samples[index],r=s.review;$('pick').value=index;$('crop').src=s.crop;$('info').textContent=JSON.stringify({sample:s.sample_id,stratum:s.stratum,unit:s.unit,anchor:s.position_anchor,prediction:s.prediction},null,2);$('status').value=r.status;for(const f of ['shape_correct','text_correct','identity_correct'])$(f).value=r[f]===null?'':String(r[f]);$('shape_correct').disabled=!s.shape_detection_attempted;for(const f of ['block','row','number','text'])$(f).value=r.correction?.[f]??'';$('notes').value=r.notes;$('position').textContent='Expected center: '+JSON.stringify(r.expected_center);}
function populate(){$('pick').innerHTML='';data.samples.forEach((s,i)=>{const o=document.createElement('option');o.value=i;o.textContent=`${i+1}. ${s.sample_id}`;$('pick').append(o)});$('missed').value=JSON.stringify(data.missed_objects??[],null,2);show();}
$('next').onclick=()=>{save();index=Math.min(index+1,data.samples.length-1);show()};$('prev').onclick=()=>{save();index=Math.max(index-1,0);show()};$('pick').onchange=e=>{save();index=Number(e.target.value);show()};
$('crop').onclick=e=>{save();const s=data.samples[index],r=e.target.getBoundingClientRect();s.review.expected_center=[s.crop_origin[0]+(e.clientX-r.left)*e.target.naturalWidth/r.width/s.render_scale,s.crop_origin[1]+(e.clientY-r.top)*e.target.naturalHeight/r.height/s.render_scale];show()};$('clear').onclick=()=>{save();data.samples[index].review.expected_center=null;show()};
$('export').onclick=()=>{save();try{data.missed_objects=JSON.parse($('missed').value);if(!Array.isArray(data.missed_objects))throw Error('Missed objects must be an array');const a=document.createElement('a'),u=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));a.href=u;a.download='review-completed.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);$('error').textContent=''}catch(e){$('error').textContent=e.message}};
$('import').onchange=async e=>{try{const incoming=JSON.parse(await e.target.files[0].text());if(incoming.schema_version!==1||incoming.samples.length!==data.samples.length)throw Error('Review template does not match');const lookup=new Map(incoming.samples.map(s=>[s.sample_id,s]));for(const s of data.samples){const prior=lookup.get(s.sample_id);if(!prior||prior.source_sha256!==s.source_sha256)throw Error('Source mismatch');}for(const s of data.samples)s.review=lookup.get(s.sample_id).review;data.missed_objects=incoming.missed_objects??[];populate();$('error').textContent=''}catch(e){$('error').textContent=e.message}};
populate();
</script>'''
    (output/'review.html').write_text(template.replace('__DATA__',payload),encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=BASE/'output/phase-abc')
    parser.add_argument('--skip-images',action='store_true',help='Rebuild report from existing image baseline results')
    args = parser.parse_args(); output = args.output_dir.resolve()
    prior_dir = BASE/'output/acc-audit'
    if output == prior_dir.resolve() or prior_dir.resolve() in output.parents:
        parser.error('Use a separate output directory; acc-audit is the preserved baseline')
    output.mkdir(parents=True,exist_ok=True); (output/'review-crops').mkdir(exist_ok=True)
    prior = json.loads((prior_dir/'summary.json').read_text(encoding='utf-8'))
    old_rows = {r['file']:r for r in prior['pdf_results']}
    samples, comparisons, images = [], [], []
    for pdf in sorted((BASE/'input/theatre-1').glob('*.pdf')):
        destination = output/'theatre-1'/pdf.stem; destination.mkdir(parents=True,exist_ok=True)
        result = extract(pdf)
        old = json.loads((prior_dir/'theatre-1'/pdf.stem/'seats.json').read_text(encoding='utf-8'))
        retained = {key(s) for s in old['seats']} <= {key(s) for s in result['seats']}
        if not retained:
            raise AssertionError(f'Previously assigned identities changed: {pdf.name}')
        sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
        result['source_sha256'] = sha
        write_json(destination/'seats.json',result)
        with fitz.open(pdf) as doc:
            page = doc[0]
            page.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False).save(destination/'page.png')
            for region in result['block_regions']:
                page.draw_rect(region['bbox_pt'],color=(0,.5,.9),width=.6)
                b = fitz.Rect(region['label_bbox_pt']); page.draw_rect(b,color=(.8,0,.8),width=.6)
            for seat in result['seats']:
                page.draw_rect(seat['text_bbox_pt'],color=(0,.7,.2),width=.3)
            for seat in result['unmatched']:
                page.draw_rect(seat['bbox_pt'],color=(1,0,0),width=1)
            page.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False).save(destination/'overlay.png')
        with (destination/'seats.csv').open('w',encoding='utf-8',newline='') as stream:
            writer = csv.writer(stream); writer.writerow(['seat_id','block','row','number','text_x_pt','text_y_pt','review_status'])
            for s in result['seats']:
                writer.writerow([s['seat_id'],s['block'],s['row'],s['number'],*s['text_center_pt'],'unreviewed'])
        comparison = {'file':pdf.name,'before_matched':old_rows[pdf.name]['matched'],
                      'before_unmatched':old_rows[pdf.name]['unmatched'],
                      'after_matched':result['summary']['matched'],'after_unmatched':result['summary']['unmatched'],
                      'previous_identities_preserved':retained,'automatic_checks_passed':result['summary']['automatic_checks_passed'],
                      'recognition_accuracy':None,'block_counts':dict(Counter(s['block'] for s in result['seats']))}
        comparisons.append(comparison)
        candidates = [{'candidate_id':s['seat_id'].replace(':','-'),'center':s['text_center_pt'],
                       'bbox':s['text_bbox_pt'],'seat_id':s['seat_id'],'block':s['block'],'row':s['row'],
                       'number':s['number'],'text':s['label'],'kind':'pdf_text_token',
                       'stratum':f"block-{s['block']}",'previously_unmatched':key(s) not in {key(v) for v in old['seats']}}
                      for s in result['seats']]
        candidates.extend({'candidate_id':f'unmatched-{i}','center':[(s['bbox_pt'][0]+s['bbox_pt'][2])/2,(s['bbox_pt'][1]+s['bbox_pt'][3])/2],
                           'bbox':s['bbox_pt'],'seat_id':None,'text':s['text'],'kind':'pdf_text_token','stratum':s['reason']}
                          for i,s in enumerate(result['unmatched']))
        with Image.open(destination/'page.png') as page_image:
            sample_document(pdf.stem,candidates,page_image,2,output,samples,'pt',sha)
    for theatre in ['theatre-2','theatre-3']:
        source, = (BASE/'input'/theatre).glob('*.jpg')
        destination = output/theatre
        result = json.loads((destination/'seats.json').read_text()) if args.skip_images else run_image(source,destination)
        images.append({'file':source.name,**result['summary'],'size_px':result['size_px'],'source_mode':result['source_mode']})
        candidates = []
        size = result['parameters']['modal_cell_size_px']
        bands = []
        for seat in sorted(result['seats'],key=lambda s:s['center_px'][1]):
            y = seat['center_px'][1]
            band = next((i for i,v in enumerate(bands) if abs(y-v)<size*.4),None)
            if band is None:
                band = len(bands); bands.append(y)
            candidates.append({'candidate_id':seat['candidate_id'],'center':seat['center_px'],'bbox':seat['bbox_px'],
                               'seat_id':seat['seat_id'],'block':seat['block'],'row':seat['row'],'number':seat['number'],
                               'text':seat['ocr']['text'],'kind':seat['kind'], 'reason':seat['reason'],
                               'stratum':f"band-{band}-{seat['reason'] or seat['block']}"})
        for region in result['accessibility_regions']:
            candidates.append({'candidate_id':region['candidate_id'],'center':region['center_px'],'bbox':region['bbox_px'],
                               'seat_id':None,'text':None,'kind':region['kind'],'stratum':region['candidate_id'],
                               'reason':region['reason']})
        for i,gap in enumerate(result['gap_candidates']):
            x,y = gap['center_px']
            candidates.append({'candidate_id':f'gap-{i}','center':[x,y],'bbox':[x-10,y-10,x+10,y+10],
                               'seat_id':None,'text':None,'kind':'possible_missing_shape','stratum':'gaps'})
        with Image.open(destination/'rgb.png') as rgb:
            sample_document(theatre,candidates,rgb,1,output,samples,'px',result['source_sha256'])
    review = {'schema_version':1,'sampling':'Purposive block/band extremes, centers and problem strata; not random.',
              'samples':samples,'missed_objects':[]}
    write_json(output/'review-template.json',review)
    write_json(output/'evaluation.json',evaluate(review))
    write_review_ui(output,review)
    summary = {'executed_at_utc':datetime.now(timezone.utc).isoformat(),
               'environment':{'python':platform.python_version(),'pymupdf':fitz.VersionBind,'pillow':pillow_version,
                              'opencv':cv2.__version__,'numpy':np.__version__,'tesseract_js':'7.0.0'},
               'pdf_comparison':comparisons,'image_results':images,'manual_review_samples':len(samples),
               'recognition_accuracy':None,'baseline_source':'Existing output/acc-audit; not rerun',
               'legend_context':{'theatre-2':{'regular':466,'orchestra_pit':40,'wheelchair':6,'total':512},
                                 'theatre-3':{'regular':244,'wheelchair':4,'total':248}},
               'limits':['Legend numbers are contextual annotations, not per-seat ground truth.',
                         'Blue region count is not wheelchair seat count.',
                         'All source coordinates remain image pixels or PDF page points.']}
    write_json(output/'summary.json',summary)
    with (output/'pdf-comparison.csv').open('w',newline='',encoding='utf-8') as stream:
        fields = ['file','before_matched','before_unmatched','after_matched','after_unmatched','previous_identities_preserved','automatic_checks_passed','recognition_accuracy']
        writer = csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore'); writer.writeheader(); writer.writerows(comparisons)
    rows = ''.join(f"<tr><td>{r['file']}</td><td>{r['before_matched']}</td><td>{r['before_unmatched']}</td><td>{r['after_matched']}</td><td>{r['after_unmatched']}</td><td>{r['previous_identities_preserved']}</td></tr>" for r in comparisons)
    report = ['<!doctype html><meta charset="utf-8"><title>ACC phase A–C experiment</title><style>body{font:16px system-ui;max-width:1150px;margin:30px auto}table{border-collapse:collapse}td,th{border:1px solid #aaa;padding:8px}img{max-width:100%}pre{white-space:pre-wrap}</style>',
              '<h1>ACC seat maps: geometry and local OCR</h1><p>Recognition accuracy: <b>unmeasured</b>. All candidates are unreviewed. Integrity checks are not recognition accuracy.</p>',
              '<p><a href="review.html">Open manual review tool</a> · <a href="review-template.json">Review JSON template</a> · <a href="evaluation.json">Unreviewed evaluation</a></p>',
              '<h2>PDF comparison</h2><table><tr><th>Plan</th><th>Before matched</th><th>Before unmatched</th><th>After matched</th><th>After unmatched</th><th>Existing identities retained</th></tr>'+rows+'</table>',
              '<p>Connected thin vector boundaries define regions. Text direction selects an adjacent horizontal or vertical boundary; its span separates connected blocks. Labels may be above, below or beside a grid. Conflicting regions and repeated identities abstain. Only axis-aligned grids and right-angle label rotations are supported; missing boundary geometry remains a limitation.</p>',
              '<h2>Image baseline</h2><p>CMYK JPEG → RGB working copy → neutral square components → number crop mosaics → local English Tesseract → row/zone association. Font-sized glyphs that sparse OCR skips are retried as single-line/single-character crops. No sequential row names or missing numbers are invented.</p>',
              '<p>Overlay: green = assigned candidate; red = unresolved; magenta = duplicate identity; blue = accessibility region (not seat count); orange = possible gap (not confirmed missing seat). Gray cells include OP seats. Theatre 3 has 244 regular seats plus 4 wheelchair spaces according to its legend.</p>']
    for image_result in images:
        theatre = image_result['file'].split('-')[0]+'-'+image_result['file'].split('-')[1]
        report.append(f'<h3>{html.escape(theatre)}</h3><pre>{html.escape(json.dumps(image_result,indent=2))}</pre><p><a href="{theatre}/seats.csv">CSV</a> · <a href="{theatre}/seats.json">JSON</a></p><a href="{theatre}/overlay.png"><img src="{theatre}/overlay.png"></a>')
    report.append('<h2>PDF verification images</h2><p>Green text candidates, blue connected block regions, magenta source labels. Individual seat shapes were not extracted. Inspect rotated sides, rear blocks and the partial rows in split-small-208.</p>')
    for r in comparisons:
        stem = Path(r['file']).stem
        report.append(f'<h3>{stem}</h3><a href="theatre-1/{stem}/overlay.png"><img loading="lazy" src="theatre-1/{stem}/overlay.png"></a>')
    report.append(f'<h2>Review and learning</h2><p>{len(samples)} purposive samples cover block/band extremes, centers and problem strata. Export review JSON from the review tool; then run evaluate_review.py. Rates use only explicitly reviewed, applicable fields. Full-map recall remains unmeasured without independent region inventories. Position errors stay separated by pt/px.</p><p>Exercises: change the relative gap thresholds in image_baseline.gap_candidates and extend its missing-seat test; add an ambiguous rotated-label fixture to test_layout.GeometryTests. Observe abstention, not only matched counts.</p><p>Known OCR failures: single digits 6/9, row I, and some O/R markers; OP labels may be unresolved. Full-page OCR joins adjacent numbers into long strings. Crop OCR reduces joining but does not eliminate missing glyphs. BOX columns must stop before the next floor. Blue regions may contain multiple symbols; their segmentation does not establish wheelchair count.</p>')
    (output/'report.html').write_text('\n'.join(report),encoding='utf-8')
    print(json.dumps({'pdfs':comparisons,'images':images,'manual_samples':len(samples)},indent=2))


if __name__ == '__main__':
    main()
