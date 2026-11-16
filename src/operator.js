import './operator.css';
import * as Model from './model.js';
import { VenueViewer } from './scene.js';

const $ = selector => document.querySelector(selector);
const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const clone = value => structuredClone(value);
const pathId = value => encodeURIComponent(value);
const uid = prefix => `${prefix}-${crypto.randomUUID().slice(0, 8)}`;
const MAX_PHOTO_BYTES = 1_500_000;
const STEPS = [['space', '공간', '프로젝트와 공연'], ['layout', '배치', '설치물과 관람대상'], ['review', '대조', '현장 사진과 검수'], ['publish', '게시', '공개 범위와 연동']];
const state = {
  auth: null, projects: [], project: null, event: null, step: 'space', loading: false, busy: false,
  drafts: new Map(), forms: new Map(), scopes: new Map(), photos: new Map(), hashes: new Map(), stats: new Map(),
  statsSequence: 0, loginToken: '', projectModel: null,
  selectedSeat: '', targetId: '', obstacleId: '', message: null, sequence: 0, controller: null,
  view: { selected: 0, comparison: null, layout: 'theatre', eyeHeight: 1.2, mode: 'seat', overlay: false, targetId: '' },
};
let preview, previewKey = '', photoSequence = 0, toastTimer;

const icon = name => {
  const paths = {
    eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    cube: '<path d="m12 2 9 5v10l-9 5-9-5V7zM3 7l9 5 9-5m-9 5v10"/>',
    copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V4H4v12h4"/>',
    arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-11v1"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    camera: '<path d="M3 7h4l2-3h6l2 3h4v13H3z"/><circle cx="12" cy="13" r="4"/>',
    reset: '<path d="M3 10a9 9 0 1 1 2 8M3 4v6h6"/>',
    link: '<path d="m9 15 6-6M8 12l-2 2a4 4 0 0 0 6 6l2-2M10 6l2-2a4 4 0 0 1 6 6l-2 2"/>',
    lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/>',
  };
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.info}</svg>`;
};
const field = (id, label, value = '', options = {}) => `<label class="field ${options.wide ? 'wide' : ''}" for="${escape(id)}"><span>${escape(label)}</span><input id="${escape(id)}" name="${escape(id)}" type="${options.type || 'text'}" value="${escape(value)}" ${options.required ? 'required' : ''} ${options.max ? `maxlength="${options.max}"` : ''} ${options.type === 'number' ? 'step="any"' : ''} ${options.min != null ? `min="${options.min}"` : ''} ${options.maxValue != null ? `max="${options.maxValue}"` : ''} ${options.placeholder ? `placeholder="${escape(options.placeholder)}"` : ''} ${options.readonly ? 'readonly' : ''}>${options.help ? `<small>${escape(options.help)}</small>` : ''}</label>`;
const selectField = (id, label, options, selected, wide = false) => `<label class="field ${wide ? 'wide' : ''}" for="${id}"><span>${escape(label)}</span><select id="${id}" name="${id}">${options.map(([value, text]) => `<option value="${escape(value)}" ${String(value) === String(selected) ? 'selected' : ''}>${escape(text)}</option>`).join('')}</select></label>`;
const textarea = (id, label, value = '', help = '', options = {}) => `<label class="field" for="${id}"><span>${escape(label)}</span><textarea id="${id}" name="${id}" rows="3" ${options.required ? 'required' : ''} ${options.max ? `maxlength="${options.max}"` : ''}>${escape(value)}</textarea>${help ? `<small>${escape(help)}</small>` : ''}</label>`;
// Computed positions can carry float noise (8.057500000000001); show at most 6 decimals.
const tidyNumber = value => typeof value === 'number' && Number.isFinite(value) ? Number(value.toFixed(6)) : value;
const vector = (prefix, label, values, axes = ['X', 'Y', 'Z'], min) => `<fieldset class="vector ${axes.length === 2 ? 'two' : ''}"><legend>${escape(label)}</legend><div class="vector-grid">${axes.map((axis, i) => field(`${prefix}-${i}`, axis, tidyNumber(values?.[i] ?? 0), { type: 'number', required: true, min })).join('')}</div></fieldset>`;
const button = (label, action, className = '', glyph) => `<button type="button" class="button ${className}" data-action="${action}">${glyph ? icon(glyph) : ''}${escape(label)}</button>`;
const submit = (label, primary = true) => `<button type="submit" class="button ${primary ? 'primary' : ''}">${escape(label)} ${icon('arrow')}</button>`;
const pill = (label, tone = '') => `<span class="pill ${tone}">${escape(label)}</span>`;
const card = (title, subtitle, body, suffix = '') => `<section class="card"><div class="card-heading"><div><h2>${escape(title)}</h2><p>${escape(subtitle)}</p></div>${suffix}</div><div class="card-body">${body}</div></section>`;
const form = (id, body) => `<form id="${id}"><fieldset ${state.busy ? 'disabled' : ''}>${body}</fieldset></form>`;
const currentKey = () => state.event?.id || `project:${state.project?.id || 'none'}`;
const formKey = () => `${currentKey()}:${state.step}`;
const draft = () => state.event ? state.drafts.get(state.event.id) : null;
const seats = () => draft() ? Model.getSeats(draft().model) : [];
const targets = model => model.targets?.length ? model.targets : [{ id: 'stage', name: '무대 전면', position: [model.stageOffset || 0, (model.stageHeight ?? .6) + .08 + (model.targetHeight ?? 2.4) / 2, -.25], size: [model.stageWidth, model.targetHeight ?? 2.4], rotation: [0, 0, 0] }];
const obstacles = model => model.schemaVersion >= 2 ? model.obstacles || [] : Model.getObstacles(model, 'theatre');
const scope = () => {
  if (!state.scopes.has(currentKey())) state.scopes.set(currentKey(), { section: '', row: '', selected: new Set() });
  return state.scopes.get(currentKey());
};

class ApiError extends Error {
  constructor(message, status, code) { super(message); this.status = status; this.code = code; }
}
async function api(path, { method = 'GET', body, signal } = {}) {
  const controller = new AbortController();
  const abort = () => controller.abort(signal?.reason);
  if (signal?.aborted) abort();
  else signal?.addEventListener('abort', abort, { once: true });
  const timeout = setTimeout(() => controller.abort(), 25000);
  try {
    const response = await fetch(`/api/v1${path}`, {
      method, credentials: 'same-origin', cache: 'no-store', signal: controller.signal,
      headers: body === undefined ? { Accept: 'application/json' } : { Accept: 'application/json', 'Content-Type': 'application/json' },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    let data;
    try { data = await response.json(); }
    catch { throw new ApiError('서버 응답을 읽지 못했습니다. 연결을 확인한 뒤 다시 시도하세요.', response.status); }
    if (!response.ok) throw new ApiError(data.error || '요청을 처리하지 못했습니다.', response.status, data.code);
    return data;
  } catch (error) {
    if (error.name === 'AbortError' && !signal?.aborted) throw new Error('응답이 지연되고 있습니다. 입력은 유지됩니다. 잠시 후 다시 시도하세요.');
    if (error instanceof TypeError) throw new Error('서버에 연결하지 못했습니다. 서버 실행 상태와 접속 주소를 확인하세요. 입력은 유지됩니다.');
    throw error;
  } finally { clearTimeout(timeout); signal?.removeEventListener('abort', abort); }
}

function captureForms() {
  const root = $('#editor');
  if (!root) return;
  const values = new Map();
  root.querySelectorAll('input[id],select[id],textarea[id]').forEach(input => {
    if (input.type !== 'file' && input.type !== 'password' && !input.readOnly && !['scope-section', 'scope-row'].includes(input.id)) values.set(input.id, input.type === 'checkbox' ? { checked: input.checked } : { value: input.value });
  });
  const details = [...root.querySelectorAll('details[id]')].map(el => [el.id, el.open]);
  state.forms.set(formKey(), { values, details });
  if (draft()) draft().selection = { selectedSeat: state.selectedSeat, targetId: state.targetId, obstacleId: state.obstacleId };
}
function restoreForms() {
  const remembered = state.forms.get(formKey());
  if (!remembered) return;
  remembered.values.forEach((value, id) => {
    const input = document.getElementById(id);
    if (!input || !$('#editor').contains(input)) return;
    if (value.checked !== undefined) input.checked = value.checked;
    else if (input.tagName !== 'SELECT' || [...input.options].some(option => option.value === value.value)) input.value = value.value;
  });
  for (const [id, open] of remembered.details) { const el = document.getElementById(id); if (el) el.open = open; }
}
function forgetFields(prefix) {
  const remembered = state.forms.get(formKey());
  if (remembered) for (const id of remembered.values.keys()) if (id.startsWith(prefix)) remembered.values.delete(id);
}
function toast(message) {
  $('#toast').textContent = message; $('#toast').hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 4500);
}
function notify(message, tone = 'error', title = '') {
  state.message = { message, tone, title }; renderMessage();
  $('#message').scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}
function renderMessage() {
  const banner = $('#message');
  banner.hidden = !state.message;
  if (state.message) banner.innerHTML = `${icon('info')}<p>${state.message.title ? `<span class="alert-title">${escape(state.message.title)}</span>` : ''}${escape(state.message.message)}</p>${button('닫기', 'dismiss', 'subtle small')}`;
  banner.className = `note banner ${state.message?.tone || ''}`;
  banner.setAttribute('role', state.message?.tone === 'error' ? 'alert' : 'status');
}

function mount() {
  $('#operator-app').innerHTML = `<a class="skip-link" href="#editor">운영 내용으로 바로가기</a><div class="studio">
    <aside class="sidebar" aria-label="프로젝트와 접속 정보">
      <div><a class="brand" href="/operator.html">${icon('eye')}<span>시야체크<span class="brand-dot">.</span></span></a><span class="studio-label">운영 스튜디오</span></div>
      <div class="project-picker"><label for="project-select">관리할 프로젝트</label><select class="control" id="project-select" disabled><option value="">프로젝트 불러오는 중</option></select>${button('새 프로젝트', 'new-project', 'subtle', 'plus')}</div>
      <div class="sidebar-divider"></div><div class="sidebar-meta"><strong>공간을 담고, 현장에서 확인하세요.</strong>공연마다 달라지는 설치물과 관람대상을 관리하고, 대조한 좌석만 관객에게 공개합니다.</div>
      <div class="sidebar-footer"><div id="auth-state" class="help">접속 확인 중</div><div id="auth-action"></div><a href="/index.html" target="_blank" rel="noopener">도면 변환 도구 열기 ${icon('arrow')}</a></div>
    </aside>
    <main class="main" id="main"><div class="topline"><div class="breadcrumb"><span>운영 스튜디오</span><span>/</span><span id="project-name">프로젝트</span></div><div class="top-actions"><span id="revision-pill" class="pill neutral">연결 확인 중</span><span id="busy-label" class="busy-label" role="status" hidden>저장 중…</span>${button('새로 불러오기', 'refresh', 'subtle small', 'reset')}</div></div>
      <section class="hero"><div><h1 id="page-title">관객의 시야를 준비하는 공간.</h1><p id="page-subtitle">공간부터 게시까지, 한 공연의 시야를 차근차근 완성하세요.</p></div></section>
      <div id="message" hidden aria-live="polite"></div><div id="event-toolbar" class="event-toolbar"></div>
      <nav class="workflow" id="workflow" aria-label="운영 단계">${STEPS.map(([id, name, hint], i) => `<button type="button" data-step="${id}" aria-current="${id === state.step ? 'step' : 'false'}"><span class="step-no">0${i + 1}</span><span class="step-copy"><strong>${name}</strong><small>${hint}</small></span></button>`).join('')}</nav>
      <div id="draft-notice" hidden></div><div class="workspace" id="workspace"><div class="editor" id="editor" tabindex="-1"></div><aside class="preview-pane" id="preview-pane" aria-label="선택 공연 미리보기">
        <section class="card"><div class="preview-header"><div><h2>관객의 자리에서</h2></div><div class="view-tabs" role="group" aria-label="미리보기 시점"><button type="button" data-view="seat" aria-pressed="true">좌석 시점</button><button type="button" data-view="overview" aria-pressed="false">공간 전체</button></div></div>
          <div class="scene-frame"><div id="scene" class="scene"><div class="scene-empty">${icon('cube')}<span>공연을 선택하면 공간을 미리 볼 수 있습니다.</span></div></div><div class="scene-tag" id="scene-tag" hidden></div><div class="scene-disclaimer">3D 추정 · 현장 대조 필요</div></div>
          <div class="preview-controls" id="preview-controls"></div><div class="sightline-summary" id="sightline-summary"></div><div class="preview-map" id="preview-map"></div><div class="preview-foot"><span id="scene-status" role="status">미리보기 대기</span><span>검수 기준 눈높이 1.20m</span></div>
        </section><div class="preview-note">${icon('info')}<span>설치물은 입력 치수대로 계산합니다. 앞사람과 공연 중 움직임은 포함되지 않습니다. 사진과 현재 공연 배치를 함께 대조하세요.</span></div>
      </aside></div><footer class="footer">SIGHTCHECK · 공간과 좌석을 연결하는 운영 스튜디오<br>작성 중인 입력은 이 페이지 안에서 공연별로 유지됩니다. 페이지를 닫기 전 서버에 저장하세요.</footer>
    </main></div><div id="toast" class="toast" role="status" aria-live="polite" hidden></div>`;
  $('#operator-app').addEventListener('click', handleClick);
  $('#operator-app').addEventListener('submit', handleSubmit);
  $('#operator-app').addEventListener('change', handleChange);
  $('#operator-app').addEventListener('input', handleInput);
  window.addEventListener('beforeunload', event => {
    if ([...state.drafts.values()].some(d => d.dirty || d.pending.size) || [...state.photos.values()].some(p => p.dataUrl)) { event.preventDefault(); event.returnValue = ''; }
  });
  window.addEventListener('pagehide', () => preview?.destroy?.());
}

function renderChrome() {
  const authenticated = !!state.auth?.authenticated;
  $('#project-name').textContent = state.project?.name || '프로젝트';
  $('#page-title').textContent = state.event?.name || '관객의 시야를 준비하는 공간.';
  $('#page-subtitle').textContent = state.event ? `${state.project?.name || ''} · ${seats().length}개 좌석 · 공연별 배치와 현장 대조를 관리합니다.` : '공간부터 게시까지, 한 공연의 시야를 차근차근 완성하세요.';
  $('#auth-state').innerHTML = `<span class="auth-dot ${authenticated ? '' : 'off'}"></span>${!state.auth ? '접속 확인 중' : state.auth.mode === 'local' ? '로컬 운영 · 이 컴퓨터에서만 접속' : authenticated ? '운영자 로그인 완료' : '운영자 로그인 필요'}`;
  $('#auth-action').innerHTML = state.auth?.mode === 'token' && authenticated ? button('로그아웃', 'logout', 'subtle small') : '';
  $('#project-select').innerHTML = `<option value="">프로젝트 선택</option>${state.projects.map(p => `<option value="${escape(p.id)}" ${state.project?.id === p.id ? 'selected' : ''}>${escape(p.name)} · ${escape(p.eventCount ?? 0)}개 공연</option>`).join('')}`;
  $('#project-select').disabled = !authenticated || state.loading || state.busy;
  $('#revision-pill').textContent = state.event ? `리비전 ${state.event.revision}` : authenticated ? '운영 연결됨' : '로그인 확인';
  const events = state.project?.events || [];
  $('#event-toolbar').innerHTML = authenticated && state.project ? `${selectField('event-select', '작업할 공연', [['', events.length ? '공연을 선택하세요' : '첫 공연을 만들어 주세요'], ...events.map(e => [e.id, e.name])], state.event?.id)}${button('새 공연', 'new-event', 'subtle', 'plus')}${state.event ? button('공연 복제', 'clone-event', 'subtle', 'copy') : ''}` : '';
  $('#event-toolbar').hidden = !authenticated || !state.project;
  $('#workflow').hidden = !authenticated;
  $('#workflow').querySelectorAll('[data-step]').forEach(el => el.setAttribute('aria-current', el.dataset.step === state.step ? 'step' : 'false'));
  $('#preview-pane').hidden = !authenticated || !state.event;
  $('#workspace').style.gridTemplateColumns = !authenticated || !state.event ? 'minmax(0,1fr)' : '';
  $('#busy-label').hidden = !state.busy;
  $('#main').setAttribute('aria-busy', String(state.busy || state.loading));
  applyBusy();
}
function applyBusy() {
  const blocked = state.busy || state.loading;
  $('#operator-app').querySelectorAll('button, #project-select, #event-select, #preview-seat, #preview-target, #preview-overlay').forEach(el => {
    if (el.dataset.action === 'dismiss') return;
    const unavailable = !state.auth?.authenticated && !['login', 'refresh', 'dismiss'].includes(el.dataset.action) && el.closest('form')?.id !== 'login-form';
    el.disabled = blocked || unavailable;
  });
  $('#editor').querySelectorAll('form>fieldset').forEach(el => { el.disabled = blocked; });
}
function renderDraftNotice() {
  const d = draft(), notice = $('#draft-notice');
  notice.hidden = !d || (!d.dirty && !d.pending.size && !d.conflict);
  if (!d) return;
  notice.className = `note banner ${d.conflict ? 'warn' : ''}`;
  notice.innerHTML = `<p>${escape(d.conflict ? '최신 서버 자료를 불러왔습니다. 작성한 변경은 보존했습니다. 아래 변경을 확인한 뒤 저장하면 최신 리비전에 반영됩니다.' : d.pending.size ? '입력 중인 항목이 있습니다. 해당 폼에서 먼저 미리보기에 적용해 주세요.' : '미리보기에 적용된 변경사항이 있습니다. 서버에 저장해야 대조·게시에서 사용할 수 있습니다.')}</p>${d.dirty && !d.pending.size ? button(d.conflict ? '변경 확인 후 저장' : '변경사항 저장', 'save-draft', 'primary small', 'check') : ''}`;
}
function renderEditor({ capture = true } = {}) {
  if (capture) captureForms();
  let html;
  if (state.loading) html = '<div class="card loading" role="status">운영 자료를 불러오고 있습니다.</div>';
  else if (!state.auth) html = card('운영 서버에 연결하지 못했습니다', '서버를 시작한 뒤 다시 불러오세요.', `${'<p class="help">운영자 API와 같은 주소에서 이 페이지를 열어 주세요.</p>'}<div class="actions">${button('다시 연결', 'refresh', 'primary', 'reset')}</div>`);
  else if (!state.auth.authenticated) html = loginView();
  else if (state.step === 'space') html = spaceView();
  else if (!state.event) html = card('먼저 공연을 선택해 주세요', '공간 단계에서 프로젝트와 공연을 만들 수 있습니다.', `<div class="empty">${icon('cube')}<h3>공연별로 다른 시야를 관리하세요.</h3><p>설치물과 대조 사진은 선택한 공연에 저장됩니다.</p>${button('공간 단계로 이동', 'go-space', 'primary')}</div>`);
  else if (state.step === 'layout') html = layoutView();
  else if (state.step === 'review') html = reviewView();
  else html = publishView();
  $('#editor').innerHTML = html;
  restoreForms(); updateModeNote(); renderChrome(); renderDraftNotice(); renderMessage(); renderPreview(); applyBusy();
}
function loginView() {
  if (state.auth.mode === 'local') return card('로컬 운영 접속이 필요합니다', '운영 서버는 이 컴퓨터의 localhost에서 열어 주세요.', `<div class="note warn">원격 주소에서는 로컬 운영 기능에 접속할 수 없습니다. 서버가 안내한 localhost 주소로 열어 주세요.</div><div class="actions">${button('접속 다시 확인', 'refresh', 'primary', 'reset')}</div>`);
  return `<section class="card login-card"><div class="card-body"><div class="login-mark">${icon('lock')}</div><h2 style="margin-top:20px">운영자 로그인이 필요합니다.</h2><p class="help">서버 운영자가 발급한 토큰으로 접속하세요. 공연 배치와 현장 사진은 로그인한 운영자만 관리할 수 있습니다.</p>${form('login-form', `${field('auth-token', '운영자 접속 토큰', state.loginToken, { type: 'password', required: true, placeholder: '접속 토큰 입력' })}${submit('로그인')}`)}</div></section>`;
}

function spaceView() {
  const p = state.project, e = state.event, d = draft();
  const remembered = state.forms.get(formKey());
  const projectOpen = !p || remembered?.details?.some(([id, open]) => id === 'project-create' && open);
  let body = `<details class="detail-box" id="project-create" ${projectOpen ? 'open' : ''}><summary>${p ? '새 프로젝트 만들기' : '첫 프로젝트 만들기'}</summary><div><p class="help">공연장 또는 공간 단위로 프로젝트를 만드세요. 기본 가상 모델 또는 이 브라우저에서 변환한 도면으로 시작할 수 있습니다.</p>${form('project-form', `${field('project-create-name', '프로젝트 이름', '', { required: true, max: 40, placeholder: '예: 오름 아트홀' })}<div class="actions">${button('이 브라우저의 도면 변환 결과 사용', 'use-browser-model', 'subtle small', 'cube')}${state.projectModel ? button('기본 가상 공간으로 시작', 'clear-project-model', 'subtle small') : ''}</div>${state.projectModel ? `<div class="import-summary">선택한 공간: ${escape(state.projectModel.name)} · ${Model.getSeats(state.projectModel).length}석</div>` : ''}<p class="help" style="margin:13px 0">도면의 사용·공개 권한을 확인하세요. 변환 결과의 축척, 좌석 위치와 설치물 치수는 현장에서 검토해야 합니다. 가져오기만으로 검수가 완료되지 않습니다.</p><div class="actions">${submit('프로젝트 만들기')}</div>`)}</div></details>`;
  if (!p) return card('공간을 관리할 프로젝트를 만드세요', '하나의 공간에 여러 공연을 연결할 수 있습니다.', body, pill('시작하기', 'neutral'));
  body = `<div class="note">${escape(p.name)}의 공연을 선택하면 저장된 공간과 배치를 불러옵니다. 다른 공연으로 이동해도 작성 중인 입력은 이 페이지 안에서 유지됩니다.</div>${body}`;
  body += `<details class="detail-box" id="event-create" ${!e ? 'open' : ''}><summary>${!e ? '공연 만들기' : '새 공연 만들기 · 현재 공연 복제'}</summary><div><p class="help">새 공연은 프로젝트의 기본 공간을 사용합니다. 복제하면 현재 공연의 저장된 모델을 가져옵니다. 현장 사진과 검수는 새 공연에서 진행하세요.</p>${form('event-form', `${field('event-create-name', '새 공연 이름', '', { required: true, max: 80, placeholder: '예: THE OTHER SIDE · 가을 공연' })}${selectField('event-clone-source', '시작할 배치', [['', '프로젝트 기본 공간'], ...(p.events || []).map(event => [event.id, `${event.name}의 배치 복제`])], '')}<div class="actions">${submit('공연 만들기')}</div>`)}</div></details>`;
  let html = card('프로젝트와 공연', '공간은 프로젝트에, 배치는 공연에 연결됩니다.', body, pill(`${p.events?.length || 0}개 공연`, 'neutral'));
  if (!e) return html;
  const m = d.model;
  html += card('선택 공연의 공간 정보', '모든 치수는 미터(m) 단위입니다.', form('space-form', `<div class="form-grid">${field('event-name', '공연 이름', d.name, { required: true, max: 80 })}${field('event-session', '적용 회차 (게시 필수)', d.sessionLabel === '적용 회차 미지정' ? '' : d.sessionLabel, { required: true, max: 120, placeholder: '예: 10월 8일 저녁 회차' })}${field('venue-name', '공간 이름', m.name, { required: true, max: 40 })}${selectField('venue-type', '공간 종류', [['theatre', '극장 · 공연장'], ['cinema', '영화관 · 상영관'], ['stadium', '경기장']], m.venueType || 'theatre')}${field('stage-width', '무대 폭 (m)', m.stageWidth, { type: 'number', required: true, min: 2, maxValue: 200 })}${field('stage-depth', '무대 깊이 (m)', m.stageDepth, { type: 'number', required: true, min: 1, maxValue: 150 })}${field('stage-height', '무대 바닥높이 (m)', m.stageHeight ?? .6, { type: 'number', required: true, min: 0, maxValue: 3 })}${field('target-height', '기본 관람 영역 높이 (m)', m.targetHeight ?? 2.4, { type: 'number', required: true, min: .1, maxValue: 20 })}${field('ticket-url', '예매 페이지 주소 (선택)', m.ticketUrl || '', { type: 'url', wide: true, placeholder: 'https://…', help: '연동할 예매 서비스의 실제 주소를 입력하세요.' })}</div><p class="coordinate-note">X는 좌우, Y는 높이, Z는 앞뒤 방향입니다. 설치물 위치는 물체 중심 기준입니다.</p><div class="actions"><small>변경된 공간은 다시 현장 대조해야 합니다.</small>${submit('공간 정보 저장')}</div>`));
  html += floorView();
  html += card('기존 도면으로 시작하기', '도면 변환 결과를 선택 공연의 공간으로 불러올 수 있습니다.', `<p class="help">도면 변환 도구에서 축척과 좌석을 확인한 뒤 모델 파일을 내려받으세요. 아래 상세 메뉴에서 가져와 3D 미리보기로 확인할 수 있습니다.</p><div class="actions"><a class="button" href="/index.html" target="_blank" rel="noopener">도면 변환 도구 열기 ${icon('arrow')}</a></div><details class="detail-box" id="import-details"><summary>상세 · 모델 JSON 가져오기</summary><div><p class="help">schemaVersion 1·2·3 모델을 가져올 수 있습니다. 가져온 모델은 미리보기에 적용되며, 변경사항 저장 후 현장 대조를 진행하세요.</p>${form('import-form', `<label class="field" for="model-file"><span>모델 JSON 파일</span><input id="model-file" type="file" accept=".json,application/json"></label>${textarea('model-json', '모델 내용 (파일 대신 직접 붙여넣기)', '', '파일 또는 텍스트 중 하나를 사용하세요.')}<div class="actions">${submit('모델 가져오기')}</div>`)}</div></details>`);
  return html;
}

function filteredSeats() {
  const s = scope();
  return seats().filter(seat => (!s.section || seat.section === s.section) && (s.row === '' || String(seat.row) === s.row));
}
function scopeFields() {
  const s = scope(), all = seats();
  return `<div class="scope-bar">${selectField('scope-section', '좌석 구역', [['', '모든 구역'], ...[...new Set(all.map(seat => seat.section))].map(v => [v, v])], s.section)}${selectField('scope-row', '좌석 행', [['', '모든 행'], ...[...new Set(all.filter(seat => !s.section || seat.section === s.section).map(seat => seat.row))].sort((a, b) => a - b).map(v => [v, `${v + 1}행 (행 값 ${v})`])], s.row)}</div>`;
}
function currentModelHash() {
  const event = state.event;
  return event?.modelHash || state.hashes.get(event?.id) || (!event?.publication?.stale ? event?.publication?.modelHash : null) || null;
}
function evidenceState(evidence) {
  const hash = currentModelHash();
  const matching = (state.event.reviews || []).filter(r => r.evidenceId === evidence.id);
  const review = matching.at(-1);
  const stale = evidence.stale === true || review?.stale === true || (!!hash && evidence.modelHash !== hash) || (!!review?.modelHash && review.modelHash !== evidence.modelHash);
  return { review, stale, hashKnown: !!hash, status: stale ? 'stale' : review?.status || 'pending' };
}
function seatReviewStatus(label, targetId = state.step === 'review' ? state.targetId : state.event?.model.activeTargetId) {
  const hash = currentModelHash();
  const review = (state.event?.reviews || []).filter(r => r.seatLabel === label && (!hash || r.modelHash === hash) && (r.targetId || state.event.model.activeTargetId) === targetId).at(-1);
  const photo = (state.event?.evidence || []).find(p => p.id === review?.evidenceId && (!hash || p.modelHash === hash));
  if (review?.stale || photo?.stale || !photo) return 'pending';
  if (review.status === 'matched' && Math.abs((photo.eyeHeightM ?? 0) - 1.2) <= .001) return 'matched';
  if (review.status === 'mismatch') return 'mismatch';
  return 'pending';
}
function seatGrid(mode, filtered = false) {
  const all = filtered ? filteredSeats() : seats(), groups = new Map();
  for (const seat of all) {
    const key = `${seat.section}\u0000${seat.row}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(seat);
  }
  return `<div class="seat-grid" role="group" aria-label="${mode === 'preview' ? '3D 미리보기 좌석' : '작업 범위 좌석'}">${[...groups.values()].map(group => `<div class="seat-group"><div class="seat-group-label">${escape(group[0].section)}<br>${escape(group[0].row + 1)}행</div><div class="seat-buttons">${group.sort((a, b) => a.x - b.x).map(seat => `<button type="button" class="seat-button ${seatReviewStatus(seat.label)}" data-seat="${escape(seat.label)}" data-seat-mode="${mode}" aria-pressed="${mode === 'preview' ? seat.label === state.selectedSeat : scope().selected.has(seat.label)}" aria-label="${escape(`${seat.section} ${seat.row + 1}행 ${seat.label} 좌석${mode === 'preview' ? ' 미리보기' : ' 범위 선택'}`)}">${escape(seat.label)}</button>`).join('')}</div></div>`).join('') || '<p class="help">선택한 조건에 해당하는 좌석이 없습니다.</p>'}</div>`;
}
function scopeView() {
  return `${scopeFields()}<div class="seat-tools">${button('이 구역·행 모두 선택', 'scope-all', 'small')}${button('현장대조 좌석 선택', 'scope-matched', 'small')}${button('선택 해제', 'scope-clear', 'subtle small')}</div><div id="scope-grid">${seatGrid('scope', true)}</div><div class="seat-legend"><span><i class="legend-dot"></i>사진 대조 일치</span><span><i class="legend-dot warn"></i>불일치</span><span><i class="legend-dot neutral"></i>대조 대기</span></div><p class="help" id="scope-count" style="margin-top:12px">선택한 좌석 ${scope().selected.size}개 · 구역·행 필터 밖의 선택도 포함됩니다.</p>`;
}
function floorView() {
  return card('좌석 바닥높이 일괄 수정', '구역·행으로 좁힌 뒤 적용할 좌석을 선택하세요.', `${scopeView()}<div class="divider"></div>${form('floor-form', `${field('seat-floor', '선택 좌석의 바닥높이 (m)', '', { type: 'number', required: true, min: -20, maxValue: 100, help: '눈높이가 아닌 좌석이 놓인 바닥의 절대 높이입니다.' })}<div class="actions"><small>같은 값으로 선택 좌석 전체를 수정합니다.</small>${submit('미리보기에 적용')}</div>`)}`);
}

