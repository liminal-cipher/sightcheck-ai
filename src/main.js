import './style.css';
import { DEFAULT_MODEL, LIMITS, LAYOUTS, getSeats, validateModel, analyzeSightline, describeSightline } from './model.js';
import { VenueViewer } from './scene.js';
import { recognizeSeatLabels } from './ocr.js';
import { mountEngineStudio } from './engine-studio.js';

const $ = (selector) => document.querySelector(selector);
const escape = value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const icon = (name) => {
  const paths = {
    eye:'<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
    settings:'<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="2"/><circle cx="15" cy="17" r="2"/>',
    arrow:'<path d="M5 12h14m-5-5 5 5-5 5"/>',
    compare:'<path d="M4 4h16v16H4zM12 4v16"/>',
    camera:'<path d="M3 7h4l2-3h6l2 3h4v13H3z"/><circle cx="12" cy="13" r="4"/>',
    reset:'<path d="M3 10a9 9 0 1 1 2 8M3 4v6h6"/>',
    info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-11v1"/>',
    close:'<path d="m6 6 12 12M6 18 18 6"/>',
    cube:'<path d="m12 2 9 5v10l-9 5-9-5V7zM3 7l9 5 9-5m-9 5v10"/>',
    download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
    check:'<path d="m5 12 4 4L19 6"/>',
  };
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.eye}</svg>`;
};
const MODEL_KEY = 'sightcheck:model:v1', PHOTO_KEY = 'sightcheck:photos:v1';
let model = structuredClone(DEFAULT_MODEL), photos = {}, startupMessage = '';
try {
  const stored = localStorage.getItem(MODEL_KEY);
  if (stored) model = validateModel(JSON.parse(stored));
  const evidence = JSON.parse(localStorage.getItem(PHOTO_KEY) || '{}');
  if (evidence && typeof evidence === 'object' && !Array.isArray(evidence)) photos = evidence;
} catch { startupMessage = '저장된 자료를 읽지 못해 기본 공연장을 열었습니다.'; }
const state = { selected:12, comparison:null, layout:'theatre', mode:'seat', eyeHeight:1.2, overlay:false, comparePick:false };
state.selected = Math.min(state.selected, getSeats(model).length - 1);
let viewer, floorplanSource, ocrBusy = false;
let analysisCache;

$('#app').innerHTML = `
  <header class="topbar">
    <a class="brand" href="#" aria-label="시야체크 홈">${icon('eye')}<span>시야체크<span class="brand-dot">.</span></span></a>
    <div class="header-middle">예매하기 전, 내 자리의 시야부터.</div>
    <div class="header-actions"><a href="/operator.html" class="text-button">공연 운영 작업실</a><span class="demo-badge">가상 공연장 DEMO</span><button id="open-admin" class="text-button">${icon('settings')}<span>공연장 관리</span></button></div>
  </header>
  <main>
    <div class="breadcrumb">공연 <span>/</span> 오름 아트홀 <span>/</span> 좌석 시야</div>
    <section class="event-heading" aria-label="공연 정보">
      <div><h1 id="event-title">뮤지컬 〈THE OTHER SIDE〉</h1><p><span id="venue-name">오름 아트홀</span><span class="dot">·</span><span id="seat-count">좌석 20개</span><span class="dot">·</span><span id="event-status">가상 공연 · 판매하지 않는 예시 가격</span></p></div>    </section>
    <div class="workspace">
      <aside class="seat-panel panel" aria-labelledby="seat-title">
        <div class="panel-top"><div><span class="step">01</span><h2 id="seat-title">좌석 선택</h2></div><span class="small-muted" id="total-seats">전체 20석</span></div>
        <div class="stage-map"><span>STAGE</span><div></div></div>
        <div id="seat-map" role="group" aria-label="가상 공연장 좌석도"></div>
        <div class="seat-legend"><span><i class="legend-seat selected"></i>선택</span><span><i class="legend-seat compared"></i>비교</span><span><i class="legend-seat risk"></i>가림 있음</span></div>
        <div class="map-hint" id="map-hint">좌석을 눌러 그 자리에서 무대를 보세요.</div>
        <div class="map-actions"><button id="pick-compare" class="secondary-button">${icon('compare')}다른 좌석과 비교</button><button id="clear-compare" class="text-button" hidden>비교 해제</button></div>
        <div class="layout-control"><label>공연별 무대 배치</label><div class="layout-options"><button data-layout="theatre" aria-pressed="true">뮤지컬</button><button data-layout="concert" aria-pressed="false">라이브</button></div><p id="layout-note">고정 무대와 2층 전면 난간을 반영합니다.</p></div>
        <div class="seat-map-note">${icon('info')}<p>실제 잔여 좌석이 아닙니다. 좌석도와 가격은 시연용입니다.</p></div>
      </aside>
      <section class="view-panel panel" aria-labelledby="view-title">
        <div class="panel-top viewer-top"><div><span class="step">02</span><h2 id="view-title">내 자리에서 보는 무대</h2></div><div class="view-tabs"><button id="seat-view" aria-pressed="true">좌석 시점</button><button id="overview" aria-pressed="false">공간 전체</button></div></div>
        <div class="scene-frame">
          <div id="scene" class="scene"></div>
          <div class="scene-labels"><span id="view-seat-label">A · 2층 C3</span><span id="view-compare-label" hidden></span></div>
          <div id="compare-divider" hidden></div>
          <div class="simulation-badge"><span></span>3D 추정 시야</div>
          <div class="scene-footer"><span id="scene-help">드래그해서 둘러보기 · 고정 화각 60°</span><button id="reset-direction" aria-label="시점 정면으로 되돌리기">${icon('reset')}</button><button id="save-image" aria-label="시야 이미지 저장">${icon('download')}</button></div>
        </div>
        <div class="viewer-controls"><label class="eye-height">앉은 눈높이 <input id="eye-height" aria-label="앉은 눈높이" type="range" min="0.9" max="1.45" step="0.05" value="1.2"/><output id="eye-value">1.20m</output></label><label class="toggle"><input type="checkbox" id="show-overlay"/>가린 표본 표시</label></div>
        <div class="sightline-strip"><div><span class="strip-dot"></span><p id="sightline-description"></p></div><button id="open-method" class="text-button">계산 기준 ${icon('info')}</button></div>
        <div id="comparison-summary" hidden></div>
        <div class="model-footer"><span id="scene-status" role="status">3D 준비 중</span><span id="validation-note">실사진 검증 전 · 앞사람·연출 변화 제외</span></div>
      </section>
      <aside class="detail-panel panel" aria-labelledby="detail-title">
        <div class="panel-top"><div><span class="step">03</span><h2 id="detail-title">자리 살펴보기</h2></div></div>
        <div id="seat-detail"></div>
        <div class="recommendation"><div class="recommend-label">${icon('eye')}시야 가이드</div><p id="recommendation-text"></p><button id="recommended-seat" class="text-button"></button><span class="small-muted">가상 모델 계산에 따른 안내</span></div>
        <button id="photo-button" class="secondary-button photo-button">${icon('camera')}실사진과 대조</button>
        <div class="booking-area"><div class="price-row"><span>선택 좌석 · 예시 가격</span><strong id="seat-price"></strong></div><button id="booking-button" class="primary-button">좌석 선택 내용 보기 ${icon('arrow')}</button><p id="booking-note">가상 공연이라 실제 예매는 진행되지 않습니다.</p></div>
      </aside>
    </div>
    <div class="bottom-note"><div>${icon('cube')}하나의 공간, 스무 개의 시점.</div><span>무대와 좌석은 같은 모델을 공유합니다. 좌석을 바꾸면 내 눈높이의 카메라만 이동합니다.</span><button id="demo-tour" class="text-button">가림 차이 체험 ${icon('arrow')}</button></div>
  </main>
  <div id="toast" role="status" aria-live="polite" hidden></div>
  <dialog id="method-dialog" class="modal"><div class="dialog-header"><h2>시야를 계산하는 방법</h2><button data-close="method-dialog" class="icon-button" aria-label="계산 기준 닫기">${icon('close')}</button></div><div class="dialog-body"><div class="method-visual">눈높이 → 고정 구조물 → 무대 표본</div><p>선택 좌석의 눈 위치에서 무대 전면 가상 영역(폭 ${model.stageWidth}m · 높이 2.4m)의 325개 표본으로 광선을 보냅니다. 무대보다 먼저 난간이나 카메라 타워를 만나면 해당 표본을 가림으로 계산합니다.</p><p><strong>표시되는 %는 표본 중 가리지 않은 비율입니다.</strong> 관람 만족도, 보이는 무대 면적의 정확한 비율, 실제 시야의 보증값이 아닙니다. 고정 화각 60°와 동일 눈높이로 좌석을 비교합니다.</p><p>사진 한 장으로 구조를 자동 복원하지 않습니다. 현재는 가상 공연장 치수이며 앞사람의 키·움직임, 음향, 배우 동선과 실제 연출은 제외했습니다.</p><p class="callout">실서비스 전 필요한 것: 현장 실측 → 동일 공연 배치의 대표 좌석 촬영 → 가림 오류 수정 → 운영자 검수.</p></div></dialog>
  <dialog id="admin-dialog" class="admin-modal"><div class="dialog-header"><div><h2>공연장 관리</h2></div><button data-close="admin-dialog" class="icon-button" aria-label="공연장 관리 닫기">${icon('close')}</button></div><div class="dialog-body">
    <div class="admin-banner">아래는 초기 가상 공연장의 수동 보정 도구입니다.<p>새 도면은 위 변환 API를 사용하세요. 축척 없는 그림이나 사진만으로 정확한 시야를 생성하지 않습니다.</p></div>
    <section class="admin-section"><h3>1. 좌석도에서 문자 후보 추출</h3><p>PNG·JPEG·WebP 좌석도를 올리세요. OCR은 영문과 숫자를 읽으며 이미지 처리는 이 브라우저 안에서 진행됩니다.</p><div class="upload-actions"><label class="secondary-button file-button">${icon('download')}도면 이미지 선택<input id="floorplan-file" type="file" accept="image/png,image/jpeg,image/webp"/></label><button id="sample-floorplan" class="secondary-button">예시 도면 불러오기</button><button id="run-ocr" class="dark-button" disabled>좌석 문자 인식</button></div><div id="floorplan-preview" hidden><img id="floorplan-image" alt="업로드한 좌석도"/></div><p id="ocr-status" role="status"></p><label class="field"><span>좌석 이름 (앞행부터, 왼쪽 → 오른쪽 · 20개)</span><textarea id="seat-labels" rows="4" spellcheck="false"></textarea></label><p class="small-muted">자동 인식 결과는 후보입니다. 방향·순서·누락을 직접 수정하세요. 도면의 픽셀 간격을 실제 거리로 쓰지 않습니다.</p></section>
    <section class="admin-section"><h3>2. 실측 치수 보정</h3><p>모든 길이의 단위는 m입니다. 저장하면 모델을 다시 만들고 기존 사진 대조 기록은 이전 버전으로 처리합니다.</p><div class="admin-grid" id="dimension-fields"></div><label class="field"><span>공연장 이름</span><input id="venue-input" maxlength="40"/></label><label class="field"><span>공식 예매 페이지 주소 (선택)</span><input id="ticket-url" type="url" placeholder="https://…"/></label><p class="small-muted">예매처와 연동된 재고·결제·자동 좌석 지정은 제공하지 않습니다. 주소를 등록하면 별도 페이지로 연결합니다.</p></section>
    <section class="admin-section"><h3>3. 모델 파일 관리</h3><div class="upload-actions"><button id="export-model" class="secondary-button">모델 JSON 내보내기</button><label class="secondary-button file-button">JSON 불러오기<input id="import-model" type="file" accept="application/json,.json"/></label><button id="reset-model" class="text-button">가상 모델로 복원</button></div><p class="small-muted">사진은 내보내기에 포함되지 않습니다. 자료는 현재 브라우저에만 저장되며 다른 사람과 공유되지 않습니다.</p></section>
    <p id="admin-error" class="error-text" role="alert"></p>
  </div><div class="dialog-footer"><span id="admin-version"></span><button id="save-model" class="primary-button">보정한 모델 저장 ${icon('check')}</button></div></dialog>
  <dialog id="photo-dialog" class="modal"><div class="dialog-header"><h2 id="photo-title">실사진과 대조</h2><button data-close="photo-dialog" class="icon-button" aria-label="사진 대조 닫기">${icon('close')}</button></div><div class="dialog-body"><p>선택 좌석·현재 무대 배치의 정면 사진을 붙여 대조하세요. 렌즈, 촬영 위치, 눈높이가 다르면 직접 비교하기 어렵습니다.</p><label class="secondary-button file-button">사진 선택<input id="photo-file" type="file" accept="image/png,image/jpeg,image/webp"/></label><div id="photo-preview" class="photo-preview"></div><p id="photo-record-status" class="small-muted"></p><label class="field"><span>촬영 정보 · 확인 내용</span><textarea id="photo-note" rows="3" placeholder="촬영일, 렌즈/화각, 눈높이, 난간 위치 대조 내용 등을 기록하세요."></textarea></label><label class="check-line"><input id="photo-verified" type="checkbox"/>동일 좌석·배치·눈높이에서 구조와 가림을 직접 대조했습니다.</label><p class="small-muted">이 표시는 운영자의 대조 기록입니다. 시스템이 사진 정확도를 자동 인증하지 않습니다. 사진과 메모는 이 브라우저에만 저장됩니다.</p><p id="photo-error" class="error-text" role="alert"></p></div><div class="dialog-footer"><button id="remove-photo" class="text-button">첨부 사진 삭제</button><button id="save-photo" class="primary-button">대조 기록 저장</button></div></dialog>
  <dialog id="booking-dialog" class="modal"><div class="dialog-header"><h2>선택 좌석 메모</h2><button data-close="booking-dialog" class="icon-button" aria-label="좌석 메모 닫기">${icon('close')}</button></div><div class="dialog-body"><p>예매 전 비교한 정보를 남길 수 있습니다. 이 데모는 실제 좌석을 확보하거나 구매하지 않습니다.</p><textarea id="booking-text" rows="7" readonly aria-label="선택 좌석 메모"></textarea><button id="copy-selection" class="primary-button">메모 복사</button></div></dialog>
