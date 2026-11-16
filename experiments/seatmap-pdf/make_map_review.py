"""Build a whole-map review page: every detected cell drawn on the plan, colored by the structure check.

The page shows each theatre's plan with all gray seat cells and blue regions.
By default it lists only the cells that need a person: cells the structure check
(check_seatmap.py) flags are red, unread cells amber, reviewed cells green, and
clean cells are left unmarked. Clicking a cell shows a zoomed view, the primary
reading, the OCR reading and why it needs checking, and lets the reviewer
confirm or correct it.

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


PAGE = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>좌석 도면 검토</title>
<style>
:root{--bg:#f4f3ef;--panel:#fff;--ink:#1c232b;--muted:#6a717b;--line:#e3e1db;--soft:#efede8;
--todo:#c97f00;--warn:#cf3a30;--done:#2f8a57;--region:#0b2a66}
*{box-sizing:border-box}html,body{height:100%}
body{margin:0;display:flex;flex-direction:column;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,-apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif}
button,select,input,textarea{font:inherit;color:inherit}
header{display:flex;align-items:center;gap:20px;padding:10px 20px;background:var(--panel);border-bottom:1px solid var(--line);flex-wrap:wrap}
h1{font-size:16px;margin:0;font-weight:700;letter-spacing:-.01em}
.seg{display:flex;gap:2px;background:var(--soft);padding:3px;border-radius:8px}
.seg button{border:0;background:transparent;padding:4px 12px;border-radius:6px;color:var(--muted);cursor:pointer;white-space:nowrap}
.seg button small{margin-left:6px;font-size:11px;color:var(--muted)}
.seg button[aria-pressed=true]{background:var(--panel);color:var(--ink);font-weight:600;box-shadow:0 1px 2px rgba(0,0,0,.08)}
.progress{display:flex;align-items:center;gap:12px;flex:1;min-width:240px}
.progress b{font-variant-numeric:tabular-nums}
.bar{width:160px;height:6px;background:var(--soft);border-radius:3px;overflow:hidden}.bar i{display:block;height:100%;width:0;background:var(--done);transition:width .2s}
.btn{border:1px solid var(--line);background:var(--panel);padding:7px 14px;border-radius:8px;cursor:pointer}
.btn.primary{background:var(--ink);border-color:var(--ink);color:#fff;font-weight:600}
.btn:focus-visible,.seg button:focus-visible{outline:2px solid #4b7bd1;outline-offset:1px}
#import{display:none}#ioerror{color:var(--warn);font-size:13px}
.app{flex:1;min-height:0;display:grid;grid-template-columns:minmax(0,1fr) 380px;gap:16px;padding:16px 20px}
.mappane{display:flex;flex-direction:column;min-height:0;background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.tools{display:flex;align-items:center;gap:16px;padding:8px 12px;border-bottom:1px solid var(--line);flex-wrap:wrap}
.legend{display:flex;gap:14px;flex-wrap:wrap;color:var(--muted);font-size:12px;flex:1}
.legend span{display:inline-flex;align-items:center;gap:5px}.legend i{width:12px;height:12px;border:2px solid;border-radius:2px}
.zoomctl{display:flex;gap:4px}.zoomctl button{width:32px;height:28px;border:1px solid var(--line);background:var(--panel);border-radius:6px;cursor:pointer}
.zoomctl button.fit{width:auto;padding:0 10px;font-size:12px}
#mapwrap{flex:1;min-height:0;overflow:auto;padding:16px}
#map{position:relative;margin:0 auto}#map img,#map svg{position:absolute;inset:0;width:100%;height:100%}
#cells rect{fill:transparent;stroke:transparent;stroke-width:6;cursor:pointer}
#cells rect.ok:hover{stroke:#8b929b}
#cells rect.todo{stroke:var(--todo);stroke-dasharray:10 6;fill:rgba(201,127,0,.16)}
#cells rect.warn{stroke:var(--warn);stroke-width:8;fill:rgba(207,58,48,.26)}
#cells rect.done{stroke:var(--done);fill:rgba(47,138,87,.22)}
#cells rect.region{stroke:var(--region);stroke-width:10;stroke-dasharray:14 6}
#cells rect.dim{opacity:.35}
#cells rect.sel{stroke:#111;stroke-width:14;stroke-dasharray:none;opacity:1}
aside{min-height:0;overflow:auto;display:flex;flex-direction:column;gap:12px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px}
.chip{display:inline-block;font-size:12px;font-weight:600;padding:1px 9px;border-radius:999px;background:var(--soft);color:#555}
.chip.warn{background:#fbe4e2;color:#a3241c}.chip.todo{background:#fbefd5;color:#7f5000}.chip.done{background:#dcefe3;color:#1d6a3f}.chip.region{background:#e0e6f2;color:var(--region)}
h2{font-size:20px;margin:6px 0 12px;letter-spacing:-.01em}
#zoom{height:200px;border-radius:8px;background-color:#fafaf8;background-repeat:no-repeat;border:1px solid var(--line);position:relative;overflow:hidden;image-rendering:pixelated}
#zoombox{position:absolute;border:2px solid #111;border-radius:2px;pointer-events:none}
.reads{display:grid;grid-template-columns:84px 1fr;gap:6px 10px;margin:14px 0 0}.reads dt{color:var(--muted)}.reads dd{margin:0;font-weight:500}
.why{margin-top:14px;padding:10px 12px;background:#fdf2f1;border-left:3px solid var(--warn);border-radius:0 6px 6px 0}
.why strong{font-size:13px}.why ul{margin:4px 0 0 18px;padding:0}
form h3{font-size:14px;margin:0 0 12px}
.field{display:block;margin-bottom:12px}.field>span{display:block;font-size:12px;color:var(--muted);margin-bottom:4px}
.field input,.field select,.field textarea{width:100%;padding:7px 9px;border:1px solid #d4d1ca;border-radius:6px;background:#fff}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.link{border:0;background:none;color:var(--muted);text-decoration:underline;cursor:pointer;padding:0;margin-left:auto}
#error{color:var(--warn);font-size:13px;margin:8px 0 0}#error:empty{display:none}
.hint{color:var(--muted);font-size:12px;margin:12px 0 0}
kbd{font:11px ui-monospace,Consolas,monospace;border:1px solid #d4d1ca;border-bottom-width:2px;border-radius:4px;padding:0 5px;background:#faf9f6;color:var(--ink)}
details{color:var(--muted);font-size:12px}details summary{cursor:pointer}details dl{display:grid;grid-template-columns:70px 1fr;gap:2px 8px;margin:8px 0 0}details dd{margin:0;word-break:break-all}
#empty h2{font-size:17px}#empty p{color:var(--muted);margin:0}
[hidden]{display:none!important}
.mappane,.legend{min-width:0}
@media(max-width:900px){body{height:auto}header{gap:10px 14px;padding:10px 16px}.app{grid-template-columns:minmax(0,1fr);padding:12px 16px}
.legend{order:3;flex-basis:100%}#mapwrap{height:60vh;flex:none}aside{overflow:visible}}
</style>
<header>
<h1>좌석 도면 검토</h1>
<div class="seg" id="theatres"></div>
<div class="progress"><span>확인할 칸 <b id="need">0</b>개 중 <b id="done">0</b>개 끝</span><span class="bar"><i id="bar"></i></span><span id="warncount" class="chip warn" hidden></span></div>
<span id="ioerror"></span>
<label class="btn" for="import">불러오기</label><input id="import" type="file" accept=".json">
<button class="btn primary" id="export">결과 파일로 저장</button>
</header>
<main class="app">
<section class="mappane">
<div class="tools">
<div class="seg" id="filters"><button data-f="todo">확인할 칸</button><button data-f="done">검토한 칸</button><button data-f="all">모든 칸</button></div>
<div class="legend"><span><i style="border-color:var(--warn);background:rgba(207,58,48,.26)"></i>경고</span><span><i style="border-color:var(--todo);border-style:dashed"></i>안 읽힘</span><span><i style="border-color:var(--done);background:rgba(47,138,87,.22)"></i>검토 끝</span><span><i style="border-color:var(--region);border-style:dashed"></i>휠체어 영역</span><span>문제없는 칸은 표시 안 함</span></div>
<div class="zoomctl"><button id="zoomout" title="축소">−</button><button id="zoomfit" class="fit">맞춤</button><button id="zoomin" title="확대">+</button></div>
</div>
<div id="mapwrap"><div id="map"><img id="plan" alt="좌석 도면"><svg id="cells"></svg></div></div>
</section>
<aside>
<div class="card" id="empty" hidden><h2 id="emptytitle"></h2><p id="emptytext"></p></div>
<div class="card" id="detail" hidden>
<span id="chip" class="chip"></span><h2 id="title"></h2>
<div id="zoom"><div id="zoombox"></div></div>
<dl class="reads"><dt id="srcname">모델</dt><dd id="reading"></dd><dt>OCR</dt><dd id="ocr"></dd></dl>
<div class="why" id="why" hidden><strong>확인이 필요한 이유</strong><ul id="flags"></ul></div>
</div>
<form class="card" id="form" hidden>
<h3>맞는 값</h3>
<label class="field"><span>좌석 한 칸인가요?</span><select id="is_seat"><option value="">선택</option><option value="yes">예, 좌석 한 칸</option><option value="no">아니요 (글자·영역·기타)</option><option value="unsure">잘 모르겠음</option></select></label>
<label class="field"><span>구역</span><select id="zone"><option value="">선택</option></select></label>
<div class="pair"><label class="field"><span>행 <small>(BOX석은 비움)</small></span><input id="row" maxlength="8" autocomplete="off"></label>
<label class="field"><span>좌석 번호</span><input id="number" maxlength="12" autocomplete="off"></label></div>
<label class="field"><span>메모</span><textarea id="notes" rows="2"></textarea></label>
<div class="actions"><button class="btn primary" type="submit">저장하고 다음 칸</button><kbd>Enter</kbd><button type="button" class="link" id="clear">검토 취소</button></div>
<p id="error"></p>
<p class="hint"><kbd>n</kbd> 다음 칸 · <kbd>p</kbd> 이전 칸 · 값이 맞으면 그대로 저장하면 돼요.</p>
</form>
<details class="card"><summary>세부 정보</summary><dl><dt>칸 ID</dt><dd id="cid">-</dd><dt>판독 출처</dt><dd id="source">-</dd><dt>판독 파일</dt><dd id="sources"></dd></dl></details>
</aside>
</main>
<script>
const data=__DATA__;const KEY='map-review-v1';const fields=['is_seat','zone','row','number','notes'];
const REASONS={incomplete:'번호나 구역이 비어 있음',not_a_seat:'회색 좌석 칸인데 좌석이 아니라고 읽음',
duplicate_id:'같은 좌석 번호가 다른 칸에도 있음',out_of_order:'줄 안에서 번호 순서가 칸 위치와 어긋남',
adjacent_jump:'옆 칸과의 번호 차이가 이 줄의 보통 간격과 다름',row_misaligned:'칸이 자기 줄에서 벗어나 있음',
row_letter_order:'행 글자가 위아래 순서와 어긋남',reader_disagreement:'모델과 OCR이 다르게 읽음'};
const ZONE_NAMES={main:'일반석',OP:'OP석','BOX-1':'BOX-1','BOX-2':'BOX-2',other:'기타'};
const SOURCE_NAMES={'subagent-preread':'Opus 모델',ocr:'OCR'};
const STATES={done:'검토 끝',region:'휠체어 영역',warn:'경고',todo:'안 읽힘',ok:'문제없음'};
const ZOOMS=[1,1.5,2,3,4];
const $=id=>document.getElementById(id);const NS='http://www.w3.org/2000/svg';
let labels={};try{labels=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){labels={}}
let t=0,sel=null,zoom=0,filter='todo',list=[];
function persist(){try{localStorage.setItem(KEY,JSON.stringify(labels))}catch(e){}}
const th=()=>data.theatres[t];
const theatreName=n=>n.replace('theatre-','극장 ');
const sourceName=s=>!s?'-':SOURCE_NAMES[s]||(s.endsWith('.json')?'검토 결과':s);
const reviewed=c=>!!(labels[c.id]&&labels[c.id].status==='reviewed');
const needs=c=>c.kind==='seat'&&(c.severe||!c.reading);
function place(r){const z=r.zone?ZONE_NAMES[r.zone]||r.zone:'';return [z,r.row?r.row+'열':'',r.number?r.number+'번':''].filter(Boolean).join(' ')||'위치 정보 없음'}
function describe(r){if(!r)return '없음';if(r.is_seat!=='yes')return '좌석 아님'+(r.number?' (글자 '+r.number+')':'');return place(r)}
function state(c){if(reviewed(c))return 'done';if(c.kind==='region')return 'region';if(c.severe)return 'warn';if(!c.reading)return 'todo';return 'ok'}
function matches(c){return filter==='all'||(filter==='done'&&reviewed(c))||(filter==='todo'&&needs(c)&&!reviewed(c))}
function scale(){const w=th().size[0];const fit=Math.max(.1,($('mapwrap').clientWidth-32)/w);return fit*ZOOMS[zoom]}
function draw(){const x=th(),[w,h]=x.size,s=scale();if($('plan').getAttribute('src')!==x.image)$('plan').src=x.image;
const svg=$('cells');svg.setAttribute('viewBox','0 0 '+w+' '+h);$('map').style.width=w*s+'px';$('map').style.height=h*s+'px';svg.replaceChildren();
x.cells.forEach((c,i)=>{const r=document.createElementNS(NS,'rect');const [x0,y0,x1,y1]=c.bbox;
r.setAttribute('x',x0);r.setAttribute('y',y0);r.setAttribute('width',x1-x0);r.setAttribute('height',y1-y0);r.dataset.i=i;
r.setAttribute('class',state(c)+(matches(c)||c.kind==='region'?'':' dim')+(sel===i?' sel':''));svg.append(r)});
list=x.cells.map((c,i)=>i).filter(i=>matches(x.cells[i]));progress()}
function progress(){const x=th();const need=x.cells.filter(needs);const done=need.filter(reviewed).length;
$('need').textContent=need.length;$('done').textContent=done;$('bar').style.width=(need.length?done/need.length*100:100)+'%';
const warn=x.cells.filter(c=>c.severe&&!reviewed(c)).length;$('warncount').hidden=!warn;$('warncount').textContent='경고 '+warn;
[...$('theatres').children].forEach((b,i)=>{const left=data.theatres[i].cells.filter(c=>needs(c)&&!reviewed(c)).length;
b.querySelector('small').textContent=left?left:'✓';b.setAttribute('aria-pressed',String(i===t))});
[...$('filters').children].forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.f===filter)))}
function showEmpty(){sel=null;draw();$('detail').hidden=true;$('form').hidden=true;$('empty').hidden=false;$('cid').textContent='-';$('source').textContent='-';
const all=filter==='todo';$('emptytitle').textContent=all?'확인할 칸을 다 봤어요':'이 목록은 비어 있어요';
$('emptytext').textContent=all?'‘결과 파일로 저장’을 눌러 검토 결과를 받아 두세요. 다른 극장도 위에서 고를 수 있어요.':'‘모든 칸’에서 아무 칸이나 눌러 볼 수 있어요.'}
function show(i){sel=i;const x=th(),c=x.cells[i];$('empty').hidden=true;$('detail').hidden=false;$('form').hidden=false;
const st=state(c);$('chip').className='chip '+st;$('chip').textContent=STATES[st];
const l=labels[c.id];const known=reviewed(c)?l:c.reading;
$('title').textContent=c.kind==='region'?'파란 휠체어 영역':known?describe(known):c.ocr?describe(c.ocr)+' (OCR 추정)':'아직 모르는 칸';
const [x0,y0,x1,y1]=c.bbox,k=3,box=$('zoom'),bw=box.clientWidth||346,bh=box.clientHeight||200,cx=(x0+x1)/2,cy=(y0+y1)/2;
box.style.backgroundImage='url('+x.image+')';box.style.backgroundSize=x.size[0]*k+'px auto';box.style.backgroundPosition=(bw/2-cx*k)+'px '+(bh/2-cy*k)+'px';
const zb=$('zoombox');zb.style.width=(x1-x0)*k+'px';zb.style.height=(y1-y0)*k+'px';zb.style.left=(bw/2-(cx-x0)*k)+'px';zb.style.top=(bh/2-(cy-y0)*k)+'px';
$('srcname').textContent=c.reading?sourceName(c.source):'모델';$('reading').textContent=c.reading?describe(c.reading):'아직 안 읽음';
$('ocr').textContent=c.kind==='region'?'해당 없음':c.ocr?describe(c.ocr):'못 읽음';
const why=c.flags.filter(f=>f!=='unread');$('why').hidden=!why.length;
$('flags').replaceChildren(...why.map(f=>{const li=document.createElement('li');li.textContent=REASONS[f]||f;return li}));
$('cid').textContent=c.id;$('source').textContent=c.source||'-';
const base=l&&l.status?l:(c.reading||{});for(const f of fields)$(f).value=base[f]??'';$('error').textContent='';$('clear').hidden=!reviewed(c);
draw();const r=$('cells').children[i];if(r&&r.scrollIntoView)r.scrollIntoView({block:'center',inline:'center'})}
function step(d){if(!list.length){showEmpty();return}const pos=list.indexOf(sel);let n;
if(pos>=0)n=list[(pos+d+list.length)%list.length];
else if(sel!==null)n=d>0?list.find(i=>i>sel):[...list].reverse().find(i=>i<sel);
if(n===undefined)n=d>0?list[0]:list[list.length-1];show(n)}
function store(){if(sel===null)return;const c=th().cells[sel];const l={status:'reviewed'};
for(const f of fields){const v=$(f).value.trim();if(v)l[f]=v}
if(!l.is_seat){$('error').textContent='좌석 한 칸인지 먼저 골라 주세요.';$('is_seat').focus();return}
labels[c.id]=l;persist();draw();step(1)}
function start(){const warn=list.find(i=>th().cells[i].severe);if(warn!==undefined)show(warn);else step(1)}
function pickTheatre(i){t=i;sel=null;draw();start()}
function pickFilter(f){filter=f;draw();if(!list.includes(sel))step(1);else progress()}
function setZoom(z){zoom=Math.max(0,Math.min(ZOOMS.length-1,z));draw();const r=sel!==null&&$('cells').children[sel];if(r)r.scrollIntoView({block:'center',inline:'center'})}
$('cells').onclick=e=>{if(e.target.dataset&&e.target.dataset.i!==undefined)show(+e.target.dataset.i)};
$('form').onsubmit=e=>{e.preventDefault();store()};
$('clear').onclick=()=>{if(sel===null)return;delete labels[th().cells[sel].id];persist();show(sel)};
$('filters').onclick=e=>{const b=e.target.closest('button');if(b)pickFilter(b.dataset.f)};
$('zoomin').onclick=()=>setZoom(zoom+1);$('zoomout').onclick=()=>setZoom(zoom-1);$('zoomfit').onclick=()=>setZoom(0);
window.addEventListener('resize',()=>draw());
$('export').onclick=()=>{const samples=Object.entries(labels).map(([sample_id,label])=>({sample_id,label}));
const out={schema_version:1,kind:'map-review',created:data.created,sources:data.sources,compare:data.compare,samples};
const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(out,null,2)],{type:'application/json'}));a.download='map-review-result.json';a.click()};
$('import').onchange=async e=>{try{const r=JSON.parse(await e.target.files[0].text());if(r.kind!=='map-review')throw Error('전체 도면 검토 결과 파일이 아니에요.');
for(const s of r.samples)labels[s.sample_id]=s.label;persist();$('ioerror').textContent='';if(sel!==null)show(sel);else draw()}catch(err){$('ioerror').textContent=err.message}};
document.onkeydown=e=>{const tag=e.target.tagName;if(['INPUT','TEXTAREA','SELECT'].includes(tag))return;
if(e.key==='n'){e.preventDefault();step(1)}else if(e.key==='p'){e.preventDefault();step(-1)}
else if(e.key==='Enter'&&(e.target===document.body||e.target.closest('#mapwrap'))&&sel!==null){e.preventDefault();store()}};
data.theatres.forEach((x,i)=>{const b=document.createElement('button');b.type='button';b.append(theatreName(x.name));b.append(document.createElement('small'));b.onclick=()=>pickTheatre(i);$('theatres').append(b)});
data.zones.forEach(z=>{const o=document.createElement('option');o.value=z;o.textContent=ZONE_NAMES[z]||z;$('zone').append(o)});
$('sources').textContent=data.sources.join(', ')+(data.compare?' · 비교: '+data.compare:'');
draw();start();
</script></html>'''


def write_page(output, theatres, sources, compare, created):
    data = {'schema_version': 1, 'created': created, 'sources': sources, 'compare': compare, 'zones': ZONES,
            'theatres': theatres}
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')
    (output/'map-review.html').write_text(PAGE.replace('__DATA__', payload), encoding='utf-8')


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