function layoutView() {
  const m = draft().model, items = obstacles(m), targetItems = targets(m);
  const obstacle = items.find(item => item.id === state.obstacleId) || items[0];
  const target = targetItems.find(item => item.id === state.targetId) || targetItems[0];
  state.obstacleId = obstacle?.id || ''; state.targetId = target.id;
  const obstacleList = items.map(item => `<button type="button" class="item-button" data-obstacle="${escape(item.id)}" aria-pressed="${item.id === state.obstacleId}">${icon('cube')}<div><strong>${escape(item.name)}</strong><small>${escape(item.size.map(n => Number(n).toFixed(2)).join(' × '))} m · ${escape(item.id)}</small></div><span>편집</span></button>`).join('');
  let html = card('공연 설치물', '이 공연의 고정 설치물은 모든 좌석 시야에 반영됩니다.', `<div class="list-toolbar"><span>${items.length}개 설치물</span>${button('설치물 추가', 'add-obstacle', 'small', 'plus')}</div><div class="item-list">${obstacleList || '<div class="empty"><p>등록된 설치물이 없습니다. 난간, 카메라, 스피커 등의 치수를 추가하세요.</p></div>'}</div>${obstacle ? form('obstacle-form', `${field('obstacle-name', '설치물 이름', obstacle.name, { required: true, max: 80 })}${field('obstacle-id', '설치물 ID', obstacle.id, { required: true, max: 60, help: '영문·숫자·밑줄·하이픈으로 중복 없이 입력하세요.' })}${vector('obstacle-position', '중심 위치 (m)', obstacle.position)}${vector('obstacle-size', '크기 (m)', obstacle.size, ['폭 X', '높이 Y', '깊이 Z'], .02)}${vector('obstacle-rotation', '회전 (°)', obstacle.rotation || [0, 0, 0])}<div class="actions">${button('이 설치물 삭제', 'delete-obstacle', 'danger small')}${submit('미리보기에 적용')}</div>`) : ''}`);
  html += card('관람대상', '무대, 스크린, 전광판 등 시야를 확인할 영역을 지정하세요.', `<div class="list-toolbar"><span>${targetItems.length}개 관람대상</span>${button('관람대상 추가', 'add-target', 'small', 'plus')}</div><div class="actions" style="margin-bottom:12px">${button('영화관 스크린 초깃값', 'preset-cinema', 'subtle small')}${button('경기장 전광판 초깃값', 'preset-stadium', 'subtle small')}</div><p class="help" style="margin-bottom:15px">초깃값은 관람대상과 공간 종류를 설정합니다. 기존 좌석은 유지되며, 실제 크기·위치는 현장에서 확인해 수정하세요.</p><div class="item-list">${targetItems.map(item => `<button type="button" class="item-button" data-target="${escape(item.id)}" aria-pressed="${item.id === state.targetId}">${icon('eye')}<div><strong>${escape(item.name)}</strong><small>${escape(item.size.join(' × '))} m · ${escape(item.id)}</small></div>${m.activeTargetId === item.id ? '<span>기본</span>' : '<span>편집</span>'}</button>`).join('')}</div>${form('target-form', `${field('target-name', '관람대상 이름', target.name, { required: true, max: 80 })}${field('target-id', '관람대상 ID', target.id, { required: true, max: 60, help: '영문·숫자·밑줄·하이픈으로 중복 없이 입력하세요.' })}${vector('target-position', '영역 중심 위치 (m)', target.position)}${vector('target-size', '관람 영역 크기 (m)', target.size, ['폭 W', '높이 H'], .1)}${vector('target-rotation', '회전 (°)', target.rotation || [0, 0, 0])}<label class="check-line"><input type="checkbox" id="target-default" ${m.activeTargetId === target.id || !m.activeTargetId ? 'checked' : ''}><span>관객 화면에서 처음 보여 줄 관람대상으로 설정</span></label><div class="actions">${targetItems.length > 1 ? button('이 관람대상 삭제', 'delete-target', 'danger small') : ''}${submit('미리보기에 적용')}</div>`)}`);
  html += `<div class="note" style="margin-top:16px">회전은 X·Y·Z축의 각도를 도(°)로 입력합니다. 설치물과 관람대상을 적용한 뒤 상단의 변경사항 저장을 눌러 주세요.</div>`;
  return html;
}

