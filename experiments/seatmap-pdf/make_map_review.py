"""Build a whole-map review page: every detected cell drawn on the plan, colored by the structure check.

The page shows each theatre's plan with all gray seat cells and blue regions.
Cells the structure check flags (check_seatmap.py) are red, unread cells gray,
clean cells green. Clicking a cell shows a zoomed view, the primary reading, the
OCR reading and why it was flagged, and lets the reviewer confirm or correct it.

Corrections are saved as JSON in the blind pages' sample/label layout. Pass that
file back to check_seatmap.py as the first --source to re-check the corrected
map. The page itself does not re-run the checks.
"""
from pathlib import Path
import argparse
import json

from check_seatmap import SEVERE, check, collect, ocr_readings, parse_expect
from make_blind_review import ZONES

BASE = Path(__file__).resolve().parent


def build_theatre(out, theatre, sources, compare_source=None, expect=None):
    data = json.loads((out/theatre/'seats.json').read_text(encoding='utf-8'))
    seats, cell = data['seats'], data['parameters']['modal_cell_size_px']
    readings, origin = collect(out, theatre, sources, seats)
    compare = None
    if compare_source:
        second, _ = collect(out, theatre, [compare_source], seats)
        compare = {c: r for c, r in second.items() if origin.get(c) != compare_source}
    result = check(seats, readings, cell, expect, compare)
    ocr = ocr_readings(seats)
    cells = []
    for s in seats:
        cid = s['candidate_id']
        flags = result['flags'].get(cid, [])
        cells.append({'id': f'{theatre}--{cid}', 'kind': 'seat', 'bbox': s['bbox_px'],
                      'reading': readings.get(cid), 'source': origin.get(cid), 'ocr': ocr.get(cid),
                      'flags': flags, 'severe': bool(SEVERE & set(flags))})
    for region in data['accessibility_regions']:
        cid = region['candidate_id']
        cells.append({'id': f'{theatre}--{cid}', 'kind': 'region', 'bbox': region['bbox_px'],
                      'reading': readings.get(cid), 'source': origin.get(cid), 'ocr': None,
                      'flags': [], 'severe': False})
    return {'name': theatre, 'image': f'{theatre}/rgb.png', 'size': data['size_px'], 'cell': cell,
            'cells': cells, 'summary': result['summary']}


