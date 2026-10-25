import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
// Run against a generated review directory; edits stay in the in-memory DOM.
const base=path.resolve(process.argv[2] ?? 'experiments/seatmap-pdf/output/phase-abc');
const html=fs.readFileSync(base+'/review.html','utf8');
const elements=new Map();
function element(){return {value:'',hidden:false,children:[],append(...items){this.children.push(...items)},replaceChildren(){this.children=[]},removeAttribute(k){delete this[k]},click(){}}}
for(const [,id] of html.matchAll(/id="([^"]+)"/g))elements.set(id,element());
let exported;
const context=vm.createContext({document:{getElementById:id=>elements.get(id),createElement:element},Blob,URL:{createObjectURL:b=>{exported=b;return 'blob:test'},revokeObjectURL(){}},setTimeout:f=>f()});
vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);
const $=id=>elements.get(id);
const template=JSON.parse(fs.readFileSync(base+'/review-template.json','utf8'));
assert.equal($('pick').children.length,template.samples.length);
assert.ok(html.includes('<details id="prediction-details"><summary>상세 정보 보기</summary>'));
const summary=()=>Object.fromEntries($('prediction-summary').children.reduce((rows,item,i,all)=>i%2===0?[...rows,[item.textContent,all[i+1].textContent]]:rows,[]));
const examples={};

