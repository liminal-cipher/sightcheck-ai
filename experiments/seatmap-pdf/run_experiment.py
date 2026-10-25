"""Run improved extraction and review preparation without repeating the saved baseline."""
import argparse
from collections import defaultdict, Counter
import csv
from datetime import datetime, timezone
import hashlib
import html
import json
import math
from pathlib import Path
import platform

import cv2
import fitz
import numpy as np
from PIL import Image, ImageDraw, __version__ as pillow_version

from extract_layout import extract, connected_rules
from image_baseline import run as run_image, write_json
from evaluate_review import evaluate

BASE = Path(__file__).resolve().parent
# Source units, independent of the surrounding crop margin.
SEAT_HIGHLIGHT_PADDING = {'pt': 1.5, 'px': 3}


def write_seat_crop(image, box, scale, bounds, unit, destination):
    crop = image.crop(bounds)
    padding = SEAT_HIGHLIGHT_PADDING[unit]
    highlight = [(box[0]-padding)*scale-bounds[0], (box[1]-padding)*scale-bounds[1],
                 (box[2]+padding)*scale-bounds[0], (box[3]+padding)*scale-bounds[1]]
    highlight = [max(0, highlight[0]), max(0, highlight[1]),
                 min(crop.width-1, highlight[2]), min(crop.height-1, highlight[3])]
    ImageDraw.Draw(crop).rectangle(highlight, outline='#ff3300', width=2)
    crop.save(destination)


def refresh_seat_crops(output, review):
    """Retain saved crop dimensions and coordinate mapping; rewrite only images."""
    grouped = defaultdict(list)
    for sample in review['samples']:
        grouped[(sample['document'], sample['unit'])].append(sample)
    for (document, unit), samples in grouped.items():
        source = output/'theatre-1'/document/'page.png' if unit == 'pt' else output/document/'rgb.png'
        with Image.open(source) as image:
            for sample in samples:
                destination = output/sample['crop']
                with Image.open(destination) as old_crop:
                    width, height = old_crop.size
                scale = sample['render_scale']
                x, y = [round(value*scale) for value in sample['crop_origin']]
                write_seat_crop(image, sample['prediction']['bbox'], scale,
                                [x,y,x+width,y+height], unit, destination)


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
        relative = f'review-crops/{sample_id}.png'
        write_seat_crop(image, box, scale, bounds, unit, output/relative)
        samples.append({'sample_id':sample_id,'document':name,'source_sha256':source_hash,
                        'unit':unit,'position_anchor':'text_center' if unit=='pt' else 'shape_center',
                        'shape_detection_attempted':candidate['kind']=='regular_seat_shape_candidate',
                        'stratum':candidate['stratum'],'kind':candidate['kind'],
                        'crop':relative,'crop_origin':[bounds[0]/scale,bounds[1]/scale],
                        'render_scale':scale,'prediction':candidate,
                        'review':{'status':'pending','shape_correct':None,'text_correct':None,
                                  'identity_correct':None,'expected_center':None,'correction':None,'notes':''}})


def pdf_context_bounds(candidate, regions, page_size):
    """Include complete predicted regions and source labels in any text direction."""
    matches = [r for r in regions if candidate.get('block') is not None
               and r['block'] == candidate['block']]
    if not matches:
        return [0, 0, *page_size], matches
    boxes = [candidate['bbox']]
    boxes.extend(box for r in matches for box in (r['bbox_pt'], r['label_bbox_pt']))
    bounds = [min(b[0] for b in boxes), min(b[1] for b in boxes),
              max(b[2] for b in boxes), max(b[3] for b in boxes)]
    # Geometry determines coverage; proportional breathing room shows adjacent aisles.
    padding = max(bounds[2]-bounds[0], bounds[3]-bounds[1]) * .08
    return [max(0, bounds[0]-padding), max(0, bounds[1]-padding),
            min(page_size[0], bounds[2]+padding), min(page_size[1], bounds[3]+padding)], matches