`;

viewer = new VenueViewer($('#scene'), text => {$('#scene-status').textContent = text;});
viewer.rebuild(model, state.layout);

function fingerprint() {return JSON.stringify([model, state.layout, state.eyeHeight]);}
function photoKey(id) {return `${id}:${state.layout}`;}
function getPhoto(id) {
  const record = photos[photoKey(id)];
  return record && typeof record.image === 'string' && record.image.startsWith('data:image/jpeg;base64,') ? record : null;
}
function photoStatus(id) {
  const record = getPhoto(id);
  if (!record) return '실사진 자료 없음';
  if (record.fingerprint !== fingerprint()) return '이전 조건의 사진 · 재대조 필요';
  return record.verified ? '운영자 사진 대조 완료' : '사진 첨부 · 미대조';
}
function update() {
  const seats = getSeats(model), selected = seats[state.selected];
  const analysisKey = fingerprint();
  if (analysisCache?.key !== analysisKey) analysisCache = {key:analysisKey, results:seats.map(seat => analyzeSightline(model, seat, state.layout, state.eyeHeight))};
  const results = analysisCache.results, analysis = results[state.selected];
  $('#venue-name').textContent = model.name;
  $('#seat-count').textContent = `좌석 ${seats.length}개`; $('#total-seats').textContent = `전체 ${seats.length}석`;
  $('#event-status').textContent = model.schemaVersion === 2 ? '도면 변환 · 외관 예시 · 현장 검수 전' : '가상 공연 · 판매하지 않는 예시 가격';
  $('.bottom-note div').innerHTML = `${icon('cube')}하나의 공간, ${seats.length}개의 시점.`;
  $('.demo-badge').textContent = model.schemaVersion === 2 ? '도면 변환 · 검수 전' : '가상 공연장 DEMO';
  $('.breadcrumb').innerHTML = `공연 <span>/</span> ${escape(model.name)} <span>/</span> 좌석 시야`;
  $('#event-title').textContent = state.layout === 'theatre' ? '뮤지컬 〈THE OTHER SIDE〉' : '라이브 〈AFTER HOURS〉';
  const seatButton = (seat,style='') => `<button data-seat="${seat.id}" style="${style}" class="seat ${state.selected === seat.id ? 'is-selected' : ''} ${state.comparison === seat.id ? 'is-compared' : ''} ${results[seat.id].visible < 100 ? 'has-risk' : ''}" aria-label="${escape(seat.section)} ${escape(seat.label)} 좌석" aria-pressed="${state.selected === seat.id}">${escape(seat.label)}</button>`;
  if (model.schemaVersion === 2) {
    const minX = Math.min(...seats.map(s => s.x)), maxX = Math.max(...seats.map(s => s.x)), minZ = Math.min(...seats.map(s => s.z)), maxZ = Math.max(...seats.map(s => s.z));
    $('#seat-map').innerHTML = `<div class="spatial-seatmap" style="height:${Math.max(190, Math.min(600,(maxZ-minZ)*34+70))}px">${seats.map(s => seatButton(s,`left:${8+(s.x-minX)/Math.max(1,maxX-minX)*84}%;top:${8+(s.z-minZ)/Math.max(1,maxZ-minZ)*84}%`)).join('')}</div>`;
    if (seats.length > 40) $('#seat-map').insertAdjacentHTML('beforeend', `<label class="field">좌석 이름으로 선택<select id="seat-jump" aria-label="좌석 이름으로 선택">${seats.map(s => `<option value="${s.id}" ${s.id === state.selected ? 'selected' : ''}>${escape(s.section)} ${escape(s.label)}</option>`).join('')}</select></label>`);
  } else $('#seat-map').innerHTML = [0,1,2,3].map(row => `<div class="map-row ${row === 2 ? 'balcony-start' : ''}"><span class="row-label">${row === 0 ? '1F' : row === 2 ? '2F' : ''}</span><div class="seat-row">${seats.filter(seat => seat.row === row).map(seat => seatButton(seat)).join('')}</div></div>`).join('');
  $('#map-hint').textContent = state.comparePick ? '비교할 두 번째 좌석을 선택하세요.' : state.comparison != null ? 'A와 B는 같은 눈높이와 화각으로 비교합니다.' : '좌석을 눌러 그 자리에서 무대를 보세요.';
  $('#pick-compare').classList.toggle('is-active', state.comparePick);
  $('#clear-compare').hidden = state.comparison == null && !state.comparePick;
  document.querySelectorAll('[data-layout]').forEach(button => button.setAttribute('aria-pressed', button.dataset.layout === state.layout));
  $('#layout-note').textContent = state.layout === 'theatre' ? '고정 무대와 2층 전면 난간을 반영합니다.' : '무대 앞 왼쪽에 촬영 카메라 타워가 추가됩니다.';
  if (model.schemaVersion === 2) $('#layout-note').textContent = '변환 입력에 등록한 해당 공연의 구조물을 반영합니다.';
  $('#seat-view').setAttribute('aria-pressed', state.mode === 'seat');
  $('#overview').setAttribute('aria-pressed', state.mode === 'overview');
  $('#eye-value').textContent = `${state.eyeHeight.toFixed(2)}m`;
  const currentPhoto = getPhoto(state.selected);
  $('#validation-note').textContent = currentPhoto?.verified && currentPhoto.fingerprint === fingerprint()
    ? '운영자 대조 기록 · 앞사람·연출 변화 제외' : '실사진 검증 전 · 앞사람·연출 변화 제외';
  $('#view-seat-label').textContent = state.mode === 'overview' ? '공간 전체 · 선택 좌석은 연두색' : `A · ${selected.section} ${selected.label}`;
  const comparing = state.comparison != null && state.mode === 'seat';
  $('#view-compare-label').hidden = !comparing;
  $('#compare-divider').hidden = !comparing;
  if (comparing) $('#view-compare-label').textContent = `B · ${seats[state.comparison].section} ${seats[state.comparison].label}`;
  $('#scene-help').textContent = state.mode === 'overview' ? '공연장 구조 보기' : comparing ? '동일 화각 60° · 비교 시점을 함께 회전합니다' : '드래그해서 둘러보기 · 고정 화각 60°';
  $('#sightline-description').textContent = describeSightline(analysis);
  $('#seat-detail').innerHTML = `<div class="selected-label">선택한 좌석</div><div class="seat-number">${escape(selected.label)}<span>${escape(selected.section)} · ${model.schemaVersion === 2 ? `${selected.row+1}행` : selected.row < 2 ? '플로어' : '발코니'}</span></div><div class="evidence-badge">${icon('info')}${escape(photoStatus(state.selected))}</div><div class="metric-main"><div><strong>${analysis.visible}<small>%</small></strong><span>가리지 않은 표본</span></div><div class="mini-stage">${miniGrid(analysis)}</div></div><div class="metric-grid"><div><span>무대 하단 표본</span><strong>${analysis.lowerVisible}%</strong></div><div><span>무대 전면 거리</span><strong>${analysis.distance}<small>m</small></strong></div><div><span>중앙축 각도</span><strong>${analysis.angle}<small>°</small></strong></div><div><span>시야 기준</span><strong class="metric-word">고정 구조물</strong></div></div>`;
  const candidates = seats.filter(seat => seat.section === selected.section && seat.id !== selected.id);
  candidates.sort((a,b) => results[b.id].visible - results[a.id].visible || Math.abs(a.x - model.stageOffset) - Math.abs(b.x - model.stageOffset));
  const recommended = candidates[0];
  if (analysis.visible < 100 && recommended && results[recommended.id].visible > analysis.visible) {
    $('#recommendation-text').textContent = `${Object.keys(analysis.causes).join('·')}의 가림이 있습니다. 같은 층의 ${recommended.label}도 비교해 보세요.`;
    $('#recommended-seat').textContent = `${recommended.label}와 비교 →`;
    $('#recommended-seat').dataset.id = recommended.id;
    $('#recommended-seat').hidden = false;
  } else {
    $('#recommendation-text').textContent = analysis.visible === 100 ? '이 모델에서는 고정 구조물의 가림이 없습니다. 거리와 중앙축 각도도 함께 살펴보세요.' : '다른 구역과 비교하거나 실제 좌석 사진을 확인하세요.';
    $('#recommended-seat').hidden = true;
  }
  $('#seat-price').textContent = model.schemaVersion === 2 ? '예매처에서 확인' : `${selected.price.toLocaleString('ko-KR')}원`;
  $('#booking-button').innerHTML = `${model.ticketUrl ? '공식 예매 페이지로 이동' : '좌석 선택 내용 보기'} ${icon('arrow')}`;
  $('#booking-note').textContent = model.ticketUrl ? '외부 예매처에서 재고와 가격을 다시 확인하세요.' : '가상 공연이라 실제 예매는 진행되지 않습니다.';
  $('#comparison-summary').hidden = !comparing;
  if (comparing) {
    const b = results[state.comparison];
    $('#comparison-summary').innerHTML = `<div><span class="compare-a">A · ${escape(selected.label)}</span><strong>${analysis.visible}%</strong><span>거리 ${analysis.distance}m</span></div><div><span class="compare-b">B · ${escape(seats[state.comparison].label)}</span><strong>${b.visible}%</strong><span>거리 ${b.distance}m</span></div><p>가리지 않은 표본 비율 · 동일 모델과 조건<br/>${state.overlay ? '주황 표본은 A 좌석에만 표시됩니다.' : '두 시점은 하나의 3D 장면을 공유합니다.'}</p>`;
  }
  viewer.setView(state);
}
function miniGrid(analysis) {
  return `<svg viewBox="0 0 100 56" role="img" aria-label="주황은 가림, 연두는 보이는 표본"><rect width="100" height="56" rx="3" fill="#282f28"/>${analysis.samples.map(sample => `<rect x="${sample.column * 3.7 + 3}" y="${(12 - sample.row) * 3.7 + 3}" width="2.5" height="2.5" fill="${sample.blocked ? '#eea16c' : '#c7ef7b'}"/>`).join('')}</svg>`;
}
let toastTimer;
function toast(message) {$('#toast').textContent = message; $('#toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => {$('#toast').hidden = true;}, 4500);}
function chooseSeat(id) {
  if (state.comparePick) {
    if (id === state.selected) {toast('현재 자리와 다른 좌석을 선택하세요.'); return;}
    state.comparison = id; state.comparePick = false;
  } else {
    state.selected = id; if (state.comparison === id) state.comparison = null;
  }
  state.mode = 'seat'; update();
}
document.addEventListener('click', event => {
  const seat = event.target.closest('[data-seat]'); if (seat) chooseSeat(Number(seat.dataset.seat));
  const layoutButton = event.target.closest('[data-layout]');
  if (layoutButton && layoutButton.dataset.layout !== state.layout) {state.layout = layoutButton.dataset.layout; viewer.rebuild(model, state.layout); update();}
  const close = event.target.closest('[data-close]'); if (close) $(`#${close.dataset.close}`).close();
});
document.addEventListener('change', event => {if (event.target.id === 'seat-jump') chooseSeat(Number(event.target.value));});
$('#pick-compare').onclick = () => {state.comparePick = !state.comparePick; state.mode = 'seat'; update();};
$('#clear-compare').onclick = () => {state.comparison = null; state.comparePick = false; update();};
$('#seat-view').onclick = () => {state.mode = 'seat'; update();};
$('#overview').onclick = () => {state.mode = 'overview'; update();};
$('#reset-direction').onclick = () => viewer.resetDirection();
$('#eye-height').oninput = event => {state.eyeHeight = Number(event.target.value); update();};
$('#show-overlay').onchange = event => {state.overlay = event.target.checked; update();};
$('#save-image').onclick = () => {if (viewer.unavailable) toast('이 브라우저에서 3D 이미지를 저장할 수 없습니다.'); else {viewer.downloadImage(); toast('가상 모델 표시를 포함한 시야 이미지를 저장합니다.');}};
$('#open-method').onclick = () => {
  $('#method-dialog .dialog-body p').textContent = `선택 좌석의 눈 위치에서 무대 전면 표본 영역(폭 ${model.stageWidth}m · 높이 ${model.targetHeight ?? 2.4}m)의 325개 표본으로 광선을 보냅니다. 무대보다 먼저 입력된 가림 구조물을 만나면 해당 표본을 가림으로 계산합니다.`;
  $('#method-dialog').showModal();
};
$('#demo-tour').onclick = () => {
  const seats = getSeats(model); state.selected = Math.max(0,seats.findIndex(s => s.label === 'C3'));
  const back = seats.findIndex(s => s.label === 'D3'); state.comparison = seats.length > 1 ? (back >= 0 && back !== state.selected ? back : seats.length-1 === state.selected ? 0 : seats.length-1) : null;
  state.comparePick = false; state.mode = 'seat'; state.layout = 'theatre'; viewer.rebuild(model, state.layout); update(); toast('선택한 두 좌석을 같은 조건으로 비교합니다.');
};
$('#recommended-seat').onclick = () => {state.comparison = Number($('#recommended-seat').dataset.id); state.comparePick = false; state.mode = 'seat'; update();};
$('#booking-button').onclick = () => {
  if (model.ticketUrl) { window.open(model.ticketUrl, '_blank', 'noopener,noreferrer'); return; }
  const seat = getSeats(model)[state.selected], analysis = analyzeSightline(model, seat, state.layout, state.eyeHeight);
  $('#booking-text').value = `시야체크 · 가상 모델 추정\n${model.name} / ${LAYOUTS[state.layout].name} / 모델 v${model.version}\n좌석 ${seat.section} ${seat.label} / 앉은 눈높이 ${state.eyeHeight.toFixed(2)}m / 화각 60°\n가리지 않은 표본 ${analysis.visible}% / 하단 표본 ${analysis.lowerVisible}%\n${describeSightline(analysis)}\n예매 재고·가격·실제 시야를 보증하지 않는 데모입니다.`;
  $('#booking-dialog').showModal();
};
$('#copy-selection').onclick = async () => {try {await navigator.clipboard.writeText($('#booking-text').value); toast('좌석 메모를 복사했습니다.');} catch {$('#booking-text').select(); toast('텍스트를 선택했습니다. Ctrl+C로 복사하세요.');}};