function photoDraft() { return state.photos.get(state.event?.id); }
function reviewView() {
  const e = state.event, photo = photoDraft(), label = state.selectedSeat || seats()[0]?.label;
  let html = card('현장 대조 범위', '선택한 좌석은 게시 단계에서도 그대로 사용할 수 있습니다.', scopeView(), pill(`${scope().selected.size}개 선택`, 'neutral'));
  html += card('현장 사진 등록', '좌석 시점의 미리보기와 같은 방향으로 촬영한 사진을 등록하세요.', `${draft().dirty || draft().pending.size ? '<div class="note warn" style="margin-bottom:17px">배치 변경을 먼저 저장한 뒤 사진을 등록하세요. 사진은 저장된 모델과 연결됩니다.</div>' : ''}${form('evidence-form', `${selectField('photo-seat', '촬영한 좌석', seats().map(seat => [seat.label, `${seat.section} · ${seat.label}`]), label)}${field('photo-target-label', '촬영한 관람대상 (현재 미리보기)', targets(draft().model).find(t => t.id === state.targetId)?.name || '', { readonly: true })}<label class="field" for="photo-file"><span>현장 사진 파일</span><input id="photo-file" type="file" accept="image/jpeg,image/png,image/webp"><small>JPEG·PNG·WebP → 브라우저에서 JPEG로 다시 인코딩 · 최대 1.5MB · 원본 메타데이터 제거</small></label><div id="photo-preview" class="photo-preview" ${photo?.dataUrl || photo?.processing || photo?.error ? '' : 'hidden'}>${photoPreviewView(photo)}</div><div class="form-grid">${field('photo-captured-at', '실제 촬영일', localDateTime().slice(0, 10), { type: 'date', required: true })}${field('photo-eye-height', '촬영 기준 눈높이 (m)', '1.20', { type: 'number', readonly: true, help: '현장 검수는 좌석 바닥 위 1.20m를 기준으로 합니다.' })}${field('photo-lens', '렌즈 · 카메라 설정', '', { required: true, max: 100, wide: true, placeholder: '예: 스마트폰 기본 1배 렌즈, 광각 보정 끔' })}</div>${textarea('photo-note', '촬영 조건 메모 (필수)', '', '설치 상태, 촬영 방향, 사진과 모델의 차이를 남기세요.', { required: true, max: 500 })}<label class="check-line"><input type="checkbox" id="photo-share"><span>이 사진을 공개 화면에도 표시합니다. 촬영·게시 권한과 식별 가능한 인물의 동의를 확인했습니다.</span></label><p class="help">공개하지 않은 사진도 운영자 대조 자료로 저장됩니다. JPEG 재인코딩은 위치·기기 등 원본 메타데이터를 제거하지만, 사진 안의 얼굴과 글자는 지우지 않습니다.</p><div class="actions">${submit('현장 사진 등록')}</div>`)}`);
  const evidence = (e.evidence || []).filter(item => item.seatLabel === label && (item.targetId || e.model.activeTargetId) === state.targetId).slice().reverse();
  html += card(`${label} 좌석의 현장 대조`, '선택한 관람대상의 사진과 3D 미리보기를 함께 확인하세요.', `<div class="note">사진 한 장으로 전체 공간을 검수하지 않습니다. 각 좌석과 동일한 공연 배치·눈높이·촬영 조건을 확인하세요.${!currentModelHash() ? ' 현재 모델과의 일치 여부는 저장 시 서버에서 최종 확인합니다.' : ''}</div>${evidence.length ? evidence.map(evidenceCard).join('') : '<div class="empty" style="margin-top:15px">' + icon('camera') + '<h3>이 좌석의 등록 사진이 없습니다.</h3><p>미리보기 좌석을 바꾸거나, 위에서 이 좌석의 사진을 등록하세요.</p></div>'}`);
  return html;
}
function photoPreviewView(photo) {
  if (!photo) return '';
  if (photo.processing) return '사진을 JPEG로 변환하고 있습니다…';
  if (photo.error) return escape(photo.error);
  return `<img src="${escape(photo.dataUrl)}" alt="등록 전 현장 사진 미리보기"><span>${escape(photo.name)} · JPEG ${(photo.bytes / 1_000_000).toFixed(2)}MB · 원본 메타데이터 제거됨</span>${button('선택 사진 지우기', 'clear-photo', 'subtle small')}`;
}
function evidenceCard(evidence) {
  const result = evidenceState(evidence);
  const statusText = { matched: '대조 일치', mismatch: '대조 불일치', pending: '대조 대기', stale: '이전 배치 · 재대조 필요' };
  return `<article class="evidence-card">${evidence.assetId ? `<img src="/api/v1/assets/${pathId(evidence.assetId)}" alt="${escape(`${evidence.seatLabel} 좌석 현장 대조 사진`)}" loading="lazy">` : ''}<div class="evidence-body"><div class="evidence-meta"><h3>${escape(evidence.seatLabel)} 좌석</h3>${pill(statusText[result.status] || '대조 대기', result.status === 'matched' ? '' : 'warn')}</div><p>촬영 ${escape(formatDate(evidence.capturedAt))} · 눈높이 ${escape(evidence.eyeHeightM ?? 1.2)}m</p><p>렌즈: ${escape(evidence.lens || '설정 미기록')} · ${evidence.sharePhoto ? '공개 사진' : '운영자용 사진'}</p>${evidence.note ? `<p>${escape(evidence.note)}</p>` : ''}${result.stale ? '<div class="note warn" style="margin-top:12px">이 사진은 현재 배치에 사용할 수 없습니다. 현재 배치로 다시 촬영해 등록하세요.</div>' : form(`review-form-${escape(evidence.id)}`, `${textarea(`review-note-${escape(evidence.id)}`, '대조 판단 메모 (필수)', result.review?.note || '', '어떤 부분을 확인했는지, 차이가 있는지 기록하세요.', { required: true, max: 800 })}<div class="actions"><button type="submit" name="status" value="matched" class="button primary">${icon('check')}사진과 일치</button><button type="submit" name="status" value="mismatch" class="button danger">차이 있음</button></div>`)}</div></article>`;
}