def seat_cell_bounds(candidate, rules):
    """Find the enclosing grid cell from source rules, not the text box size."""
    x0, y0, x1, y1 = candidate['bbox']
    cx, cy = (x0+x1)/2, (y0+y1)/2
    horizontal = [r for r in rules if r.width > r.height and r.x0 <= cx <= r.x1]
    vertical = [r for r in rules if r.height > r.width and r.y0 <= cy <= r.y1]
    sides = ([r.x1 for r in vertical if r.x1 < cx],
             [r.y1 for r in horizontal if r.y1 < cy],
             [r.x0 for r in vertical if r.x0 > cx],
             [r.y0 for r in horizontal if r.y0 > cy])
    if not all(sides):
        return None
    left, top, right, bottom = max(sides[0]), max(sides[1]), min(sides[2]), min(sides[3])
    # Each chosen side must span the cell, rather than belong to a distant grid.
    if not all(any(r.x0 <= left+1 and r.x1 >= right-1 and r.y0-1 <= y <= r.y1+1
                   for r in horizontal) for y in (top, bottom)):
        return None
    if not all(any(r.y0 <= top+1 and r.y1 >= bottom-1 and r.x0-1 <= x <= r.x1+1
                   for r in vertical) for x in (left, right)):
        return None
    # Include rule thickness so exterior marks also clear heavy outer borders.
    return [min(r.x0 for r in vertical if r.x1 == left),
            min(r.y0 for r in horizontal if r.y1 == top),
            max(r.x1 for r in vertical if r.x0 == right),
            max(r.y1 for r in horizontal if r.y0 == bottom)]


def draw_cell_corners(image, cell, gap=3, width=1, arm_length=None, background_min=250):
    """Draw thin exterior corners only on blank pixels, preserving source ink."""
    mask = Image.new('L', image.size)
    draw = ImageDraw.Draw(mask)
    left, top, right, bottom = cell
    left, top = math.floor(left)-gap, math.floor(top)-gap
    right, bottom = math.ceil(right)+gap, math.ceil(bottom)+gap
    length = arm_length or max(3, min(7, round(min(right-left, bottom-top)*.2)))
    for x, dx in ((left, 1), (right, -1)):
        for y, dy in ((top, 1), (bottom, -1)):
            draw.line([(x+dx*length, y), (x, y), (x, y+dy*length)], fill=255, width=width)
    blank = np.all(np.asarray(image.convert('RGB')) >= background_min, axis=2)
    mask = Image.fromarray(np.where(blank, np.asarray(mask), 0).astype(np.uint8))
    image.paste('#ff3300', (0, 0), mask)


def write_pdf_contexts(output, review):
    """Keep display-only context outside the persisted review schema."""
    contexts = {}
    grouped = defaultdict(list)
    for sample in review['samples']:
        if sample['unit'] == 'pt':
            grouped[sample['document']].append(sample)
    (output/'review-contexts').mkdir(exist_ok=True)
    for document, samples in grouped.items():
        source = output/'theatre-1'/document
        layout = json.loads((source/'seats.json').read_text(encoding='utf-8'))
        with fitz.open(BASE/'input/theatre-1'/f'{document}.pdf') as pdf:
            rules = [rule for group in connected_rules(pdf[0]) for rule in group]
        with Image.open(source/'page.png') as image:
            sx, sy = image.width/layout['page_size_pt'][0], image.height/layout['page_size_pt'][1]
            for sample in samples:
                bounds, matches = pdf_context_bounds(sample['prediction'], layout['block_regions'], layout['page_size_pt'])
                pixels = [math.floor(bounds[0]*sx), math.floor(bounds[1]*sy),
                          math.ceil(bounds[2]*sx), math.ceil(bounds[3]*sy)]
                crop = image.crop(pixels)
                draw = ImageDraw.Draw(crop)
                def local(box):
                    return [box[0]*sx-pixels[0], box[1]*sy-pixels[1],
                            box[2]*sx-pixels[0], box[3]*sy-pixels[1]]
                for region in matches:
                    draw.rectangle(local(region['bbox_pt']), outline='#0072b2', width=2)
                cell = seat_cell_bounds(sample['prediction'], rules)
                if cell:
                    draw_cell_corners(crop, local(cell))
                relative = f"review-contexts/{sample['sample_id']}.png"
                crop.save(output/relative)
                contexts[sample['sample_id']] = {'image':relative, 'has_region':bool(matches), 'has_cell':cell is not None}
    return contexts