PAGE = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>전체 도면 검토</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f5f6f7;color:#252a32;font:14px/1.5 system-ui,"Malgun Gothic",sans-serif}
header{position:sticky;top:0;z-index:5;background:#fff;border-bottom:1px solid #dce0e5;padding:10px 16px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
h1{font-size:18px;margin:0 8px 0 0}.muted{color:#626a75;font-size:12px}#count{min-width:160px}
button,select,.file{font:inherit;border:1px solid #cbd0d8;border-radius:6px;padding:6px 10px;background:#fff;cursor:pointer}
button.primary{background:#343d49;color:#fff;border-color:#343d49}#import{display:none}
main{display:grid;grid-template-columns:minmax(0,1fr) 380px;gap:12px;padding:12px 16px}
#mapwrap{overflow:auto;height:calc(100vh - 80px);background:#fff;border:1px solid #dce0e5;border-radius:8px}
#map{position:relative;transform-origin:0 0}#map img,#map svg{position:absolute;left:0;top:0;width:100%;height:100%}
#map img{opacity:.85}rect{fill:transparent;stroke-width:4;cursor:pointer}
.ok{stroke:#2e9d57}.severe{stroke:#d6312b;fill:rgba(214,49,43,.25)!important;stroke-width:8}.unread{stroke:#5f6670;stroke-width:6;stroke-dasharray:8 5;fill:rgba(95,102,112,.18)!important}
.region{stroke:#0b2a66;stroke-width:10;stroke-dasharray:14 6}.fixed{stroke:#7b3fd0;fill:rgba(123,63,208,.22)!important;stroke-width:8}.sel{stroke:#000!important;stroke-width:12!important}
.hidden-cell{display:none}aside{display:flex;flex-direction:column;gap:10px;height:calc(100vh - 80px);overflow:auto}
.panel{background:#fff;border:1px solid #dce0e5;border-radius:8px;padding:12px}
#zoom{width:100%;height:220px;background-repeat:no-repeat;background-color:#fafafa;border:1px solid #e1e4e8;position:relative;image-rendering:pixelated}
#zoombox{position:absolute;border:2px solid #d6312b;pointer-events:none}
dl{display:grid;grid-template-columns:90px 1fr;gap:4px 8px;margin:0}dt{color:#626a75}dd{margin:0}
ul{margin:4px 0 0 18px;padding:0}label{display:block;font-weight:600;margin-bottom:8px}label span{font-weight:400;color:#626a75;font-size:12px}
input,textarea,form select{font:inherit;width:100%;padding:6px;border:1px solid #cbd0d8;border-radius:6px}
.legend span{display:inline-block;width:12px;height:12px;border:2px solid;margin:0 4px 0 10px;vertical-align:-2px}
#error{color:#803c3c}@media(max-width:900px){main{grid-template-columns:1fr}#mapwrap,aside{height:auto}#mapwrap{height:70vh}}
</style>
<header><h1>전체 도면 검토</h1>
<select id="theatre"></select>
<select id="filter"><option value="severe">경고 칸</option><option value="unread">안 읽힌 칸</option><option value="fixed">고친 칸</option><option value="all">모든 칸</option></select>
<button id="prev">이전</button><button id="next">다음</button><span id="count" class="muted"></span>
<button id="zoomout">축소</button><button id="zoomin">확대</button>
<button id="export" class="primary">결과 저장</button><label class="file" style="margin:0;font-weight:400">불러오기<input id="import" type="file" accept=".json"></label>
<span class="legend muted"><span style="border-color:#2e9d57"></span>문제없음<span style="border-color:#d6312b"></span>경고<span style="border-color:#8a9099;border-style:dashed"></span>안 읽힘<span style="border-color:#0b2a66;border-style:dashed"></span>파란(휠체어) 영역<span style="border-color:#7b3fd0"></span>검토함</span>
<span id="error"></span></header>
<main><div id="mapwrap"><div id="map"><img id="plan" alt="좌석 도면"><svg id="cells"></svg></div></div>
<aside><div class="panel"><div id="zoom"><div id="zoombox"></div></div><p class="muted" id="where">도면에서 칸을 누르거나 ‘다음’으로 넘겨 보세요.</p>
<dl><dt>판독</dt><dd id="reading"></dd><dt>판독 출처</dt><dd id="source"></dd><dt>OCR</dt><dd id="ocr"></dd></dl>
<div id="flagbox"><strong>경고 이유</strong><ul id="flags"></ul></div></div>
<form class="panel" id="form">
<label>좌석 한 칸인가요?<select id="is_seat"><option value="">선택</option><option value="yes">예, 좌석 한 칸</option><option value="no">아니오 (라벨·영역·기타)</option><option value="unsure">판단 불가</option></select></label>
<label>구역<select id="zone"><option value="">선택</option>__ZONES__</select><span>main = BOX·OP가 아닌 일반 객석</span></label>
<label>행<input id="row" maxlength="8"><span>BOX석처럼 행이 없으면 비워 두세요.</span></label>
<label>좌석 번호<input id="number" maxlength="12"></label>
<label>메모<textarea id="notes" rows="2"></textarea></label>
<button type="button" id="accept">판독이 맞음</button> <button type="button" id="save" class="primary">고친 값 저장</button> <button type="button" id="clear">검토 취소</button>
<p class="muted">‘결과 저장’으로 받은 JSON을 check_seatmap.py의 첫 --source로 넣으면 고친 값을 반영해 다시 검사합니다. 이 페이지는 검사를 다시 돌리지 않습니다.</p>
</form></aside></main>
<script>
const data=__DATA__;const KEY='map-review-v1';const fields=['is_seat','zone','row','number','notes'];
const REASONS={unread:'판독 없음',incomplete:'번호나 구역이 비어 있음',not_a_seat:'회색 좌석 칸인데 좌석이 아니라고 읽음',
duplicate_id:'같은 좌석 ID가 다른 칸에도 있음',out_of_order:'행 안에서 번호 순서가 칸 위치와 어긋남',
adjacent_jump:'붙어 있는 칸과의 번호 차이가 그 행의 보통 간격과 다름',row_misaligned:'칸이 그 행의 줄에서 벗어나 있음',
row_letter_order:'행 문자가 위아래 순서와 어긋남',reader_disagreement:'모델 판독과 OCR 판독이 다름'};
const $=id=>document.getElementById(id);const NS='http://www.w3.org/2000/svg';
let labels={};try{labels=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){labels={}}
let t=0,sel=null,zoom=1,list=[];
function persist(){try{localStorage.setItem(KEY,JSON.stringify(labels))}catch(e){}}
function th(){return data.theatres[t]}
function describe(r){if(!r)return '없음';if(r.is_seat!=='yes')return '좌석 한 칸 아님'+(r.number?' · 글자 '+r.number:'');return `${r.zone} · 행 ${r.row||'-'} · 번호 ${r.number??'-'}`}
function cls(c){if(labels[c.id]&&labels[c.id].status==='reviewed')return 'fixed';if(c.kind==='region')return 'region';if(c.severe)return 'severe';if(!c.reading)return 'unread';return 'ok'}
function matches(c){const f=$('filter').value;const k=cls(c);return f==='all'||(f==='severe'&&c.severe)||(f==='unread'&&!c.reading&&c.kind==='seat')||(f==='fixed'&&k==='fixed')}
function draw(){const x=th();$('plan').src=x.image;const [w,h]=x.size;const svg=$('cells');svg.setAttribute('viewBox',`0 0 ${w} ${h}`);
$('map').style.width=(w*zoom/2)+'px';$('map').style.height=(h*zoom/2)+'px';svg.replaceChildren();
x.cells.forEach((c,i)=>{const r=document.createElementNS(NS,'rect');const [x0,y0,x1,y1]=c.bbox;
r.setAttribute('x',x0);r.setAttribute('y',y0);r.setAttribute('width',x1-x0);r.setAttribute('height',y1-y0);
r.dataset.i=i;r.setAttribute('class',cls(c)+(sel===i?' sel':''));svg.append(r)});
list=x.cells.map((c,i)=>i).filter(i=>matches(x.cells[i]));count()}
function count(){const x=th();const sev=x.cells.filter(c=>c.severe).length,unread=x.cells.filter(c=>c.kind==='seat'&&!c.reading).length;
const done=x.cells.filter(c=>labels[c.id]&&labels[c.id].status==='reviewed').length;const pos=list.indexOf(sel);
$('count').textContent=`${pos>=0?pos+1:'-'} / ${list.length} · 경고 ${sev} · 안 읽힘 ${unread} · 검토함 ${done}`}
function show(i){sel=i;const x=th(),c=x.cells[i];const [x0,y0,x1,y1]=c.bbox,k=3,box=$('zoom');const bw=box.clientWidth||340,bh=220;
const cx=(x0+x1)/2,cy=(y0+y1)/2;box.style.backgroundImage=`url(${x.image})`;box.style.backgroundSize=`${x.size[0]*k}px auto`;
box.style.backgroundPosition=`${bw/2-cx*k}px ${bh/2-cy*k}px`;const zb=$('zoombox');zb.style.width=(x1-x0)*k+'px';zb.style.height=(y1-y0)*k+'px';
zb.style.left=(bw/2-(cx-x0)*k)+'px';zb.style.top=(bh/2-(cy-y0)*k)+'px';
$('where').textContent=c.id+(c.kind==='region'?' · 파란 영역 (구조 검사 대상 아님)':'');$('reading').textContent=describe(c.reading);
$('source').textContent=c.source||'-';$('ocr').textContent=c.kind==='region'?'해당 없음':describe(c.ocr);
$('flags').replaceChildren(...(c.flags.length?c.flags:['없음']).map(f=>{const li=document.createElement('li');li.textContent=REASONS[f]||f;return li}));
const l=labels[c.id]||{};const base=l.status?l:(c.reading||{});for(const f of fields)$(f).value=base[f]??'';
draw();const r=$('cells').children[i];if(r&&r.scrollIntoView)r.scrollIntoView({block:'center',inline:'center'})}
function step(d){if(!list.length)return;const pos=list.indexOf(sel);const n=pos<0?(d>0?0:list.length-1):(pos+d+list.length)%list.length;show(list[n])}
function store(fromReading){if(sel===null)return;const c=th().cells[sel];const l={status:'reviewed'};
if(fromReading&&c.reading){for(const f of ['is_seat','zone','row','number'])if(c.reading[f])l[f]=String(c.reading[f])}
else{for(const f of fields){const v=$(f).value.trim();if(v)l[f]=v}}
if(!l.is_seat){$('error').textContent='좌석 여부를 고르세요.';return}$('error').textContent='';labels[c.id]=l;persist();step(1)}
$('cells').onclick=e=>{if(e.target.dataset&&e.target.dataset.i!==undefined)show(+e.target.dataset.i)};
$('accept').onclick=()=>store(true);$('save').onclick=()=>store(false);
$('clear').onclick=()=>{if(sel===null)return;delete labels[th().cells[sel].id];persist();show(sel)};
$('prev').onclick=()=>step(-1);$('next').onclick=()=>step(1);$('filter').onchange=e=>{e.target.blur();draw()};
$('theatre').onchange=e=>{e.target.blur();t=+e.target.value;sel=null;draw()};
$('zoomin').onclick=()=>{zoom=Math.min(6,zoom+1);draw()};$('zoomout').onclick=()=>{zoom=Math.max(1,zoom-1);draw()};
$('export').onclick=()=>{const samples=Object.entries(labels).map(([sample_id,label])=>({sample_id,label}));
const out={schema_version:1,kind:'map-review',created:data.created,sources:data.sources,compare:data.compare,samples};
const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(out,null,2)],{type:'application/json'}));a.download='map-review-result.json';a.click()};
$('import').onchange=async e=>{try{const r=JSON.parse(await e.target.files[0].text());if(r.kind!=='map-review')throw Error('전체 도면 검토 결과 파일이 아닙니다.');
for(const s of r.samples)labels[s.sample_id]=s.label;persist();$('error').textContent='';draw()}catch(err){$('error').textContent=err.message}};
document.onkeydown=e=>{if(['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName))return;if(e.key==='n')step(1);if(e.key==='p')step(-1)};
data.theatres.forEach((x,i)=>{const o=document.createElement('option');o.value=i;o.textContent=x.name;$('theatre').append(o)});
if(!data.theatres.some(x=>x.cells.some(c=>c.severe)))$('filter').value='unread';
draw();
</script></html>'''


def write_page(output, theatres, sources, compare, created):
    data = {'schema_version': 1, 'created': created, 'sources': sources, 'compare': compare, 'zones': ZONES,
            'theatres': theatres}
    options = ''.join(f'<option value="{z}">{z}</option>' for z in ZONES)
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')
    (output/'map-review.html').write_text(PAGE.replace('__ZONES__', options).replace('__DATA__', payload),
                                         encoding='utf-8')


def main():
    from datetime import datetime, timezone
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output-dir', type=Path, default=BASE/'output/phase-abc')
    parser.add_argument('--theatre', action='append', help='Theatre folder; default: theatre-2 and theatre-3')
    parser.add_argument('--source', action='append', help='As in check_seatmap.py; default: ocr')
    parser.add_argument('--compare', help='Second reader to cross-check, normally "ocr"')
    parser.add_argument('--expect', action='append', metavar='THEATRE:KEY=N')
    args = parser.parse_args()
    sources, expect = args.source or ['ocr'], parse_expect(args.expect)
    theatres = [build_theatre(args.output_dir, t, sources, args.compare, expect.get(t))
                for t in args.theatre or ['theatre-2', 'theatre-3']]
    created = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    write_page(args.output_dir, theatres, sources, args.compare, created)
    for t in theatres:
        s = t['summary']
        print(f"{t['name']}: {len(t['cells'])} cells, {s['severe_cells']} severe, {s['by_reason'].get('unread', 0)} unread")
    print(args.output_dir/'map-review.html')


if __name__ == '__main__':
    main()