function publishView() {
  const e = state.event, publication = e.publication, count = scope().selected.size;
  const reviewedSeats = seats().filter(seat => seatReviewStatus(seat.label) === 'matched').length;
  let html = card('게시할 좌석 선택', '현장 대조를 마친 좌석만 공개하거나, 검수 전 시연으로 게시하세요.', `${scopeView()}<div class="divider"></div><div class="stat-grid"><div class="stat"><span>전체 좌석</span><strong>${seats().length}</strong></div><div class="stat"><span>대조 일치 기록</span><strong>${reviewedSeats}</strong></div><div class="stat"><span>게시 선택</span><strong>${count}</strong></div></div><p class="help">관객 화면의 기본 관람대상에 대한 대조 기록을 집계합니다. 모델·사진·촬영 조건이 현재 공연과 같은지 서버가 확인합니다. 배치가 바뀐 좌석은 다시 촬영하고 대조하세요.</p>`);
  html += card('공개 설정', '게시하면 현재 모델과 선택 좌석의 고정 스냅샷이 만들어집니다.', `${publication?.stale ? '<div class="note warn" style="margin-bottom:18px">배치 또는 적용 회차 변경으로 기존 공개가 자동 중지되었습니다. 다시 게시하면 새 링크가 발급되며, 기존 링크는 사용할 수 없습니다.</div>' : ''}${form('publish-form', `${selectField('publication-mode', '게시 방식', [['reviewed', '현장 대조 완료 · 선택한 좌석만 공개'], ['demo', '현장 검수 전 · 시연 표시로 공개']], 'reviewed')}<div class="note warn" id="publication-mode-note" style="margin-bottom:17px">현장 대조 게시에는 선택 좌석마다 현재 모델과 연결된 사진 및 일치 검수가 필요합니다.</div>${field('publication-reviewer', '게시 책임자 이름', '', { required: true, max: 80, placeholder: '실제 검수·게시를 책임지는 운영자' })}${textarea('publication-origins', '위젯을 사용할 사이트 주소 (선택)', '', '사이트 출처만 한 줄씩 입력하세요. 예: https://tickets.example.com · 경로와 하위 도메인은 따로 허용할 수 없습니다.')}<label class="check-line"><input type="checkbox" id="publication-rights" required><span>모델·도면·사진을 게시할 권한을 확인했습니다. 선택 좌석의 게시 방식과 공개 범위를 확인했습니다.</span></label><div class="actions"><small>선택한 ${count}개 좌석으로 게시합니다.</small>${submit(publication ? '현재 버전 다시 게시' : '선택 좌석 게시')}</div>`)}`);
  html += publication ? publicationView(publication) : card('공개 링크와 예매 연동', '게시 후 관객 링크와 위젯 코드를 사용할 수 있습니다.', '<div class="empty">' + icon('link') + '<h3>아직 게시하지 않은 공연입니다.</h3><p>게시 범위와 책임자를 확인하고 게시하면 링크가 준비됩니다.</p></div>');
  const stats = state.stats.get(e.id) || e.stats || {};
  html += card('이 공연의 이용 지표', '이 공연의 현재·이전 공개본 이용 기록을 합산합니다.', `<div class="stat-grid"><div class="stat"><span>화면 조회</span><strong>${escape(statValue(stats, ['view']))}</strong></div><div class="stat"><span>좌석 비교</span><strong>${escape(statValue(stats, ['compare']))}</strong></div><div class="stat"><span>예매 이동</span><strong>${escape(statValue(stats, ['ticket_out']))}</strong></div></div><p class="help">— 는 아직 해당 지표를 불러오지 않았다는 뜻입니다.</p><div class="actions">${button('최신 지표 불러오기', 'refresh-stats', 'subtle small', 'reset')}</div>`);
  return html;
}
function statValue(stats, keys) {
  for (const key of keys) if (typeof stats[key] === 'number' && Number.isFinite(stats[key])) return stats[key].toLocaleString('ko-KR');
  return '—';
}
function publicUrl(value, fallback) {
  try {
    const url = new URL(value || fallback, window.location.origin);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.origin !== window.location.origin) return new URL(fallback, window.location.origin).href;
    return url.href;
  } catch { return new URL(fallback, window.location.origin).href; }
}
function publicationView(publication) {
  const query = `publication=${pathId(publication.slug)}`;
  const viewerUrl = publicUrl(publication.viewerUrl, `/viewer.html?${query}`);
  const embedUrl = publicUrl(publication.embedUrl, `/viewer.html?${query}`);
  const integrationUrl = new URL(`/integration.html?${query}`, location.origin).href;
  const iframe = `<iframe src="${embedUrl.replaceAll('&', '&amp;').replaceAll('"', '&quot;')}" title="좌석 시야 미리보기" width="100%" height="640" style="border:0" loading="lazy" referrerpolicy="strict-origin-when-cross-origin" allow="fullscreen"></iframe>`;
  return card('공개 링크와 위젯', `게시 ${formatDate(publication.publishedAt)} · ${publication.mode === 'demo' ? '현장 검수 전 시연' : '현장 대조 좌석 공개'}`, `<div class="note ${publication.stale ? 'warn' : ''}">${publication.stale ? '배치 또는 회차 변경으로 공개가 자동 중지되었습니다. 다시 게시한 새 링크와 위젯 코드로 교체하세요. 이전 배치 사진은 현재 모델의 대조에 사용할 수 없습니다.' : publication.mode === 'demo' ? '관객 화면에 현장 검수 전 시연임이 표시됩니다.' : '검수를 통과한 선택 좌석으로 공개되었습니다.'}</div><div class="publication-links"><label class="field" for="viewer-url"><span>관객용 링크</span><div class="copy-row"><input id="viewer-url" readonly value="${escape(viewerUrl)}">${button('링크 복사', 'copy-viewer', 'small', 'copy')}</div></label><label class="field" for="embed-code"><span>사이트 삽입용 iframe 코드</span><div class="copy-row"><textarea id="embed-code" readonly rows="4">${escape(iframe)}</textarea>${button('코드 복사', 'copy-embed', 'small', 'copy')}</div></label><label class="field" for="integration-url"><span>예매 연동 샘플 링크</span><div class="copy-row"><input id="integration-url" readonly value="${escape(integrationUrl)}">${button('샘플 링크 복사', 'copy-integration', 'small', 'copy')}</div></label><div class="link-row"><a class="button small" href="${escape(viewerUrl)}" target="_blank" rel="noopener">관객 화면 열기 ${icon('arrow')}</a><a class="button subtle small" href="${escape(integrationUrl)}" target="_blank" rel="noopener">예매 연동 샘플 ${icon('arrow')}</a></div></div><details class="detail-box" id="unpublish-details"><summary>게시 중지</summary><div><p class="help">게시를 중지하면 이 공연의 공개 링크가 더 이상 제공되지 않습니다. 공연 배치와 대조 자료는 운영 화면에 남습니다.</p>${button('이 공연 게시 중지', 'unpublish', 'danger')}</div></details>`, pill(publication.stale ? '공개 자동 중지' : '게시 중', publication.stale ? 'warn' : ''));
}