def write_jpeg_contexts(output, review):
    """Keep full-plan labels and floor/BOX divisions visible without inferring zones."""
    contexts = {}
    grouped = defaultdict(list)
    for sample in review['samples']:
        if sample['unit'] == 'px':
            grouped[sample['document']].append(sample)
    (output/'review-contexts').mkdir(exist_ok=True)
    for document, samples in grouped.items():
        with Image.open(output/document/'rgb.png') as source:
            for sample in samples:
                image = source.convert('RGB')
                # JPEG floor backgrounds are tinted; keep dark glyphs and seat fills intact.
                draw_cell_corners(image, sample['prediction']['bbox'], gap=6, width=3,
                                  arm_length=18, background_min=180)
                relative = f"review-contexts/{sample['sample_id']}.png"
                image.save(output/relative, compress_level=1)
                contexts[sample['sample_id']] = {'image':relative}
    return contexts


def write_review_contexts(output, review):
    return {**write_pdf_contexts(output, review), **write_jpeg_contexts(output, review)}


def write_review_ui(output, review, contexts=None):
    payload = json.dumps(review).replace('<','\\u003c')
    template = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>좌석 후보 검토</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f5f6f7;color:#252a32;font:15px/1.6 system-ui,"Malgun Gothic",sans-serif}main{max-width:1320px;margin:auto;padding:28px 24px 48px}h1{font-size:26px;margin:0}h2{font-size:18px;margin:0 0 12px}p{margin:8px 0 16px}.muted,.hint{color:#626a75;font-size:13px}.notice{border-left:3px solid #737b87;padding:8px 12px;background:#eef0f3}.toolbar,.panel{background:white;border:1px solid #dce0e5;border-radius:10px;padding:20px}.toolbar{margin:20px 0}.toolbar-row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.toolbar-row+.toolbar-row{margin-top:14px}.grow{flex:1;min-width:180px}.toolbar label{margin:0}#current-sample{font-weight:650;overflow-wrap:anywhere}#progress-counts{font-size:14px;color:#4e5662}progress{width:100%;height:7px;accent-color:#596474;display:block;margin-top:10px}button,select,input,textarea{font:inherit;color:inherit}button,.file-button{border:1px solid #cbd0d8;border-radius:6px;padding:9px 14px;background:#fff;cursor:pointer;display:inline-block}button:hover,.file-button:hover{background:#f0f2f5}button.primary{background:#343d49;color:#fff;border-color:#343d49}button:disabled{opacity:.45;cursor:default}select,input,textarea{border:1px solid #cbd0d8;border-radius:6px;padding:9px;background:#fff;max-width:100%}select,textarea{width:100%}input{width:100%}input[type=file]{width:auto}#import{position:absolute;width:1px;height:1px;opacity:0}.file-button:focus-within,button:focus-visible,select:focus-visible,input:focus-visible,textarea:focus-visible,summary:focus-visible,a:focus-visible{outline:2px solid #566274;outline-offset:3px}.grid{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:24px;align-items:start}.column{min-width:0;display:grid;gap:20px}.image-frame{background:#fafafa;border:1px solid #e1e4e8;padding:12px;text-align:center;overflow:auto}img{max-width:100%;height:auto;display:block;margin:auto}#crop{cursor:crosshair}#context-image{cursor:zoom-in}a{color:#414c5c;text-underline-offset:3px}.image-tools{display:flex;justify-content:space-between;gap:12px;font-size:13px;margin:10px 0 0}.prediction-summary dl{display:grid;grid-template-columns:135px minmax(0,1fr);gap:7px 14px;margin:12px 0}.prediction-summary dt{color:#626a75;font-size:13px}.prediction-summary dd{margin:0;overflow-wrap:anywhere}.prediction-summary dd:first-of-type{font-size:25px;font-weight:700;line-height:1.3}.prediction-summary dt.aux,.prediction-summary dd.aux{font-size:12px;color:#737b87}.question{display:block;margin-bottom:16px;font-weight:600}.question select{display:block;margin-top:6px;font-weight:400}fieldset{border:0;padding:0;margin:0}legend{font-weight:650;margin-bottom:14px}details{border-top:1px solid #e1e4e8;margin-top:16px;padding-top:4px}summary{cursor:pointer;padding:12px 0;font-weight:600}details pre{font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f6f7;padding:12px}.corrections{display:grid;grid-template-columns:1fr 1fr;gap:12px}.corrections label{display:block;font-size:13px}.corrections input{display:block;margin-top:4px}textarea{min-height:90px;resize:vertical;display:block}.advanced{margin-top:24px}.advanced details{margin:0;border:0}#error{color:#803c3c;white-space:pre-wrap}#error:empty{display:none}#position{font-size:13px;overflow-wrap:anywhere}.status-row{margin-bottom:20px;padding-bottom:18px;border-bottom:1px solid #e1e4e8}@media(max-width:800px){main{padding:18px 14px}.grid{grid-template-columns:1fr}.panel,.toolbar{padding:16px}.toolbar-row{gap:8px}.prediction-summary dl{grid-template-columns:110px minmax(0,1fr)}}
