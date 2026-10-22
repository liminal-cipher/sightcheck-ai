from pathlib import Path
import re
P=Path(__file__).resolve().parents[1]
s=(P/'capture/index-original-draft.html').read_text(encoding='utf-8')
# Preserve all unaffected scenes, typography, soundtrack and timing.
for name in ['hook-c','hook-d','compare-c','compare-d']:
 s=re.sub(r'(<div id="'+name+r'"[^>]*>)<img[^>]*>',r'\1',s)
s=s.replace('.picture{overflow:hidden;', '.picture{overflow:hidden;').replace('background:#191e25;position:absolute','background:transparent;position:absolute')
s=s.replace('</style>','''
#hybrid-canvas{position:absolute;inset:0;z-index:0}#hybrid-canvas canvas{width:1920px;height:1080px}
#hook .scene,#compare .scene,#calculation .scene,#transformation .scene,#performance .scene{background:transparent}
.hybrid-copy{position:absolute;left:96px;top:174px}.hybrid-copy h2{font-size:66px}.hybrid-copy p{font-size:25px;color:#aeb8ba;margin-top:20px;letter-spacing:.03em}
.measure{position:absolute;padding:12px 20px;border-left:3px solid #c7ef7b;background:#12161ce8;color:#f4f5f3;font-size:27px}
</style>''')
s=s.replace('<section id="hook"','<div id="hybrid-canvas" data-layout-ignore></div><section id="hook"',1)
def replace_scene(name,body):
 global s
 s=re.sub(r'<section id="'+name+r'".*?</section>',body,s,flags=re.S)
top='<div class="top"><span class="brand">시야체크 <b>AI</b></span><span>FROM PLAN TO PERSPECTIVE</span></div>'
replace_scene('calculation','''<section id="calculation" class="clip" data-start="13" data-duration="5" data-track-index="1"><div class="scene">'''+top+'''<div id="calc-title" class="hybrid-copy"><h2>그 자리에서, <span class="lime">가림의 원인까지.</span></h2><p>무대 표본과 등록 구조물의 교차 계산</p></div><div class="foot">가상 공연장 · 실제 엔진의 좌석 카메라와 가림 표본</div></div></section>''')
replace_scene('candidates','''<section id="transformation" class="clip" data-start="18" data-duration="16" data-track-index="1"><div class="scene">'''+top+'''
<div id="hybrid-draft" class="hybrid-copy"><h2>도면에서 <span class="lime">구조를 읽고</span></h2><p>VLM 공간 요소 후보 · OCR 좌석 문자</p></div>
<div id="hybrid-review" class="hybrid-copy"><h2>실제 공간을 <span class="lime">확인하고</span></h2><p>축척 · 단차 · 난간 높이 · 공연별 구조물</p></div>
<div id="hybrid-sight" class="hybrid-copy"><h2>좌석의 <span class="lime">시야로 바꿉니다</span></h2><p>Three.js / WebGL · 좌석별 카메라 · 가림 계산</p></div>
<div id="measure-width" class="measure" style="left:1270px;top:404px">무대 폭 · 8.60 m</div>
<div id="measure-floor" class="measure" style="left:1270px;top:468px">C3 바닥 · 2.40 m</div>
<div id="measure-rail" class="measure" style="left:1270px;top:532px">난간 높이 · 1.00 m</div>
<div id="measure-source" style="position:absolute;left:1270px;top:602px;font-size:23px;color:#c7ef7b">실제 치수·높이는 사람이 제공·검토</div>
<div id="seat-camera-label" class="pill" style="position:absolute;left:130px;top:378px">C3 · 눈높이 1.20m · 60°</div>
<div class="foot"><div style="color:#c7ef7b">가상 도면 20석 · AI 후보부터 3D 시야 계산까지 연결 확인</div><div style="font-size:22px;margin-top:7px">저장 VLM 출력 + 합성 실측 입력 실험 · 실시간 VLM 호출 아님 · 실제 공연장 정확도는 후속 검증 대상</div></div>
</div></section>''')
replace_scene('human','');replace_scene('engine','')
replace_scene('performance','''<section id="performance" class="clip" data-start="34" data-duration="8" data-track-index="1"><div class="scene">'''+top+'''<div id="performance-title" class="hybrid-copy"><h2>같은 공연장, <span class="lime">다른 공연.</span></h2><p>공연별 구조물이 바뀌면, 시야도 다시 계산.</p></div><div id="tower-before" class="pill" style="position:absolute;left:130px;top:378px">A2 · 기본 무대</div><div id="tower-after" class="pill" style="position:absolute;left:130px;top:378px">A2 · 라이브 / 촬영 타워</div><div class="foot">가상 배치 전환 예시 · 같은 좌석·눈높이·화각 · 설치물 등장 모션은 설명용</div></div></section>''')
# Remove only animations belonging to the replaced shots.
a=s.index('// calculation');b=s.index('// publish',a)
s=s[:a]+'''// revised Three.js mechanism
enter('#calc-title',13);
enter('#hybrid-draft',18);tl.to('#hybrid-draft',{opacity:0,y:-20,duration:.35,ease:EXIT},22.5);
enter('#hybrid-review',23);tl.to('#hybrid-review',{opacity:0,y:-20,duration:.35,ease:EXIT},27.5);
enter('#measure-width',23.3);enter('#measure-floor',23.5);enter('#measure-rail',23.7);enter('#measure-source',23.9);
tl.to(['#measure-width','#measure-floor','#measure-rail','#measure-source'],{opacity:0,duration:.35,ease:EXIT},27.5);
enter('#hybrid-sight',28);enter('#seat-camera-label',30.5);
enter('#performance-title',34);enter('#tower-before',34.2);tl.to('#tower-before',{opacity:0,duration:.35,ease:EXIT},35.65);enter('#tower-after',36.1);
'''+s[b:]
# Hook cameras supply the same movement; image scale tweens no longer have targets.
s=re.sub(r"tl.fromTo\('#hook-[cd] img'.*?;",'',s)
s=s.replace("window.__timelines['main']=tl;","tl.eventCallback('onUpdate',()=>window.renderHybrid?.(tl.time()));window.__timelines['main']=tl;")
s=s.replace('</body>','<script src="assets/hybrid-3d.js"></script></body>')
(P/'index.html').write_text(s,encoding='utf-8')
print('Targeted hybrid revision applied; original HTML and draft MP4 preserved.')