function renderPreview() {
  const d = draft();
  if (!d || !state.auth?.authenticated) {
    preview?.destroy?.(); preview = null; previewKey = '';
    $('#scene').innerHTML = `<div class="scene-empty">${icon('cube')}<span>공연을 선택하면 공간을 미리 볼 수 있습니다.</span></div>`;
    return;
  }
  const allSeats = seats(), allTargets = targets(d.model);
  if (!allSeats.some(seat => seat.label === state.selectedSeat)) state.selectedSeat = allSeats[0]?.label || '';
  if (!allTargets.some(target => target.id === state.targetId)) state.targetId = d.model.activeTargetId || allTargets[0]?.id || '';
  state.view.selected = Math.max(0, allSeats.findIndex(seat => seat.label === state.selectedSeat));
  state.view.targetId = state.targetId;
  $('#preview-controls').innerHTML = `<div class="form-grid">${selectField('preview-seat', '미리보기 좌석', allSeats.map(seat => [seat.label, `${seat.section} · ${seat.label}`]), state.selectedSeat)}${selectField('preview-target', '관람대상 전환', allTargets.map(target => [target.id, target.name]), state.targetId)}</div><div class="preview-bottom"><label class="check-line"><input id="preview-overlay" type="checkbox" ${state.view.overlay ? 'checked' : ''}>가린 표본 표시</label>${button('정면으로 되돌리기', 'reset-preview', 'subtle small', 'reset')}</div>`;
  $('#preview-map').innerHTML = `<div class="section-heading"><h3>좌석을 눌러 시점 전환</h3><span class="muted" style="font-size:10px">${allSeats.length}석</span></div>${seatGrid('preview')}`;
  $('#scene-tag').hidden = false;
  $('#scene-tag').textContent = `${state.selectedSeat} · ${allTargets.find(target => target.id === state.targetId)?.name || ''}${d.dirty ? ' · 미저장 배치' : ''}`;
  document.querySelectorAll('[data-view]').forEach(el => el.setAttribute('aria-pressed', String(el.dataset.view === state.view.mode)));
  try {
    const key = `${state.event.id}:${JSON.stringify(d.model)}`;
    if (!preview) {
      $('#scene').replaceChildren();
      preview = new VenueViewer($('#scene'), text => { $('#scene-status').textContent = text; });
    }
    if (key !== previewKey) { preview.rebuild(d.model, 'theatre'); previewKey = key; }
    preview.setView(state.view);
    const result = Model.analyzeSightline(d.model, allSeats[state.view.selected], 'theatre', 1.2, state.targetId);
    $('#sightline-summary').innerHTML = `<strong>${escape(result.visible)}<small>%</small></strong><p>가리지 않은 관람대상 표본<br>${escape(Model.describeSightline(result))}</p>`;
  } catch (error) {
    $('#scene-status').textContent = `미리보기: ${error.message}`;
    $('#sightline-summary').innerHTML = '<p>3D 미리보기를 실행하지 못했습니다. 입력과 저장 기능은 계속 이용할 수 있습니다.</p>';
  }
}