const FIELD_NAMES = {seatSpacing:'좌석 중심 간격', rowSpacing:'행 간격', rowRise:'2층 후행 단차', balconyHeight:'2층 전행 바닥 높이', railHeight:'2층 난간 높이', stageWidth:'무대 폭', stageDepth:'무대 깊이', stageOffset:'무대 좌우 이동'};
function fillAdmin() {
  $('#dimension-fields').innerHTML = Object.entries(LIMITS).map(([key, [min,max]]) => `<label class="field"><span>${FIELD_NAMES[key]} (m)</span><input data-dimension="${key}" type="number" min="${min}" max="${max}" step="0.05" value="${model[key]}" required/></label>`).join('');
  $('#seat-labels').value = model.labels.map((name,i) => `${name}${(i + 1) % 5 === 0 ? '\n' : ', '}`).join('');
  $('#venue-input').value = model.name; $('#ticket-url').value = model.ticketUrl;
  $('#admin-version').textContent = `모델 v${model.version} · ${model.updatedAt}`;
  $('#admin-error').textContent = '';
  document.querySelectorAll('[data-dimension],#seat-labels,#save-model').forEach(input => {input.disabled = model.schemaVersion === 2;});
  if (model.schemaVersion === 2) $('#admin-error').textContent = '도면 모델의 수정은 변환 API에서 좌표·치수를 바꾼 뒤 다시 적용하세요. 아래 수동 보정은 초기 20석 모델 전용입니다.';
}
$('#open-admin').onclick = () => {fillAdmin(); $('#admin-dialog').showModal();};
function commitModel(next) {
  const previousLabel = getSeats(model)[state.selected]?.label;
  next = validateModel({...next, version:model.version + 1, updatedAt:new Date().toISOString().slice(0,10)});
  try {localStorage.setItem(MODEL_KEY, JSON.stringify(next));} catch {throw new Error('브라우저 저장 공간이 부족하거나 저장이 차단되었습니다.');}
  model = next;
  const nextSeats = getSeats(model), matched = nextSeats.findIndex(seat => seat.label === previousLabel);
  state.selected = matched >= 0 ? matched : 0; state.comparison = null; state.comparePick = false;
  viewer.rebuild(model, state.layout); update(); fillAdmin();
}
$('#save-model').onclick = () => {
  try {
    const next = {...model, name:$('#venue-input').value, ticketUrl:$('#ticket-url').value.trim(), labels:$('#seat-labels').value.toUpperCase().split(/[\s,;]+/).filter(Boolean)};
    document.querySelectorAll('[data-dimension]').forEach(input => {next[input.dataset.dimension] = input.value === '' ? NaN : Number(input.value);});
    commitModel(next); $('#admin-dialog').close(); toast('모델을 저장했습니다. 이전 사진은 새 조건에서 다시 대조하세요.');
  } catch(error) {$('#admin-error').textContent = error.message;}
};
$('#reset-model').onclick = () => {try {commitModel(structuredClone(DEFAULT_MODEL)); toast('가상 공연장 기본 모델로 복원했습니다.');} catch(error) {$('#admin-error').textContent = error.message;}};
function downloadJson(data, filename) {
  const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([JSON.stringify(data,null,2)], {type:'application/json'})); link.download = filename; link.click(); setTimeout(() => URL.revokeObjectURL(link.href), 1500);
}
$('#export-model').onclick = () => {downloadJson(model, 'sightcheck-venue.json'); toast('현재 저장된 모델을 내보냅니다. 수정 중인 값은 먼저 저장하세요.');};
$('#import-model').onchange = async event => {
  const file = event.target.files[0]; if (!file) return;
  try {
    if (file.size > 512000) throw new Error('모델 파일은 512KB 이하만 가능합니다.');
    commitModel(validateModel(JSON.parse(await file.text()))); toast('모델 JSON을 불러와 저장했습니다.');
  } catch(error) {$('#admin-error').textContent = `불러오기 실패: ${error.message}`;} finally {event.target.value = '';}
};
function fileImage(file, maxSide = 1400) {
  return new Promise((resolve,reject) => {
    if (!['image/jpeg','image/png','image/webp'].includes(file.type) || file.size > 10 * 1024 * 1024) return reject(new Error('10MB 이하의 PNG·JPEG·WebP 이미지를 선택하세요.'));
    const url = URL.createObjectURL(file), image = new Image();
    image.onload = () => {
      URL.revokeObjectURL(url);
      if (image.naturalWidth * image.naturalHeight > 24000000) return reject(new Error('이미지는 2,400만 픽셀 이하로 준비하세요.'));
      const scale = Math.min(1, maxSide / Math.max(image.width,image.height));
      const canvas = document.createElement('canvas'); canvas.width = Math.round(image.width * scale); canvas.height = Math.round(image.height * scale);
      const ctx = canvas.getContext('2d'); ctx.fillStyle = '#fff'; ctx.fillRect(0,0,canvas.width,canvas.height); ctx.drawImage(image,0,0,canvas.width,canvas.height);
      resolve(canvas.toDataURL('image/jpeg', 0.85));
    };
    image.onerror = () => {URL.revokeObjectURL(url); reject(new Error('이미지를 읽지 못했습니다.'));}; image.src = url;
  });
}
function setFloorplan(source) {
  floorplanSource = source; $('#floorplan-image').src = source; $('#floorplan-preview').hidden = false;
  $('#run-ocr').disabled = ocrBusy; $('#ocr-status').textContent = '도면을 준비했습니다. 문자 인식 후 후보를 직접 확인하세요.';
}
$('#floorplan-file').onchange = async event => {
  if (!event.target.files[0]) return;
  try {setFloorplan(await fileImage(event.target.files[0]));} catch(error) {$('#ocr-status').textContent = error.message;}
  event.target.value = '';
};
$('#sample-floorplan').onclick = () => {setFloorplan(new URL('/sample-seatmap.png', location.origin).href);};
$('#run-ocr').onclick = async () => {
  if (ocrBusy || !floorplanSource) return;
  ocrBusy = true; $('#run-ocr').disabled = true; $('#sample-floorplan').disabled = true; $('#floorplan-file').disabled = true;
  try {
    const result = await recognizeSeatLabels(floorplanSource, text => {$('#ocr-status').textContent = text;});
    if (!result.candidates.length) {$('#ocr-status').textContent = '영문·숫자 좌석 이름을 찾지 못했습니다. 직접 입력하거나 선명한 도면으로 다시 시도하세요.';}
    else {
      $('#seat-labels').value = result.candidates.map(candidate => candidate.label).join(', ');
      $('#ocr-status').textContent = `${result.candidates.length}개 문자 후보를 찾았습니다. 앞행부터 왼쪽→오른쪽 순서로 정렬했습니다. 20개인지 확인·수정 후 모델을 저장하세요.`;
    }
  } catch(error) {$('#ocr-status').textContent = `문자 인식을 완료하지 못했습니다. 도면과 로컬 OCR 파일을 확인하고 다시 시도하세요. (${error.message})`;}
  finally {ocrBusy = false; $('#run-ocr').disabled = false; $('#sample-floorplan').disabled = false; $('#floorplan-file').disabled = false;}
};

