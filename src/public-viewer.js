import './public-viewer.css';
import {validateModel,getSeats,getTarget,analyzeSightline} from './model.js';
import {VenueViewer} from './scene.js';
const app=document.querySelector('#app'),slug=new URLSearchParams(location.search).get('publication');
const esc=x=>String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let publication,model,seats,viewer,selected=0,comparison=null,targetId,eyeHeight=1.2,stopped=false;
const metric=kind=>fetch(`/api/v1/publications/${slug}/metrics`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind})}).catch(()=>{});
function announce(type,extra={}) {
  if(window.parent===window || !publication)return;
  for(const origin of new Set([location.origin,...publication.allowedOrigins]))window.parent.postMessage({namespace:'sightcheck',version:1,type,publicationId:slug,...extra},origin);
}
function stop(message) {
  stopped=true;viewer?.destroy();app.innerHTML=`<main class="unavailable"><span class="wordmark">시야체크.</span><h1>시야 안내를 준비하고 있습니다</h1><p>${esc(message)}</p><button id="retry">다시 확인</button></main>`;
  document.querySelector('#retry').onclick=()=>location.reload();announce('unavailable');
}
async function load() {
  if(!slug)return stop('공연기획자가 제공한 시야 안내 링크로 접속해 주세요.');
  app.innerHTML='<main class="unavailable"><span class="wordmark">시야체크.</span><p role="status">좌석 시야를 불러오고 있습니다.</p></main>';
  try {
    const res=await fetch(`/api/v1/publications/${encodeURIComponent(slug)}`),data=await res.json();if(!res.ok)throw new Error(data.error);
    publication=data.publication;model=validateModel(publication.model);seats=getSeats(model);targetId=model.activeTargetId;
    const param=new URLSearchParams(location.search).get('seat');if(param){const i=seats.findIndex(s=>s.label===param);if(i>=0)selected=i;}
    app.innerHTML=`<header><span class="wordmark">시야체크<span>.</span></span><span class="state-badge">${publication.mode==='reviewed'?'공개 좌석 현장 대조 기록 있음':'현장 검수 전 · 시연'}</span></header>
      <main><div class="event-info"><h1>${esc(publication.eventName)}</h1><p>${esc(model.name)} · ${esc(publication.sessionLabel)}</p></div>
      <div class="public-layout"><aside class="map-panel"><h2>어떤 자리에서 볼까요?</h2><label>구역 <select id="section"><option value="">전체 공개 좌석</option>${[...new Set(seats.map(s=>s.section))].map(s=>`<option>${esc(s)}</option>`).join('')}</select></label><div id="seat-map" class="seat-map" aria-label="공개 승인된 좌석도"></div><label>좌석 선택 <select id="seat-select">${seats.map((s,i)=>`<option value="${i}">${esc(s.section)} · ${esc(s.label)}</option>`).join('')}</select></label><button id="compare" class="secondary">다른 좌석과 비교</button><button id="clear" class="quiet" hidden>비교 해제</button><p class="muted">공개된 시야 안내 좌석입니다. 실제 잔여석은 예매처에서 확인하세요.</p></aside>
      <section class="scene-panel"><div class="scene-heading"><h2 id="view-title"></h2><select id="target" aria-label="관람 대상">${model.targets.map(t=>`<option value="${esc(t.id)}">${esc(t.name)}</option>`).join('')}</select></div><div id="scene" class="scene"><div class="scene-stamp">치수 기반 시뮬레이션</div></div><div class="controls"><label>앉은 눈높이 <input id="height" type="range" min="0.9" max="1.45" step="0.05" value="1.2"><output id="height-value">1.20m</output></label><label><input id="overlay" type="checkbox">가린 표본 표시</label><button id="reset" class="quiet">정면 보기</button></div><div id="finding" class="finding" aria-live="polite"></div><div id="photo-panel"></div><div class="actions"><a id="ticket" class="primary" hidden target="_blank" rel="noopener noreferrer">공식 예매처에서 확인</a><span id="graphics-status" class="muted" role="status"></span></div></section></div>
      <footer>게시 ${esc(publication.publishedAt.slice(0,10))} · 배치 버전 ${publication.sourceRevision}<br>등록된 고정 구조물과 지정 관람 대상의 예상 시야입니다. 앞사람·자세·연출 변경·관람 만족도는 보증하지 않습니다.</footer></main>`;
    viewer=new VenueViewer(document.querySelector('#scene'),s=>{const el=document.querySelector('#graphics-status');if(el)el.textContent=s;});viewer.rebuild(model,'theatre');
    document.querySelector('#section').onchange=drawMap;
    document.querySelector('#seat-select').onchange=e=>choose(Number(e.target.value));
    document.querySelector('#compare').onclick=()=>{comparePick=true;document.querySelector('#compare').textContent='비교할 좌석을 선택하세요';};
    document.querySelector('#clear').onclick=()=>{comparison=null;comparePick=false;update();};
    document.querySelector('#target').value=targetId;document.querySelector('#target').onchange=e=>{targetId=e.target.value;viewer.resetDirection();update();};
    document.querySelector('#height').oninput=e=>{eyeHeight=Number(e.target.value);update();};
    document.querySelector('#overlay').onchange=update;document.querySelector('#reset').onclick=()=>viewer.resetDirection();
    if(model.ticketUrl){const link=document.querySelector('#ticket');link.href=model.ticketUrl;link.hidden=false;link.onclick=()=>metric('ticket_out');}
    drawMap();update();metric('view');announce('ready',{seatLabels:seats.map(s=>s.label)});
  } catch(error) {stop(error.message || '페이지를 불러오지 못했습니다.');}
}
let comparePick=false;
function choose(index) {
  if(stopped || !seats[index])return;
  if(comparePick){if(index===selected)return;comparison=index;comparePick=false;metric('compare');}
  else selected=index;
  update();announce('seat-changed',{seatLabel:seats[selected].label});
}
function drawMap() {
  const section=document.querySelector('#section').value,visible=seats.filter(s=>!section||s.section===section);
  const xs=visible.map(s=>s.x),zs=visible.map(s=>s.z),minX=Math.min(...xs)-.8,maxX=Math.max(...xs)+.8,minZ=Math.min(...zs)-.8,maxZ=Math.max(...zs)+.8;
  const map=document.querySelector('#seat-map');map.innerHTML=`<span class="map-caption">${esc(getTarget(model,targetId).name)} 방향은 3D에서 확인</span>`;
  const display=visible.slice(0,400);
  for(const seat of display) {
    const button=document.createElement('button');button.className='seat-dot';button.textContent=seat.label;button.title=`${seat.section} ${seat.label}`;button.setAttribute('aria-label',`좌석 ${seat.label}`);button.dataset.index=String(seat.id);
    button.style.left=`${7+(seat.x-minX)/(maxX-minX)*86}%`;button.style.top=`${18+(seat.z-minZ)/(maxZ-minZ)*70}%`;button.onclick=()=>choose(seat.id);map.append(button);
  }
  if(visible.length>400){const p=document.createElement('p');p.className='map-caption';p.textContent='지도는 첫 400석을 표시합니다. 목록에서 전체 공개 좌석을 선택할 수 있습니다.';map.append(p);}
  markMap();
}
function markMap(){document.querySelectorAll('.seat-dot').forEach(b=>{const i=Number(b.dataset.index);b.classList.toggle('selected',i===selected);b.classList.toggle('compared',i===comparison);b.setAttribute('aria-pressed',String(i===selected));});}
function update() {
  if(stopped)return;
  viewer.setView({selected,comparison,layout:'theatre',mode:'seat',eyeHeight,targetId,overlay:document.querySelector('#overlay').checked});
  document.querySelector('#height-value').textContent=`${eyeHeight.toFixed(2)}m`;document.querySelector('#seat-select').value=String(selected);
  document.querySelector('#view-title').textContent=`${seats[selected].label}${comparison!==null?` / ${seats[comparison].label}`:''}의 시야`;
  document.querySelector('#clear').hidden=comparison===null;document.querySelector('#compare').textContent='다른 좌석과 비교';
  const indices=[selected,...(comparison!==null?[comparison]:[])];
  document.querySelector('#finding').innerHTML=indices.map(i=>{
    const analysis=analyzeSightline(model,seats[i],'theatre',eyeHeight,targetId),causes=Object.keys(analysis.causes);
    return `<article><span class="seat-chip">${esc(seats[i].label)}</span><strong>${causes.length?`${esc(causes.join(' · '))}에 ${esc(analysis.targetName)} 일부가 가립니다.`:'입력된 고정 구조물에 가리는 표본이 없습니다.'}</strong><p>대상 중심까지 ${analysis.distance}m · 표본 ${analysis.visible}% 가리지 않음</p></article>`;
  }).join('')+'<p class="muted">표본 비율은 실제 화면 면적이나 좌석 평점이 아닙니다.</p>';
  const photo=publication.evidence.find(e=>e.seatLabel===seats[selected].label && e.targetId===targetId);
  const panel=document.querySelector('#photo-panel');panel.innerHTML=photo?`<details><summary>현장 대조 기록${Math.abs(photo.eyeHeightM-eyeHeight)>.001?' · 현재 눈높이와 다름':''}</summary><p>촬영 ${esc(photo.capturedAt)} · 눈높이 ${photo.eyeHeightM.toFixed(2)}m · ${esc(photo.lens)}</p>${photo.assetId?`<img class="evidence-photo" src="/api/v1/publications/${slug}/assets/${photo.assetId}" alt="${esc(seats[selected].label)}의 공개 승인된 현장 사진">`:'<p>현장 대조 기록이 있으며 사진 공개는 승인되지 않았습니다.</p>'}<p class="muted">담당자의 비교 기록이며 자동 정확도 인증이 아닙니다.</p></details>`:'<p class="muted">이 좌석의 현장 대조 기록이 공개되어 있지 않습니다.</p>';
  markMap();
}
window.addEventListener('message',event=>{
  if(!publication || stopped || event.source!==window.parent || ![location.origin,...publication.allowedOrigins].includes(event.origin))return;
  const data=event.data;if(!data || data.namespace!=='sightcheck' || data.version!==1 || data.publicationId!==slug)return;
  if(data.type==='select-seat'){
    const label=data.seatLabel || publication.seatMapping.find(m=>m.externalId===data.externalId)?.seatLabel;
    const index=seats.findIndex(s=>s.label===label);if(index>=0){comparePick=false;choose(index);}else announce('selection-unavailable');
  }
});
async function checkPublication() {
  if(stopped || !publication || document.hidden)return;
  try{const response=await fetch(`/api/v1/publications/${slug}`);if(response.status===410||response.status===404){const data=await response.json();stop(data.error);}}catch{}
}
const timer=setInterval(checkPublication,15000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)checkPublication();});
window.addEventListener('pagehide',()=>{clearInterval(timer);viewer?.destroy();});
load();