function model3(model) {
  return clone(Model.toVenueModel(model));
}
function applyModel(candidate, formId) {
  const validated = Model.validateModel(candidate);
  draft().model = validated; draft().dirty = true;
  if (formId) draft().pending.delete(formId);
  return validated;
}
function value(id) { return document.getElementById(id)?.value ?? ''; }
function number(id) {
  if (!value(id).trim()) throw new Error('빈 치수 항목이 있습니다. 위치·크기·회전을 모두 입력하세요.');
  const n = Number(value(id)); if (!Number.isFinite(n)) throw new Error('치수는 유한한 숫자로 입력하세요.'); return n;
}
function readVector(prefix, length = 3) { return Array.from({ length }, (_, i) => number(`${prefix}-${i}`)); }
function ensureSaved() {
  if (draft()?.dirty || draft()?.pending.size) throw new Error('작성한 공간·배치 변경을 먼저 적용하고 저장하세요. 저장된 모델을 기준으로 현장 대조와 게시를 진행합니다.');
}
function initializeDraft(event) {
  state.drafts.set(event.id, { model: clone(event.model), name: event.name, sessionLabel: event.sessionLabel || '', baseName: event.name, baseSession: event.sessionLabel || '', dirty: false, pending: new Set(), conflict: false, baseRevision: event.revision });
}
async function acceptEvent(event, { replaceDraft = false } = {}) {
  if (!event?.id || !event.model) throw new Error('서버가 공연 모델을 반환하지 않았습니다.');
  try {
    // This serialization is shared with Repository.geometryHash; no browser-only geometry is used.
    const { seats, targets, activeTargetId, obstacles, venueType } = Model.toVenueModel(event.model);
    const bytes = new TextEncoder().encode(JSON.stringify({ seats, targets, activeTargetId, obstacles, venueType }));
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    state.hashes.set(event.id, [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, '0')).join(''));
  } catch { state.hashes.delete(event.id); }
  state.event = event;
  if (state.project?.id === event.projectId) {
    const events = state.project.events || [];
    const index = events.findIndex(item => item.id === event.id);
    if (index < 0) events.push(event); else events[index] = event;
    state.project.events = events;
    const summary = state.projects.find(p => p.id === event.projectId);
    if (summary) { summary.eventCount = events.length; summary.updatedAt = event.updatedAt; }
  }
  if (replaceDraft || !state.drafts.has(event.id)) initializeDraft(event);
  else {
    const d = draft();
    if (!d.dirty && !d.pending.size) { d.model = clone(event.model); d.name = event.name; d.sessionLabel = event.sessionLabel || ''; }
    else if (d.baseRevision !== event.revision) {
      d.conflict = true;
      // Preserve local edits without overwriting another operator's untouched metadata.
      if (!d.pending.has('space-form')) {
        if (d.name === d.baseName) {
          d.name = event.name;
          state.forms.get(`${event.id}:space`)?.values.delete('event-name');
        }
        if (d.sessionLabel === d.baseSession) {
          d.sessionLabel = event.sessionLabel || '';
          state.forms.get(`${event.id}:space`)?.values.delete('event-session');
        }
      }
    }
    d.baseName = event.name; d.baseSession = event.sessionLabel || '';
    d.baseRevision = event.revision;
  }
  scope().selected = new Set([...scope().selected].filter(label => seats().some(seat => seat.label === label)));
}

async function loadProject(id, eventId, { preserve = true } = {}) {
  if (preserve) captureForms();
  state.controller?.abort();
  const controller = state.controller = new AbortController(), sequence = ++state.sequence;
  state.loading = true; renderChrome();
  try {
    const data = await api(`/projects/${pathId(id)}`, { signal: controller.signal });
    if (sequence !== state.sequence) return;
    if (!data.project || !Array.isArray(data.project.events)) throw new Error('프로젝트 응답에 공연 목록이 없습니다.');
    state.project = data.project;
    const events = data.project.events;
    const wanted = events.find(e => e.id === eventId) || events[0];
    state.event = null;
    if (wanted) {
      const event = wanted.model ? wanted : (await api(`/events/${pathId(wanted.id)}`, { signal: controller.signal })).event;
      if (sequence !== state.sequence) return;
      await acceptEvent(event);
    }
    state.selectedSeat = draft()?.selection?.selectedSeat || seats()[0]?.label || '';
    state.targetId = draft()?.selection?.targetId || draft()?.model.activeTargetId || '';
    state.obstacleId = draft()?.selection?.obstacleId || '';
    state.message = null;
  } catch (error) {
    if (sequence === state.sequence && error.name !== 'AbortError') notify(error.message);
  } finally {
    if (sequence === state.sequence) { state.loading = false; renderEditor({ capture: false }); if (state.step === 'publish' && state.event) await loadStats(); }
  }
}
async function boot() {
  captureForms(); state.loading = true; renderEditor({ capture: false });
  const sequence = ++state.sequence;
  try {
    const auth = await api('/auth');
    if (sequence !== state.sequence) return;
    state.auth = auth;
    if (auth.authenticated) {
      const result = await api('/projects');
      if (sequence !== state.sequence) return;
      if (!Array.isArray(result.projects)) throw new Error('프로젝트 목록 응답을 확인할 수 없습니다.');
      state.projects = result.projects;
      const selected = result.projects.find(p => p.id === state.project?.id) || result.projects[0];
      state.loading = false;
      if (selected) { await loadProject(selected.id, state.event?.id, { preserve: false }); return; }
      state.project = null; state.event = null;
    }
    state.message = null;
  } catch (error) { notify(error.message); }
  finally { if (sequence === state.sequence) { state.loading = false; renderEditor({ capture: false }); } }
}
async function recoverConflict(id) {
  const projectId = state.project?.id;
  const data = await api(`/projects/${pathId(projectId)}`);
  if (state.event?.id !== id || state.project?.id !== projectId) return;
  const summary = data.project?.events?.find(event => event.id === id);
  const event = summary?.model ? summary : (await api(`/events/${pathId(id)}`)).event;
  if (state.event?.id === id && event) { await acceptEvent(event); draft().conflict = true; }
}
async function mutation(run, success = '') {
  if (state.busy || state.loading) return;
  captureForms(); const eventId = state.event?.id;
  state.busy = true; renderChrome(); applyBusy();
  try {
    await run();
    state.message = null;
    if (success) toast(success);
  } catch (error) {
    if (error.status === 409 && eventId) {
      try { await recoverConflict(eventId); }
      catch (refreshError) { notify(`${error.message} 최신 자료를 불러오지 못했습니다: ${refreshError.message}`, 'error', '동시 편집 충돌'); return; }
      notify(`${error.message} 최신 서버 자료를 불러왔으며 입력은 유지했습니다. 변경과 공개 범위를 확인한 뒤 다시 시도하세요.`, 'warn', error.code === 'STALE_EVIDENCE' ? '현재 배치로 다시 촬영해야 합니다' : '다른 운영자의 변경사항이 있습니다');
    } else {
      if (error.status === 401) state.auth = { ...state.auth, authenticated: false };
      notify(error.message, 'error', error.code ? `처리하지 못했습니다 · ${error.code}` : '입력은 유지됩니다');
    }
  } finally { state.busy = false; renderEditor({ capture: false }); }
}
async function saveDraft() {
  const d = draft();
  if (!d || d.pending.size) throw new Error('입력한 폼을 먼저 미리보기에 적용하세요.');
  const result = await api(`/events/${pathId(state.event.id)}`, { method: 'PATCH', body: { expectedRevision: state.event.revision, model: d.model, name: d.name, sessionLabel: d.sessionLabel } });
  await acceptEvent(result.event, { replaceDraft: true });
}
async function loadStats() {
  const id = state.event?.id, sequence = ++state.statsSequence;
  if (!id) return;
  try {
    const result = await api(`/events/${pathId(id)}/stats`);
    if (sequence !== state.statsSequence) return;
    state.stats.set(id, result.stats || {});
    if (state.event?.id === id && state.step === 'publish') renderEditor();
  } catch (error) { if (state.event?.id === id && sequence === state.statsSequence) notify(error.message, 'error', '이용 지표를 불러오지 못했습니다'); }
}

function localDateTime() {
  const date = new Date(); return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}