</style>
<main><header><h1>좌석 후보 검토</h1><p class="muted">이미지와 알고리즘의 예측을 비교하고, 각 항목을 독립적으로 판단하세요. 모든 예측은 미검증 상태입니다.</p></header>
<section class="toolbar" aria-label="검토 진행 및 이동">
<div class="toolbar-row"><div class="grow"><div id="current-sample"></div><div id="progress-counts" aria-live="polite"></div></div><button id="export" class="primary">검토 결과 저장</button><label class="file-button">이전 결과 불러오기<input id="import" type="file" accept=".json"></label></div>
<progress id="progress" value="0" max="1" aria-label="검토 완료 비율"></progress>
<div class="toolbar-row"><button id="prev">이전</button><label class="grow"><span class="hint">검토 항목 선택</span><select id="pick"></select></label><button id="next">다음</button></div>
<p class="hint" style="margin-bottom:0">자동 저장되지 않습니다. <strong>‘검토 결과 저장’으로 내려받은 JSON 파일만 저장본입니다.</strong> 창을 닫기 전에 저장하고, 다음 검토 때 불러오세요.</p>
<p id="error" role="alert"></p></section>
<div class="grid"><div class="column">
<section class="panel"><h2>좌석 확대 이미지</h2><p class="hint">빨간 테두리는 선택 후보입니다. 이미지에서 올바른 중심을 클릭하면 위치를 기록합니다.</p><div class="image-frame"><img id="crop" alt="선택 좌석 후보 확대 이미지"></div><div class="image-tools"><span>표시 색상은 정답 여부를 뜻하지 않습니다.</span><a id="crop-link" target="_blank" rel="noopener">원본 크기로 보기 ↗</a></div></section>
<section id="context" class="panel" hidden><h2 id="context-title">PDF 블록 문맥</h2>
<p id="pdf-context-description" class="hint">파란 선은 예측 블록 경계, 주황 모서리는 선택 후보 위치입니다. 원본 라벨과 주변 경계를 비교하세요. PDF 위치는 문자 중심이며, 개별 좌석 도형 검출은 수행하지 않았습니다.</p>
<p id="jpeg-context-description" class="hint" hidden>전체 도면에서 행 라벨·구역·BOX·층 구분을 확인하세요. 주황 모서리는 선택 후보 위치입니다. 파란 영역은 여러 자리를 포함할 수 있으며 개별 휠체어 좌석이 아닙니다.</p>
<p id="context-note" class="hint"></p><a id="context-link" target="_blank" rel="noopener" class="image-frame"><img id="context-image" alt="선택 후보의 도면 문맥"></a><p class="hint" style="margin-bottom:0">문맥 이미지를 누르면 원본 크기로 열립니다. 위치 기록은 위의 확대 이미지에서만 가능합니다.</p></section>
</div><div class="column">
<section class="panel prediction-summary" aria-labelledby="prediction-heading"><h2 id="prediction-heading">예측 정보 요약</h2><p class="notice hint">미검증 예측 · 연결됨은 정답을 의미하지 않습니다.</p><dl id="prediction-summary"></dl><details id="prediction-details"><summary>상세 정보 보기</summary><pre id="info"></pre></details></section>
<section class="panel"><h2>정확성 검토</h2><label class="question status-row">검토 상태<select id="status"><option value="pending">미검토</option><option value="reviewed">검토 완료</option><option value="uncertain">판단 불가</option></select></label>
<fieldset><legend class="hint">근거가 부족하거나 해당하지 않으면 ‘판단 안 함·해당 없음’을 유지하세요.</legend>
<label class="question">좌석 도형 검출이 정확한가요?<select id="shape_correct"></select></label>
<label class="question">추출한 문자가 정확한가요?<select id="text_correct"></select></label>
<label class="question">구역·행·번호 연결이 정확한가요?<select id="identity_correct"></select></label></fieldset>
<details id="corrections-details"><summary>수정값 입력 (선택)</summary><p class="hint">원본에서 확인한 표기를 입력하세요. 예측값 자체는 바뀌지 않습니다.</p><div class="corrections"><label>구역<input id="block"></label><label>행<input id="row"></label><label>번호<input id="number"></label><label>문자<input id="text"></label></div></details>
<label class="question" style="margin-top:18px">검토 메모<textarea id="notes"></textarea></label><p id="position"></p><button id="clear">기록한 위치 지우기</button></section>
</div></div>
<section class="panel advanced"><details><summary>누락 좌석 기록 · 고급</summary><p class="hint">전체 도면에서 별도로 발견한 누락 후보를 JSON 배열로 기록하세요. 도면·유형·중심 좌표·단위·메모를 포함하며, JSON 필드명은 기존 형식을 유지하세요. 이 기록은 누락 이슈 목록이며 전체 검출률의 분모가 아닙니다. 선정된 표본만으로 전체 도면의 정확도나 검출률을 판단할 수 없습니다.</p><label for="missed" class="hint">누락 후보 JSON 배열</label><textarea id="missed" placeholder="[]"></textarea></details></section></main>
<script>
let data = __DATA__, index=0;
const contexts = __CONTEXTS__;
const $=id=>document.getElementById(id);
function showPrediction(s){
    const p=s.prediction,pdf=s.unit==='pt',blue=s.kind==='accessibility_or_blue_region';
    const present=value=>value!==null&&value!==undefined&&String(value).trim()!=='';
    const rows=[['예측 좌석 ID',blue?'해당 없음 (개별 좌석 아님)':present(p.seat_id)?p.seat_id:'미매칭'],['도면명',s.document],['검토 대상 ID',s.sample_id],
        [blue?'영역 후보 ID':pdf?'추출 후보 ID':'좌석 후보 ID',p.candidate_id??'없음'],
        ['검토 대상 유형',blue?'파란 접근성 영역 후보 (개별 좌석 아님)':pdf?'PDF 좌석 문자':'JPEG 좌석 후보'],
        [pdf?'추출 문자':'OCR 문자',present(p.text)?p.text:blue?'해당 없음 (영역 후보)':'인식되지 않음']];
    for(const [field,label] of [['block','예측 블록·구역'],['row','예측 행'],['number','예측 번호']]){
        if(present(p[field]))rows.push([label,p[field]]);
    }
    rows.push(['매칭 상태',blue?'해당 없음 (개별 좌석 연결 대상 아님)':present(p.seat_id)?'연결됨 (미검증)':'미매칭']);
    const reasons={number_ocr_uncertain:'좌석 번호 OCR이 불확실함',row_or_zone_unresolved:'행 또는 구역을 연결하지 못함',region_not_individual_wheelchair_seat:'개별 휠체어 좌석이 아닌 파란 영역 후보'};
    if(present(p.reason))rows.push([blue?'영역 설명':'미매칭 사유',reasons[p.reason]??p.reason]);
    const auxiliary=rows.splice(1,4);rows.push(...auxiliary);
    $('prediction-summary').replaceChildren();
    for(const [label,value] of rows){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=String(value);if(auxiliary.some(row=>row[0]===label)){dt.className='aux';dd.className='aux';}$('prediction-summary').append(dt,dd);}
}
for(const f of ['shape_correct','text_correct','identity_correct']) $(''+f).innerHTML='<option value="">판단 안 함·해당 없음</option><option value="true">맞음</option><option value="false">틀림</option>';
function save(){let r=data.samples[index].review;r.status=$('status').value;for(const f of ['shape_correct','text_correct','identity_correct'])r[f]=$(f).value===''?null:$(f).value==='true';r.notes=$('notes').value;const c={};for(const f of ['block','row','number','text'])if($(f).value!=='')c[f]=$(f).value;r.correction=Object.keys(c).length?c:null;updateProgress();}
function show(){const s=data.samples[index],r=s.review;$('pick').value=index;$('crop').src=s.crop;$('info').textContent=JSON.stringify({sample:s.sample_id,stratum:s.stratum,unit:s.unit,anchor:s.position_anchor,prediction:s.prediction},null,2);$('status').value=r.status;for(const f of ['shape_correct','text_correct','identity_correct'])$(f).value=r[f]===null?'':String(r[f]);$('shape_correct').disabled=!s.shape_detection_attempted;for(const f of ['block','row','number','text'])$(f).value=r.correction?.[f]??'';$('notes').value=r.notes;$('position').textContent=r.expected_center?'기록한 중심: '+JSON.stringify(r.expected_center)+' ('+(s.unit==='pt'?'PDF 포인트':'픽셀')+')':'기록한 위치 없음';}
const showSample = show;
show = function(){
    showSample();const s=data.samples[index],c=contexts[s.sample_id],pdf=s.unit==='pt';
    showPrediction(s);updateProgress();$('crop-link').href=s.crop;
    $('current-sample').textContent=`${index+1} / ${data.samples.length} · ${s.document}`;
    $('prev').disabled=index===0;$('next').disabled=index===data.samples.length-1;
    $('context').hidden=false;$('context-title').textContent=pdf?'PDF 블록 문맥':'JPEG 전체 도면 문맥';
    $('pdf-context-description').hidden=!pdf;$('jpeg-context-description').hidden=pdf;
    $('context-image').hidden=!c;$('context-link').removeAttribute('href');$('context-image').removeAttribute('src');
    $('context-image').alt=pdf?'예측 블록과 선택 후보가 표시된 PDF 문맥':'선택 후보와 행·BOX·층 구분이 있는 JPEG 전체 도면';
    if(c){$('context-image').src=c.image;$('context-link').href=c.image;}
    $('context-note').textContent=!c?'문맥 이미지를 사용할 수 없습니다.':pdf?(c.has_region?'':'예측 블록 영역이 없어 전체 도면을 표시합니다. ')+(c.has_cell?'':'좌석 칸 경계를 찾지 못해 선택 표시를 생략했습니다.'):
        '미검증 예측 — 구역: '+(s.prediction.block??'미지정')+', 행: '+(s.prediction.row??'미지정')+'. 층은 원본 도면에서 확인하세요.';
};
function updateProgress(){const counts={pending:0,reviewed:0,uncertain:0};for(const s of data.samples)if(s.review.status in counts)counts[s.review.status]++;$('progress-counts').textContent=`검토 완료 ${counts.reviewed} · 미검토 ${counts.pending} · 판단 불가 ${counts.uncertain} / 전체 ${data.samples.length}`;$('progress').max=data.samples.length;$('progress').value=counts.reviewed;}
$('status').onchange=()=>save();
function populate(){$('pick').innerHTML='';data.samples.forEach((s,i)=>{const o=document.createElement('option');o.value=i;o.textContent=`${i+1}. ${s.sample_id}`;$('pick').append(o)});$('missed').value=JSON.stringify(data.missed_objects??[],null,2);show();}
$('next').onclick=()=>{save();index=Math.min(index+1,data.samples.length-1);show()};$('prev').onclick=()=>{save();index=Math.max(index-1,0);show()};$('pick').onchange=e=>{save();index=Number(e.target.value);show()};
$('crop').onclick=e=>{save();const s=data.samples[index],r=e.target.getBoundingClientRect();s.review.expected_center=[s.crop_origin[0]+(e.clientX-r.left)*e.target.naturalWidth/r.width/s.render_scale,s.crop_origin[1]+(e.clientY-r.top)*e.target.naturalHeight/r.height/s.render_scale];show()};$('clear').onclick=()=>{save();data.samples[index].review.expected_center=null;show()};
$('export').onclick=()=>{save();try{data.missed_objects=JSON.parse($('missed').value);if(!Array.isArray(data.missed_objects))throw Error('누락 좌석 기록은 JSON 배열이어야 합니다.');const a=document.createElement('a'),u=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));a.href=u;a.download='review-completed.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);$('error').textContent=''}catch(e){$('error').textContent=e instanceof SyntaxError?'JSON 형식을 읽을 수 없습니다. 파일 또는 누락 좌석 기록을 확인하세요.':e instanceof TypeError?'검토 파일의 필수 항목이 없거나 잘못되었습니다.':e.message}};
$('import').onchange=async e=>{if(!e.target.files[0])return;try{const incoming=JSON.parse(await e.target.files[0].text());if(incoming.schema_version!==1||incoming.samples.length!==data.samples.length)throw Error('검토 파일의 형식 또는 표본 수가 일치하지 않습니다.');const lookup=new Map(incoming.samples.map(s=>[s.sample_id,s]));for(const s of data.samples){const prior=lookup.get(s.sample_id);if(!prior||prior.source_sha256!==s.source_sha256)throw Error('검토 대상 ID 또는 원본 자료가 일치하지 않습니다.');}for(const s of data.samples)s.review=lookup.get(s.sample_id).review;data.missed_objects=incoming.missed_objects??[];populate();$('error').textContent=''}catch(e){$('error').textContent=e instanceof SyntaxError?'JSON 형식을 읽을 수 없습니다. 파일 또는 누락 좌석 기록을 확인하세요.':e instanceof TypeError?'검토 파일의 필수 항목이 없거나 잘못되었습니다.':e.message}};
populate();
</script></html>'''
    context_payload = json.dumps(contexts or {}).replace('<','\\u003c')
    (output/'review.html').write_text(template.replace('__DATA__',payload).replace('__CONTEXTS__',context_payload),encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=BASE/'output/phase-abc')
    parser.add_argument('--skip-images',action='store_true',help='Rebuild report from existing image baseline results')
    parser.add_argument('--review-only',action='store_true',help='Rebuild review HTML/context from saved results without rewriting JSON or seat crops')
    parser.add_argument('--crops-only',action='store_true',help='Refresh seat highlight crops only; retain saved JSON, crop mapping and context images')
    args = parser.parse_args(); output = args.output_dir.resolve()
    prior_dir = BASE/'output/acc-audit'
    if output == prior_dir.resolve() or prior_dir.resolve() in output.parents:
        parser.error('Use a separate output directory; acc-audit is the preserved baseline')
    if args.crops_only:
        if args.review_only:
            parser.error('Choose either --crops-only or --review-only')
        review = json.loads((output/'review-template.json').read_text(encoding='utf-8'))
        refresh_seat_crops(output, review)
        print(f"Refreshed {len(review['samples'])} seat crops")
        return
    if args.review_only:
        review = json.loads((output/'review-template.json').read_text(encoding='utf-8'))
        write_review_ui(output, review, write_review_contexts(output, review))
        print(str(output/'review.html'))
        return
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
    write_review_ui(output,review,write_review_contexts(output,review))
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