for(let i=0;i<template.samples.length;i++){
  $('pick').onchange({target:{value:String(i)}});
  const s=template.samples[i],p=s.prediction,shown=summary(),blue=s.kind==='accessibility_or_blue_region';
  assert.equal(shown['도면명'],s.document);
  assert.equal(shown['검토 대상 ID'],s.sample_id);
  assert.equal(shown[blue?'영역 후보 ID':s.unit==='pt'?'추출 후보 ID':'좌석 후보 ID'],p.candidate_id);
  assert.equal(shown['예측 좌석 ID'],blue?'해당 없음 (개별 좌석 아님)':p.seat_id??'미매칭');
  assert.equal(shown['매칭 상태'],blue?'해당 없음 (개별 좌석 연결 대상 아님)':p.seat_id?'연결됨 (미검증)':'미매칭');
  assert.equal(shown[s.unit==='pt'?'추출 문자':'OCR 문자'],p.text?.trim()?p.text:blue?'해당 없음 (영역 후보)':'인식되지 않음');
  for(const [field,label] of [['block','예측 블록·구역'],['row','예측 행'],['number','예측 번호']]){
    assert.equal(shown[label],p[field]==null?undefined:String(p[field]));
  }
  assert.equal(Boolean(shown[blue?'영역 설명':'미매칭 사유']),Boolean(p.reason));
  const category=blue?'blue':s.unit==='pt'?'PDF':p.seat_id?'JPEG matched':p.text?'JPEG unmatched':'OCR missing';
  examples[category]??=shown;

  assert.equal($('crop').src,s.crop);
  assert.ok(fs.existsSync(path.join(base,$('crop').src)));
  assert.equal($('context').hidden,false);
  assert.equal($('jpeg-context-description').hidden,s.unit==='pt');
  assert.equal($('pdf-context-description').hidden,s.unit!=='pt');
  if(s.unit==='px')assert.match($('context-note').textContent,/미검증 예측/);
  assert.equal($('crop-link').href,s.crop);
  assert.equal($('current-sample').textContent,`${i+1} / ${template.samples.length} · ${s.document}`);
  assert.equal($('shape_correct').disabled,!s.shape_detection_attempted);
  assert.ok(fs.existsSync(path.join(base,$('context-image').src)));
}
$('pick').onchange({target:{value:'0'}});
const initialReviewed=template.samples.filter(s=>s.review.status==='reviewed').length;
assert.equal($('progress').value,initialReviewed);
assert.equal($('progress').max,template.samples.length);
for(const f of ['shape_correct','text_correct','identity_correct']){
 assert.equal($(f).value,template.samples[0].review[f]===null?'':String(template.samples[0].review[f]));
 assert.match($(f).innerHTML,/판단 안 함·해당 없음/);
}
$('status').value='reviewed';$('identity_correct').value='false';$('notes').value='isolated smoke test';$('block').value='correction';
$('status').onchange();
assert.equal($('progress').value,initialReviewed+(template.samples[0].review.status==='reviewed'?0:1));
$('crop').onclick({target:{getBoundingClientRect:()=>({left:10,top:20,width:200,height:100}),naturalWidth:400,naturalHeight:200},clientX:110,clientY:70});
const expected=[template.samples[0].crop_origin[0]+200/template.samples[0].render_scale,template.samples[0].crop_origin[1]+100/template.samples[0].render_scale];
$('next').onclick();$('prev').onclick();
assert.equal($('notes').value,'isolated smoke test');
$('export').onclick();
const saved=JSON.parse(await exported.text());
assert.equal(saved.samples[0].review.identity_correct,false);
assert.equal(saved.samples[0].review.status,'reviewed');
assert.equal(saved.samples[0].review.correction.block,'correction');
assert.equal(saved.samples.length,template.samples.length);
assert.deepEqual(saved.samples.map(s=>s.prediction),template.samples.map(s=>s.prediction));
assert.deepEqual(saved.samples[0].review.expected_center,expected);
assert.deepEqual(Object.keys(saved.samples[0]),Object.keys(template.samples[0]));
assert.equal(saved.schema_version,1);
assert.ok(!('contexts' in saved));
saved.samples[0].review.notes='import test';
await $('import').onchange({target:{files:[{text:async()=>JSON.stringify(saved)}]}});
assert.equal($('notes').value,'import test');
assert.equal(summary()['예측 좌석 ID'],template.samples[0].prediction.seat_id);
assert.equal($('error').textContent,'');
$('clear').onclick();$('export').onclick();
assert.equal(JSON.parse(await exported.text()).samples[0].review.expected_center,null);
for(const doc of ['theatre-2','theatre-3']){
 const i=template.samples.findIndex(s=>s.document===doc);
 $('pick').onchange({target:{value:String(i)}});
 $('status').value='uncertain';$('notes').value='JPEG round trip '+doc;
 $('crop').onclick({target:{getBoundingClientRect:()=>({left:0,top:0,width:100,height:100}),naturalWidth:200,naturalHeight:200},clientX:50,clientY:50});
 $('export').onclick();
 const result=JSON.parse(await exported.text());
 assert.equal(result.samples[i].review.notes,'JPEG round trip '+doc);
 assert.deepEqual(result.samples[i].review.expected_center,[template.samples[i].crop_origin[0]+100,template.samples[i].crop_origin[1]+100]);
 assert.deepEqual(Object.keys(result.samples[i]),Object.keys(template.samples[i]));
 result.samples[i].review.notes='JPEG imported '+doc;
 await $('import').onchange({target:{files:[{text:async()=>JSON.stringify(result)}]}});
 assert.equal($('notes').value,'JPEG imported '+doc);
 assert.equal($('jpeg-context-description').hidden,false);
}
assert.deepEqual(Object.keys(examples).sort(),['PDF','JPEG matched','JPEG unmatched','OCR missing','blue'].sort());
$('export').onclick();
const allStatuses=JSON.parse(await exported.text());
allStatuses.samples[0].review.status='reviewed';
allStatuses.samples[1].review.status='uncertain';
allStatuses.samples[2].review.status='pending';
await $('import').onchange({target:{files:[{text:async()=>JSON.stringify(allStatuses)}]}});
const count=status=>allStatuses.samples.filter(s=>s.review.status===status).length;
assert.equal($('progress-counts').textContent,`검토 완료 ${count('reviewed')} · 미검토 ${count('pending')} · 판단 불가 ${count('uncertain')} / 전체 ${template.samples.length}`);
assert.equal($('progress').value,count('reviewed'));
await $('import').onchange({target:{files:[{text:async()=>'{'}]}});
assert.match($('error').textContent,/JSON 형식을 읽을 수 없습니다/);
await $('import').onchange({target:{files:[{text:async()=>'{}'}]}});
assert.match($('error').textContent,/검토 파일/);
$('missed').value='{}';$('export').onclick();
assert.match($('error').textContent,/JSON 배열이어야 합니다/);
$('missed').value='[]';
assert.ok(html.includes('<option value="pending">미검토</option>'));
assert.ok(html.includes('<option value="reviewed">검토 완료</option>'));
assert.ok(html.includes('<option value="uncertain">판단 불가</option>'));
assert.ok(html.includes('<details id="corrections-details">'));
assert.ok(html.includes('@media(max-width:800px)'));
console.log(JSON.stringify({examples,samples:template.samples.length,pdfContexts:template.samples.filter(s=>s.unit==='pt').length,passed:['sample navigation and asset paths','PDF and JPEG context switching','field applicability','position mapping and clear','navigation persistence','JSON schema unchanged','export/import round trip'],limitation:'DOM harness, not a real browser rendering test'},null,2));