function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '일시 미기록' : date.toLocaleString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}
async function encodePhoto(file) {
  if (!file || !['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) throw new Error('JPEG·PNG·WebP 사진 파일을 선택하세요.');
  if (file.size > 30_000_000) throw new Error('원본 사진은 30MB 이하로 선택하세요.');
  const objectUrl = URL.createObjectURL(file);
  try {
    const image = new Image(); image.src = objectUrl; await image.decode();
    if (!image.naturalWidth || !image.naturalHeight || image.naturalWidth * image.naturalHeight > 100_000_000) throw new Error('사진 크기가 너무 크거나 이미지가 손상되었습니다. 작은 사진으로 다시 선택하세요.');
    const canvas = document.createElement('canvas');
    let scale = Math.min(1, 1920 / Math.max(image.naturalWidth, image.naturalHeight));
    let blob;
    for (let attempt = 0; attempt < 8; attempt++) {
      canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
      canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
      const ctx = canvas.getContext('2d');
      if (!ctx) throw new Error('사진 변환을 실행할 수 없습니다. 다른 브라우저에서 다시 시도하세요.');
      ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, canvas.width, canvas.height); ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
      blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', Math.max(.5, .88 - attempt * .06)));
      if (!blob) throw new Error('JPEG 사진을 만들지 못했습니다.');
      // The limit also covers the base64 data URL sent in the JSON request.
      if (blob.size <= MAX_PHOTO_BYTES && 4 * Math.ceil(blob.size / 3) + 23 <= MAX_PHOTO_BYTES) break;
      scale *= .82;
    }
    if (!blob || blob.size > MAX_PHOTO_BYTES || 4 * Math.ceil(blob.size / 3) + 23 > MAX_PHOTO_BYTES) throw new Error('사진을 1.5MB 이하로 줄이지 못했습니다. 작은 사진을 선택하세요.');
    const dataUrl = await new Promise((resolve, reject) => {
      const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = () => reject(new Error('변환 사진을 읽지 못했습니다.')); reader.readAsDataURL(blob);
    });
    if (!dataUrl.startsWith('data:image/jpeg;base64,')) throw new Error('사진을 JPEG로 변환하지 못했습니다.');
    return { dataUrl, bytes: blob.size, name: file.name };
  } finally { URL.revokeObjectURL(objectUrl); }
}
async function choosePhoto(file) {
  const eventId = state.event?.id, sequence = ++photoSequence;
  if (!eventId || !file) return;
  const previous = state.photos.get(eventId);
  state.photos.set(eventId, { ...previous, processing: true });
  if ($('#photo-preview')) { $('#photo-preview').hidden = false; $('#photo-preview').innerHTML = photoPreviewView(state.photos.get(eventId)); }
  try {
    const encoded = await encodePhoto(file);
    if (sequence !== photoSequence) return;
    state.photos.set(eventId, { ...encoded, processing: false });
  } catch (error) {
    if (sequence !== photoSequence) return;
    state.photos.set(eventId, { ...previous, processing: false, error: error.message });
    if (state.event?.id === eventId) notify(error.message);
  } finally {
    if (state.event?.id === eventId && sequence === photoSequence && $('#photo-preview')) {
      $('#photo-preview').innerHTML = photoPreviewView(state.photos.get(eventId)); $('#photo-preview').hidden = false;
    }
  }
}

async function handleSubmit(event) {
  const el = event.target.closest('form');
  if (!el) return;
  event.preventDefault();
  if (state.busy || state.loading) return;
  const id = el.id;
  try {
    if (id === 'login-form') {
      const token = value('auth-token');
      state.loginToken = token;
      await mutation(async () => { await api('/auth', { method: 'POST', body: { token } }); state.auth = { mode: 'token', authenticated: true }; state.loginToken = ''; }, '운영자로 로그인했습니다.');
      if (state.auth?.authenticated) await boot();
    } else if (id === 'project-form') {
      const name = value('project-create-name').trim();
      await mutation(async () => {
        const result = await api('/projects', { method: 'POST', body: { name, ...(state.projectModel ? { model: state.projectModel } : {}) } });
        state.project = result.project; state.event = null;
        state.projects.push({ id: result.project.id, name: result.project.name, updatedAt: result.project.updatedAt, eventCount: 0 });
        state.forms.delete(formKey());
        state.projectModel = null;
      }, '프로젝트를 만들었습니다. 첫 공연을 추가해 주세요.');
    } else if (id === 'event-form') {
      const name = value('event-create-name').trim(), cloneEventId = value('event-clone-source');
      const previousKey = formKey();
      await mutation(async () => {
        const result = await api(`/projects/${pathId(state.project.id)}/events`, { method: 'POST', body: { name, ...(cloneEventId ? { cloneEventId } : {}) } });
        await acceptEvent(result.event, { replaceDraft: true }); state.selectedSeat = seats()[0]?.label || ''; state.targetId = draft().model.activeTargetId || ''; state.obstacleId = '';
        state.forms.delete(previousKey); state.forms.delete(formKey());
      }, '공연을 만들었습니다. 배치 단계에서 설치물과 관람대상을 확인하세요.');
    } else if (id === 'space-form') {
      const m = model3(draft().model);
      m.name = value('venue-name').trim(); m.venueType = value('venue-type'); m.stageWidth = number('stage-width'); m.stageDepth = number('stage-depth'); m.stageHeight = number('stage-height'); m.targetHeight = number('target-height'); m.ticketUrl = value('ticket-url').trim();
      applyModel(m, id); draft().name = value('event-name').trim(); draft().sessionLabel = value('event-session').trim();
      await mutation(saveDraft, '공간 정보를 저장했습니다.');
    } else if (id === 'floor-form') {
      const labels = scope().selected;
      if (!labels.size) throw new Error('바닥높이를 적용할 좌석을 먼저 선택하세요.');
      const height = number('seat-floor'), m = model3(draft().model);
      m.seats = m.seats.map(seat => labels.has(seat.label) ? { ...seat, floor: height } : seat);
      applyModel(m, id); renderEditor(); toast(`${labels.size}개 좌석의 바닥높이를 적용했습니다. 변경사항을 저장하세요.`);
    } else if (id === 'obstacle-form') {
      const m = model3(draft().model), previousId = state.obstacleId;
      const item = { id: value('obstacle-id').trim(), name: value('obstacle-name').trim(), position: readVector('obstacle-position'), size: readVector('obstacle-size'), rotation: readVector('obstacle-rotation'), layout: 'all' };
      m.obstacles = m.obstacles.map(o => o.id === previousId ? item : o);
      applyModel(m, id); state.obstacleId = item.id; renderEditor(); toast('설치물을 적용했습니다. 변경사항을 저장하세요.');
    } else if (id === 'target-form') {
      const m = model3(draft().model), previousId = state.targetId;
      const item = { id: value('target-id').trim(), name: value('target-name').trim(), position: readVector('target-position'), size: readVector('target-size', 2), rotation: readVector('target-rotation') };
      m.targets = m.targets.map(t => t.id === previousId ? item : t);
      if ($('#target-default').checked || m.activeTargetId === previousId) m.activeTargetId = item.id;
      applyModel(m, id); state.targetId = item.id; renderEditor(); toast('관람대상을 적용했습니다. 변경사항을 저장하세요.');
    } else if (id === 'import-form') {
      const file = $('#model-file').files[0], text = value('model-json').trim();
      if (!file && !text) throw new Error('모델 파일을 선택하거나 모델 내용을 붙여넣으세요.');
      if (file && text) throw new Error('모델 파일과 직접 입력 중 하나만 사용하세요. 입력 내용은 유지했습니다.');
      if (file?.size > 5_000_000) throw new Error('모델 파일은 5MB 이하로 선택하세요.');
      const eventId = state.event.id;
      if (file) { const content = await file.text(); if (state.event?.id !== eventId) return; $('#model-json').value = content; $('#model-file').value = ''; }
      let model; try { model = JSON.parse(value('model-json')); } catch { throw new Error('모델 JSON 형식을 읽지 못했습니다. 쉼표와 괄호를 확인하세요.'); }
      applyModel(model, id); state.targetId = draft().model.activeTargetId || ''; state.obstacleId = ''; state.selectedSeat = seats()[0]?.label || '';
      renderEditor(); toast('모델을 가져왔습니다. 3D 미리보기를 확인하고 변경사항을 저장하세요.');
    } else if (id === 'evidence-form') {
      ensureSaved();
      const photo = photoDraft();
      if (photo?.processing) throw new Error('사진 변환이 끝난 뒤 등록하세요.');
      if (!photo?.dataUrl || photo.error) throw new Error('정상적으로 변환된 사진을 선택하세요.');
      const capturedAt = new Date(value('photo-captured-at'));
      if (Number.isNaN(capturedAt.getTime())) throw new Error('실제 촬영 일시를 확인하세요.');
      const seatLabel = value('photo-seat');
      const body = { expectedRevision: state.event.revision, seatLabel, targetId: state.targetId || state.event.model.activeTargetId, photoDataUrl: photo.dataUrl, capturedAt: value('photo-captured-at'), eyeHeightM: 1.2, lens: value('photo-lens').trim(), note: value('photo-note').trim(), sharePhoto: $('#photo-share').checked };
      await mutation(async () => {
        const result = await api(`/events/${pathId(state.event.id)}/evidence`, { method: 'POST', body });
        await acceptEvent(result.event); state.photos.delete(state.event.id); state.selectedSeat = seatLabel;
        forgetFields('photo-');
      }, '사진을 등록했습니다. 아래에서 3D 미리보기와 대조해 주세요.');
    } else if (id.startsWith('review-form-')) {
      ensureSaved();
      const evidenceId = id.slice('review-form-'.length), status = event.submitter?.value;
      if (!['matched', 'mismatch'].includes(status)) throw new Error('일치 또는 차이 있음 버튼으로 대조 판단을 선택하세요.');
      const body = { expectedRevision: state.event.revision, evidenceId, status, note: value(`review-note-${evidenceId}`).trim() };
      await mutation(async () => { const result = await api(`/events/${pathId(state.event.id)}/reviews`, { method: 'POST', body }); await acceptEvent(result.event); }, status === 'matched' ? '사진 대조를 일치로 기록했습니다.' : '차이를 기록했습니다. 배치를 수정하고 다시 현장 대조하세요.');
    } else if (id === 'publish-form') {
      ensureSaved();
      if (!state.event.sessionLabel?.trim() || state.event.sessionLabel === '적용 회차 미지정') throw new Error('공간 단계에서 실제 적용 회차를 먼저 입력하고 저장하세요.');
      const seatLabels = seats().map(seat => seat.label).filter(label => scope().selected.has(label));
      if (!seatLabels.length) throw new Error('게시할 좌석을 하나 이상 선택하세요.');
      const mode = value('publication-mode'), reviewer = value('publication-reviewer').trim();
      const allowedOrigins = [...new Set(value('publication-origins').split(/[\n,]/).map(line => line.trim()).filter(Boolean).map(line => {
        let url; try { url = new URL(line); } catch { throw new Error(`사이트 주소를 확인하세요: ${line}`); }
        if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.pathname !== '/' || url.search || url.hash) throw new Error(`위젯 사이트에는 HTTP(S) 출처만 입력하세요: ${line}`);
        return url.origin;
      }))];
      if (!$('#publication-rights').checked || !reviewer) throw new Error('게시 책임자 이름과 게시 권한 확인이 필요합니다.');
      await mutation(async () => {
        const result = await api(`/events/${pathId(state.event.id)}/publish`, { method: 'POST', body: { expectedRevision: state.event.revision, mode, seatLabels, rightsConfirmed: true, reviewer, allowedOrigins } });
        await acceptEvent({ ...result.event, publication: result.publication || result.event.publication });
      }, mode === 'demo' ? '현장 검수 전 시연으로 게시했습니다.' : '현장 대조 좌석을 게시했습니다.');
    }
  } catch (error) { captureForms(); notify(error.message, 'error', '입력은 유지됩니다'); renderDraftNotice(); }
}