let photoImage = null, photoSeat = null, photoFingerprint = null, activePhotoKey = null;
$('#photo-button').onclick = () => {
  photoSeat = state.selected; photoFingerprint = fingerprint(); activePhotoKey = photoKey(photoSeat);
  const record = getPhoto(photoSeat);
  photoImage = record?.image || null;
  $('#photo-title').textContent = `${getSeats(model)[photoSeat].label} · 실사진 대조`;
  $('#photo-note').value = record?.note || '';
  $('#photo-verified').checked = !!record?.verified && record.fingerprint === photoFingerprint;
  $('#photo-error').textContent = ''; $('#photo-record-status').textContent = photoStatus(photoSeat);
  showPhoto(); $('#photo-dialog').showModal();
};
function showPhoto() {
  $('#photo-preview').replaceChildren();
  if (photoImage) {const img = document.createElement('img'); img.src = photoImage; img.alt = '선택 좌석에 첨부한 대조 사진'; $('#photo-preview').append(img);}
  else $('#photo-preview').textContent = '아직 첨부한 실사진이 없습니다.';
}
$('#photo-file').onchange = async event => {
  if (!event.target.files[0]) return;
  try {photoImage = await fileImage(event.target.files[0], 800); $('#photo-verified').checked = false; showPhoto(); $('#photo-error').textContent = '';}
  catch(error) {$('#photo-error').textContent = error.message;} event.target.value = '';
};
$('#save-photo').onclick = () => {
  if (!photoImage) {$('#photo-error').textContent = '먼저 사진을 첨부하세요.'; return;}
  const note = $('#photo-note').value.trim();
  if ($('#photo-verified').checked && note.length < 10) {$('#photo-error').textContent = '대조 완료로 기록하려면 촬영 조건과 확인 내용을 10자 이상 남기세요.'; return;}
  const next = {...photos, [activePhotoKey]:{image:photoImage, note:note.slice(0,2000), verified:$('#photo-verified').checked, fingerprint:photoFingerprint, date:new Date().toISOString()}};
  try {localStorage.setItem(PHOTO_KEY, JSON.stringify(next)); photos = next; $('#photo-dialog').close(); update(); toast('사진과 대조 기록을 이 브라우저에 저장했습니다.');}
  catch {$('#photo-error').textContent = '사진을 저장하지 못했습니다. 저장 공간을 확보하거나 작은 사진을 사용하세요.';}
};
$('#remove-photo').onclick = () => {
  const next = {...photos}; delete next[activePhotoKey];
  try {localStorage.setItem(PHOTO_KEY,JSON.stringify(next)); photos = next; photoImage = null; showPhoto(); $('#photo-note').value = ''; $('#photo-verified').checked = false; $('#photo-record-status').textContent = '실사진 자료 없음'; update(); toast('이 좌석의 첨부 사진을 삭제했습니다.');}
  catch {$('#photo-error').textContent = '삭제 기록을 저장하지 못했습니다.';}
};
mountEngineStudio({fileImage, commitModel, toast});
update(); if (startupMessage) toast(startupMessage);
