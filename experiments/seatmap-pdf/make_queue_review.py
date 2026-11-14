"""Build a review page for the OCR/model disagreement queue and agreement spot checks.

Unlike the blind page, this one shows both readings: its purpose is to confirm or
correct non-blind items, not to measure accuracy. Selection is seeded:
every direct conflict, every spot check from compare_readings.py, and a random
draw from items where only the model answered.
"""
from pathlib import Path
import argparse
import json
import random

from make_blind_review import ZONES

BASE = Path(__file__).resolve().parent


def describe_ocr(reading):
    if reading is None:
        return '판독 실패 (답 없음)'
    if reading['is_seat'] != 'yes':
        return '좌석 한 칸 아님 (영역)'
    return f"{reading['zone']} · 행 {reading['row'] or '-'} · 번호 {reading['number']}"


def describe_model(reading):
    if reading['is_seat'] != 'yes':
        text = f"좌석 한 칸 아님 · 글자 {reading['number'] or '-'}"
    else:
        text = f"{reading['zone']} · 행 {reading['row'] or '-'} · 번호 {reading['number']}"
    extra = f" (확신: {reading['confidence']}{' · ' + reading['note'] if reading.get('note') else ''})"
    return text + extra


def select_items(comparison, model_only_count, seed):
    queue = comparison['review_queue']
    conflicts = [x for x in queue if x['ocr'] is not None]
    model_only = sorted((x for x in queue if x['ocr'] is None), key=lambda x: x['sample_id'])
    drawn = random.Random(seed).sample(model_only, min(model_only_count, len(model_only)))
    chosen = ([dict(x, group='conflict') for x in conflicts] + [dict(x, group='spot_check') for x in comparison['spot_checks']]
              + [dict(x, group='model_only') for x in drawn])
    random.Random(seed + 1).shuffle(chosen)
    return chosen