async function handleClick(event) {
  const el = event.target.closest('button');
  if (!el || el.type === 'submit' || state.busy || state.loading) return;
  try {
    if (el.dataset.step) {
      captureForms(); state.step = el.dataset.step; renderEditor({ capture: false }); if (state.step === 'publish') await loadStats(); return;
    }
    if (el.dataset.view) { state.view.mode = el.dataset.view; renderPreview(); return; }
    if (el.dataset.seat) {
      if (el.dataset.seatMode === 'preview') {
        captureForms(); state.selectedSeat = el.dataset.seat;
        if (state.step === 'review') { forgetFields('photo-seat'); renderEditor({ capture: false }); }
        else renderPreview();
      } else {
        const selected = scope().selected;
        if (selected.has(el.dataset.seat)) selected.delete(el.dataset.seat); else selected.add(el.dataset.seat);
        updateScope();
      }
      return;
    }
    if (el.dataset.obstacle || el.dataset.target) {
      captureForms();
      if (el.dataset.obstacle) {
        if (draft().pending.has('obstacle-form')) throw new Error('편집 중인 설치물을 먼저 미리보기에 적용하세요.');
        state.obstacleId = el.dataset.obstacle; forgetFields('obstacle-');
      } else {
        if (draft().pending.has('target-form')) throw new Error('편집 중인 관람대상을 먼저 미리보기에 적용하세요.');
        state.targetId = el.dataset.target; forgetFields('target-');
      }
      renderEditor({ capture: false }); return;
    }
    const action = el.dataset.action;
    if (action === 'dismiss') { state.message = null; renderMessage(); }
    else if (action === 'refresh') await boot();
    else if (action === 'refresh-event') await loadProject(state.project.id, state.event.id);
    else if (action === 'refresh-stats') await loadStats();
    else if (action === 'go-space') { captureForms(); state.step = 'space'; renderEditor({ capture: false }); }
    else if (action === 'use-browser-model') {
      const stored = localStorage.getItem('sightcheck:model:v1');
      if (!stored) throw new Error('이 브라우저에 저장된 도면 변환 결과가 없습니다. 도면 변환 도구에서 변환 결과를 적용한 뒤 다시 선택하세요.');
      let model; try { model = JSON.parse(stored); } catch { throw new Error('저장된 변환 결과를 읽지 못했습니다. 도면 변환 도구에서 결과를 다시 저장하세요.'); }
      const validated = Model.validateModel(model);
      captureForms(); state.projectModel = validated; renderEditor({ capture: false });
      $('#project-create').open = true;
      if (!value('project-create-name').trim()) $('#project-create-name').value = validated.name;
      toast('브라우저의 변환 결과를 선택했습니다. 프로젝트를 만들면 서버에 저장됩니다.');
    } else if (action === 'clear-project-model') { captureForms(); state.projectModel = null; renderEditor({ capture: false }); $('#project-create').open = true; }
    else if (action === 'new-project' || action === 'new-event' || action === 'clone-event') {
      captureForms(); state.step = 'space'; renderEditor({ capture: false });
      const detail = action === 'new-project' ? $('#project-create') : $('#event-create');
      detail.open = true; detail.scrollIntoView({ behavior: 'smooth', block: 'center' });
      if (action === 'clone-event') {
        $('#event-clone-source').value = state.event.id;
        $('#event-create-name').value = `${state.event.name} · 복제`;
      }
      $(action === 'new-project' ? '#project-create-name' : '#event-create-name').focus();
    } else if (action === 'scope-all' || action === 'scope-matched') {
      filteredSeats().filter(seat => action === 'scope-all' || seatReviewStatus(seat.label) === 'matched').forEach(seat => scope().selected.add(seat.label)); updateScope();
    } else if (action === 'scope-clear') { scope().selected.clear(); updateScope(); }
    else if (action === 'save-draft') await mutation(saveDraft, '변경사항을 저장했습니다. 변경된 배치를 현장에서 다시 대조하세요.');
    else if (action === 'preset-cinema' || action === 'preset-stadium') {
      if (draft().pending.has('target-form')) throw new Error('입력 중인 관람대상을 먼저 미리보기에 적용하세요.');
      captureForms(); const m = model3(draft().model), cinema = action === 'preset-cinema';
      const item = { id: uid(cinema ? 'screen' : 'board'), name: cinema ? '상영 스크린' : '경기장 전광판', position: cinema ? [0, 4, -.25] : [0, 12, -15], size: cinema ? [12, 6] : [20, 10], rotation: [0, 0, 0] };
      m.targets.push(item); m.venueType = cinema ? 'cinema' : 'stadium'; m.activeTargetId = item.id;
      applyModel(m); state.targetId = item.id; forgetFields('target-'); renderEditor({ capture: false });
      toast('관람대상 초깃값을 추가했습니다. 좌석 배치는 유지됩니다. 현장 치수로 수정하고 저장하세요.');
    }
    else if (action === 'reset-preview') preview?.resetDirection();
    else if (action === 'add-obstacle' || action === 'add-target') {
      if (draft().pending.has(action === 'add-obstacle' ? 'obstacle-form' : 'target-form')) throw new Error('입력 중인 항목을 먼저 미리보기에 적용하세요.');
      captureForms(); const m = model3(draft().model);
      if (action === 'add-obstacle') {
        const item = { id: uid('object'), name: '새 설치물', position: [0, .5, 2], size: [1, 1, .2], rotation: [0, 0, 0], layout: 'all' };
        m.obstacles.push(item); state.obstacleId = item.id; forgetFields('obstacle-');
      } else {
        const item = { id: uid('target'), name: '새 관람대상', position: [0, 2, -.25], size: [4, 2.4], rotation: [0, 0, 0] };
        m.targets.push(item); state.targetId = item.id; forgetFields('target-');
      }
      applyModel(m); renderEditor({ capture: false });
    } else if (action === 'delete-obstacle' || action === 'delete-target') {
      captureForms(); const m = model3(draft().model);
      if (action === 'delete-obstacle') { m.obstacles = m.obstacles.filter(o => o.id !== state.obstacleId); state.obstacleId = ''; draft().pending.delete('obstacle-form'); forgetFields('obstacle-'); }
      else {
        if (m.targets.length < 2) throw new Error('관람대상은 하나 이상 남겨야 합니다.');
        m.targets = m.targets.filter(t => t.id !== state.targetId);
        if (m.activeTargetId === state.targetId) m.activeTargetId = m.targets[0].id;
        state.targetId = m.targets[0].id; draft().pending.delete('target-form'); forgetFields('target-');
      }
      applyModel(m); renderEditor({ capture: false }); toast('미리보기에서 삭제했습니다. 변경사항을 저장하면 반영됩니다.');
    } else if (action === 'clear-photo') { ++photoSequence; state.photos.delete(state.event.id); if ($('#photo-file')) $('#photo-file').value = ''; $('#photo-preview').hidden = true; }
    else if (action?.startsWith('copy-')) {
      const input = document.getElementById({ 'copy-viewer': 'viewer-url', 'copy-embed': 'embed-code', 'copy-integration': 'integration-url' }[action]);
      try { await navigator.clipboard.writeText(input.value); toast('복사했습니다.'); }
      catch { input.focus(); input.select(); toast('자동 복사를 사용할 수 없습니다. 선택한 내용을 직접 복사하세요.'); }
    } else if (action === 'unpublish') await mutation(async () => {
      const result = await api(`/events/${pathId(state.event.id)}/unpublish`, { method: 'POST', body: { expectedRevision: state.event.revision } }); await acceptEvent(result.event);
    }, '게시를 중지했습니다.');
    else if (action === 'logout') await mutation(async () => {
      await api('/auth', { method: 'DELETE' });
      state.auth = { mode: 'token', authenticated: false }; state.projects = []; state.project = null; state.event = null;
      state.drafts.clear(); state.forms.clear(); state.photos.clear(); state.scopes.clear(); state.stats.clear(); state.hashes.clear(); state.loginToken = ''; state.projectModel = null; ++photoSequence; ++state.statsSequence;
    }, '로그아웃했습니다.');
  } catch (error) { notify(error.message, 'error', '입력은 유지됩니다'); }
}

function updateScope() {
  captureForms();
  if ($('#scope-grid')) $('#scope-grid').innerHTML = seatGrid('scope', true);
  if ($('#scope-count')) $('#scope-count').textContent = `선택한 좌석 ${scope().selected.size}개 · 구역·행 필터 밖의 선택도 포함됩니다.`;
  if (state.step === 'publish') renderEditor({ capture: false });
  applyBusy();
}
async function handleChange(event) {
  if (state.busy || state.loading) return;
  const el = event.target;
  try {
    if (el.id === 'project-select') { if (el.value) await loadProject(el.value); }
    else if (el.id === 'event-select') { if (el.value) await loadProject(state.project.id, el.value); }
    else if (el.id === 'preview-seat' || el.id === 'photo-seat') {
      captureForms(); state.selectedSeat = el.value;
      if (state.step === 'review') { forgetFields('photo-seat'); renderEditor({ capture: false }); } else renderPreview();
    } else if (el.id === 'preview-target') {
      if (draft().pending.has('target-form')) { el.value = state.targetId; throw new Error('편집 중인 관람대상을 먼저 미리보기에 적용하세요.'); }
      captureForms(); state.targetId = el.value;
      if (state.step === 'layout') { forgetFields('target-'); renderEditor({ capture: false }); }
      else if (state.step === 'review') renderEditor({ capture: false });
      else renderPreview();
    } else if (el.id === 'preview-overlay') { state.view.overlay = el.checked; renderPreview(); }
    else if (el.id === 'scope-section' || el.id === 'scope-row') {
      captureForms();
      if (el.id === 'scope-section') { scope().section = el.value; scope().row = ''; forgetFields('scope-row'); } else scope().row = el.value;
      renderEditor({ capture: false });
    } else if (el.id === 'photo-file') await choosePhoto(el.files[0]);
    else if (el.id === 'publication-mode') updateModeNote();
    else if (el.id === 'model-file') {
      if (el.files[0]?.size > 5_000_000) throw new Error('모델 파일은 5MB 이하로 선택하세요.');
    }
  } catch (error) { notify(error.message); }
}
function updateModeNote() {
  const el = $('#publication-mode-note');
  if (el) el.textContent = value('publication-mode') === 'demo' ? '현장 검수 전 시연으로 표시됩니다. 실제 현장 검수 완료나 시야 보증으로 안내하지 마세요.' : '선택 좌석마다 현재 모델과 연결된 사진 및 일치 검수가 필요합니다. 검수할 수 없는 좌석은 서버의 안내에 따라 범위에서 제외하거나 다시 대조하세요.';
}
function handleInput(event) {
  const form = event.target.closest('form');
  if (draft() && ['space-form', 'obstacle-form', 'target-form', 'floor-form'].includes(form?.id)) {
    draft().pending.add(form.id); renderDraftNotice(); applyBusy();
  }
}

mount();
await boot();
