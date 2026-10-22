from pathlib import Path
import re
root=Path(__file__).resolve().parents[1]
replacements={
'도면에서 <span class="lime">구조를 읽고.</span>':'도면에서 <span class="lime">구조를 읽고</span>',
'VLM · OCR candidates':'VLM 공간 요소 후보 · OCR 좌석 문자',
'사람이 <span class="lime">실제 공간을 확인하고.</span>':'실제 공간을 <span class="lime">확인하고</span>',
'scale · floor · rail':'축척 · 단차 · 난간 높이 · 공연별 구조물',
'좌석의 <span class="lime">시야로 바꿉니다.</span>':'좌석의 <span class="lime">시야로 바꿉니다</span>',
'3D model · seat camera · sightline':'Three.js / WebGL · 좌석별 카메라 · 가림 계산',
'사람이 제공한 합성 실측 예시':'실제 치수·높이는 사람이 제공·검토',
'<div class="foot">저장 VLM 출력 + 합성 실측 입력 연결 실험 · 실시간 VLM 호출·현장 정확도 미검증</div>':'<div class="foot"><div style="color:#c7ef7b">가상 도면 20석 · AI 후보부터 3D 시야 계산까지 연결 확인</div><div style="font-size:22px;margin-top:7px">저장 VLM 출력 + 합성 실측 입력 실험 · 실시간 VLM 호출 아님 · 실제 공연장 정확도는 후속 검증 대상</div></div>'
}
for name in ['index.html','scripts/revise-hybrid.py']:
    p=root/name;s=p.read_text(encoding='utf-8');before=s
    for a,b in replacements.items():
        if a not in s:
            assert b in s,(name,a)
        s=s.replace(a,b)
    if name=='index.html':
        pattern=r'<section id="transformation".*?</section>'
        assert re.sub(pattern,'',before,flags=re.S)==re.sub(pattern,'',s,flags=re.S),'Unrelated scene changed'
    p.write_text(s,encoding='utf-8')
print('Technical copy updated. Other scenes and animation code unchanged.')
