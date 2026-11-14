"""Build a prediction-blind review page for a seeded random subset of JPEG samples.

The page shows only the seat crop and plan context, never the OCR or model
prediction, so the reviewer's labels can later score both readers fairly.
"""
from pathlib import Path
import argparse
import json
import random

BASE = Path(__file__).resolve().parent
# Shared with claude_preread.py so human and model labels are directly comparable.
ZONES = ['main', 'BOX-1', 'BOX-2', 'OP', 'other']


def select_samples(review, count, seed):
    pool = sorted((s for s in review['samples'] if s['unit'] == 'px'), key=lambda s: s['sample_id'])
    if count > len(pool):
        raise ValueError(f'Requested {count} samples but only {len(pool)} JPEG samples exist')
    chosen = random.Random(seed).sample(pool, count)
    return [{'sample_id': s['sample_id'], 'document': s['document'], 'source_sha256': s['source_sha256'],
             'crop': s['crop'], 'context': f"review-contexts/{s['sample_id']}.png"} for s in chosen]


PAGE = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>좌석 블라인드 검토</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f5f6f7;color:#252a32;font:15px/1.6 system-ui,"Malgun Gothic",sans-serif}
main{max-width:1280px;margin:auto;padding:24px 16px 48px}h1{font-size:24px;margin:0}.muted{color:#626a75;font-size:13px}
.bar,.panel{background:#fff;border:1px solid #dce0e5;border-radius:10px;padding:16px;margin-top:16px}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.grow{flex:1;min-width:160px}
.grid{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr);gap:16px;align-items:start;margin-top:16px}
img{max-width:100%;height:auto;display:block;margin:auto}.frame{background:#fafafa;border:1px solid #e1e4e8;padding:8px}
#crop{image-rendering:pixelated;width:100%;max-width:360px}
button,.file{font:inherit;border:1px solid #cbd0d8;border-radius:6px;padding:8px 14px;background:#fff;cursor:pointer}
button.primary{background:#343d49;color:#fff;border-color:#343d49}input,select,textarea{font:inherit;width:100%;padding:8px;border:1px solid #cbd0d8;border-radius:6px}
label{display:block;font-weight:600;margin-bottom:12px}label span{display:block;font-weight:400;color:#626a75;font-size:13px}
#import{display:none}#error{color:#803c3c}@media(max-width:800px){.grid{grid-template-columns:1fr}}
</style>
<main><h1>좌석 블라인드 검토</h1>
<p class="muted">빨간 표시가 가리키는 칸 하나만 보고, 도면에 보이는 그대로 적으세요. 자동 판독 결과는 일부러 숨겼습니다. 자동 저장되지 않으니 ‘결과 저장’으로 받은 JSON을 보관하세요.</p>
<section class="bar"><div class="row"><div class="grow"><strong id="title"></strong><div id="progress" class="muted"></div></div>
<button id="prev">이전</button><button id="next">다음</button><button id="export" class="primary">결과 저장</button>
<label class="file" style="margin:0;font-weight:400">불러오기<input id="import" type="file" accept=".json"></label></div><p id="error"></p></section>
<div class="grid"><div class="panel"><div class="frame"><img id="context" alt="도면 전체와 검토 위치 표시"></div></div>
<div><div class="panel"><div class="frame"><img id="crop" alt="검토 위치 확대"></div></div>
<form class="panel" id="form">
<label>좌석 한 칸인가요?<select id="is_seat"><option value="">선택</option><option value="yes">예, 좌석 한 칸</option><option value="no">아니오 (라벨·영역·기타)</option><option value="unsure">판단 불가</option></select></label>
<label>구역<select id="zone"><option value="">선택</option>__ZONES__</select><span>main = BOX·OP가 아닌 일반 객석(1층·2층 모두)</span></label>
<label>행<input id="row" maxlength="8"><span>예: A, Q. OP석은 왼쪽 원 번호(1, 2). BOX석처럼 행이 없으면 비워 두세요.</span></label>
<label>좌석 번호(칸에 적힌 글자)<input id="number" maxlength="8"></label>
<label>메모<textarea id="notes" rows="2"></textarea></label>
<label style="font-weight:400"><input id="done" type="checkbox" style="width:auto"> 이 항목 검토 완료</label>
</form></div></div></main>
<script>
const data=__DATA__;const fields=['is_seat','zone','row','number','notes'];let i=0;const $=id=>document.getElementById(id);
for(const s of data.samples)s.label=s.label||{status:'pending'};
function show(){const s=data.samples[i];$('title').textContent=`${i+1} / ${data.samples.length} · ${s.sample_id}`;$('context').src=s.context;$('crop').src=s.crop;
for(const f of fields)$(f).value=s.label[f]??'';$('done').checked=s.label.status==='reviewed';progress();}
function progress(){const n=data.samples.filter(x=>x.label.status==='reviewed').length;$('progress').textContent=`검토 완료 ${n} / ${data.samples.length}`;}
function save(){const l={status:$('done').checked?'reviewed':'pending'};for(const f of fields){const v=$(f).value.trim();if(v)l[f]=v;}data.samples[i].label=l;}
$('form').oninput=()=>{save();progress()};$('form').onchange=()=>{save();progress()};$('prev').onclick=()=>{save();i=Math.max(0,i-1);show()};$('next').onclick=()=>{save();i=Math.min(data.samples.length-1,i+1);show()};
$('export').onclick=()=>{save();const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));a.download='blind-review-result.json';a.click();};
$('import').onchange=async e=>{try{const t=JSON.parse(await e.target.files[0].text());const m=new Map(t.samples.map(s=>[s.sample_id,s]));
for(const s of data.samples){const p=m.get(s.sample_id);if(!p||p.source_sha256!==s.source_sha256)throw Error('표본 목록이 일치하지 않습니다.');}
for(const s of data.samples)s.label=m.get(s.sample_id).label;$('error').textContent='';show();}catch(err){$('error').textContent=err.message}};
show();
</script></html>'''


def write_page(output, subset, seed):
    data = {'schema_version': 1, 'seed': seed, 'zones': ZONES,
            'sampling': 'Seeded random subset of JPEG review samples; predictions hidden from the reviewer.',
            'samples': subset}
    options = ''.join(f'<option value="{z}">{z}</option>' for z in ZONES)
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')
    (output/'blind-review.html').write_text(PAGE.replace('__ZONES__', options).replace('__DATA__', payload), encoding='utf-8')
    (output/'blind-review-samples.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=BASE/'output/phase-abc')
    parser.add_argument('--count', type=int, default=30)
    parser.add_argument('--seed', type=int, default=20261114)
    args = parser.parse_args()
    review = json.loads((args.output_dir/'review-template.json').read_text(encoding='utf-8'))
    subset = select_samples(review, args.count, args.seed)
    write_page(args.output_dir, subset, args.seed)
    print(args.output_dir/'blind-review.html')


if __name__ == '__main__':
    main()