PAGE = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>판독 불일치 검토</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f5f6f7;color:#252a32;font:15px/1.6 system-ui,"Malgun Gothic",sans-serif}
main{max-width:1280px;margin:auto;padding:24px 16px 48px}h1{font-size:24px;margin:0}.muted{color:#626a75;font-size:13px}
.bar,.panel{background:#fff;border:1px solid #dce0e5;border-radius:10px;padding:16px;margin-top:16px}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.grow{flex:1;min-width:160px}
.grid{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr);gap:16px;align-items:start;margin-top:16px}
img{max-width:100%;height:auto;display:block;margin:auto}.frame{background:#fafafa;border:1px solid #e1e4e8;padding:8px}
#crop{image-rendering:pixelated;width:100%;max-width:360px}
.reading{display:grid;grid-template-columns:70px 1fr;gap:6px 12px;margin:0}.reading dt{color:#626a75}.reading dd{margin:0;font-weight:600;overflow-wrap:anywhere}
button,.file{font:inherit;border:1px solid #cbd0d8;border-radius:6px;padding:8px 14px;background:#fff;cursor:pointer}
button.primary{background:#343d49;color:#fff;border-color:#343d49}input,select,textarea{font:inherit;width:100%;padding:8px;border:1px solid #cbd0d8;border-radius:6px}
label{display:block;font-weight:600;margin-bottom:12px}label span{display:block;font-weight:400;color:#626a75;font-size:13px}
#fix{border-top:1px solid #e1e4e8;padding-top:12px}#import{display:none}#error{color:#803c3c}@media(max-width:800px){.grid{grid-template-columns:1fr}}
</style>
<main><h1>판독 불일치 검토</h1>
<p class="muted">빨간 표시가 가리키는 칸을 보고, 두 판독 중 무엇이 맞는지 고르세요. 둘 다 틀리면 정답을 적어 주세요. 자동 저장되지 않으니 ‘결과 저장’으로 받은 JSON을 보관하세요.</p>
<section class="bar"><div class="row"><div class="grow"><strong id="title"></strong><div id="progress" class="muted"></div></div>
<button id="prev">이전</button><button id="next">다음</button><button id="export" class="primary">결과 저장</button>
<label class="file" style="margin:0;font-weight:400">불러오기<input id="import" type="file" accept=".json"></label></div><p id="error"></p></section>
<div class="grid"><div class="panel"><div class="frame"><img id="context" alt="도면 전체와 검토 위치 표시"></div></div>
<div><div class="panel"><div class="frame"><img id="crop" alt="검토 위치 확대"></div>
<dl class="reading" style="margin-top:12px"><dt>OCR</dt><dd id="ocr"></dd><dt>Claude</dt><dd id="model"></dd></dl></div>
<form class="panel" id="form">
<label>어느 쪽이 맞나요?<select id="verdict"><option value="">선택</option><option value="both">둘 다 맞음</option><option value="model">Claude만 맞음</option><option value="ocr">OCR만 맞음</option><option value="neither">둘 다 틀림</option><option value="unsure">판단 불가</option></select>
<span>OCR이 ‘판독 실패’면 Claude가 맞을 때 ‘Claude만 맞음’을 고르세요.</span></label>
<div id="fix"><p class="muted" style="margin-top:0">‘둘 다 틀림’일 때만 정답을 적으세요.</p>
<label>좌석 한 칸인가요?<select id="is_seat"><option value="">-</option><option value="yes">예</option><option value="no">아니오</option></select></label>
<label>구역<select id="zone"><option value="">-</option>__ZONES__</select></label>
<label>행<input id="row" maxlength="8"></label><label>좌석 번호<input id="number" maxlength="8"></label></div>
<label>메모<textarea id="notes" rows="2"></textarea></label>
</form></div></div></main>
<script>
const data=__DATA__;const fields=['verdict','is_seat','zone','row','number','notes'];let i=0;const $=id=>document.getElementById(id);
for(const s of data.items)s.review=s.review||{};
function progress(){const n=data.items.filter(x=>x.review.verdict).length;$('progress').textContent=`판정 완료 ${n} / ${data.items.length}`;}
function show(){const s=data.items[i];$('title').textContent=`${i+1} / ${data.items.length} · ${s.sample_id}`;$('context').src=s.context;$('crop').src=s.crop;
$('ocr').textContent=s.ocr_text;$('model').textContent=s.model_text;for(const f of fields)$(f).value=s.review[f]??'';progress();}
function save(){const r={};for(const f of fields){const v=$(f).value.trim();if(v)r[f]=v;}data.items[i].review=r;}
$('form').oninput=()=>{save();progress()};$('form').onchange=()=>{save();progress()};
$('prev').onclick=()=>{save();i=Math.max(0,i-1);show()};$('next').onclick=()=>{save();i=Math.min(data.items.length-1,i+1);show()};
$('export').onclick=()=>{save();const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));a.download='queue-review-result.json';a.click();};
$('import').onchange=async e=>{try{const t=JSON.parse(await e.target.files[0].text());const m=new Map(t.items.map(s=>[s.sample_id,s]));
for(const s of data.items)if(!m.has(s.sample_id))throw Error('검토 목록이 일치하지 않습니다.');for(const s of data.items)s.review=m.get(s.sample_id).review||{};$('error').textContent='';show();}catch(err){$('error').textContent=err.message}};
show();
</script></html>'''


def write_page(output, chosen, seed):
    items = [{'sample_id': x['sample_id'], 'group': x['group'], 'crop': f"review-crops/{x['sample_id']}.png",
              'context': f"review-contexts/{x['sample_id']}.png", 'ocr': x['ocr'], 'model': x['model'],
              'ocr_text': describe_ocr(x['ocr']), 'model_text': describe_model(x['model'])} for x in chosen]
    data = {'schema_version': 1, 'seed': seed, 'items': items,
            'sampling': 'All direct conflicts, all agreement spot checks, seeded random draw of model-only answers.'}
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')
    options = ''.join(f'<option value="{z}">{z}</option>' for z in ZONES)
    (output/'queue-review.html').write_text(PAGE.replace('__ZONES__', options).replace('__DATA__', payload), encoding='utf-8')
    (output/'queue-review-items.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=BASE/'output/phase-abc')
    parser.add_argument('--model-only', type=int, default=20)
    parser.add_argument('--seed', type=int, default=20261114)
    args = parser.parse_args()
    comparison = json.loads((args.output_dir/'reading-comparison.json').read_text(encoding='utf-8'))
    chosen = select_items(comparison, args.model_only, args.seed)
    write_page(args.output_dir, chosen, args.seed)
    print(len(chosen), args.output_dir/'queue-review.html')


if __name__ == '__main__':
    main()
