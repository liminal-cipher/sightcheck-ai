# VLM integration spike

실행일: 2026-10-01 (KST). 기준 HEAD: `61a4278446c5d5b2da5318191cc298d6609dd0f0`.
기계 판독 결과와 입력 SHA-256: [run-results.json](./run-results.json).

## 1. End-to-end 결과

**성공: 합성 fixture 기반으로 저장된 VLM JSON → 실측 fixture 결합 → 기존 HTTP 변환 API → 3D 모델·좌석 camera → C3 sightline 계산 및 기존 UI의 실제 WebGL 1인칭 렌더링까지 확인했다.**

VLM 호출은 사용자가 ChatGPT에서 별도로 수행한 단계다. 이번 실행에서는 저장된 결과를 읽었으며, 이미지 인식이나 VLM API 호출을 재실행하지 않았다. 두 PNG를 직접 열어 구조를 확인했고, PNG 헤더에서 이미지 크기를 읽었다. 실험 자료의 실제 위치는 요청문과 달리 `scripts/experiments/vlm-spike/`였다. 원본 파일은 이동하거나 수정하지 않았다.

실제 실행 경로:

2026-10-23 폴더 정리로 입력 자료를 `experiments/vlm-spike/fixtures/`로 옮겼다. 아래 실행 경로는 현재 위치이며, 과거 실행 기록과 결과 JSON의 원본 경로는 그대로 보존한다. 입력 파일 내용은 변경하지 않았다.

```text
experiments/vlm-spike/fixtures/base-vlm-output.json
  + public/engine-demo.json의 허용된 fixture 필드
  + public/engine-plan.png의 실제 이미지 크기
→ experiments/vlm-spike/adapter.mjs
→ convert-input.json
→ server/api.mjs: POST /api/v1/convert (HTTP 200)
→ src/conversion.js: convertPlan → src/model.js: validateModel/getSeats/eyePosition
→ conversion-result.json / model.json
→ src/scene.js: VenueViewer.positionCamera (Node에서 실제 메서드 실행)
→ POST /api/v1/sightline (HTTP 200)
→ calculateSeat → analyzeSightline (기존 Three.js Ray/Box3 교차 계산)
```

| 검증 | 실제 결과 |
| --- | --- |
| VLM 좌석이 변환 입력에 포함 | A1–D5, 중복 없는 20석; 모든 label·xPx·yPx를 VLM 원본과 대조 |
| 변환 모델 | schemaVersion 2, 20석의 유한한 x·floor·z 생성 |
| 좌석별 camera | 20개 position·target 생성 |
| 기존 viewer camera 코드 | 20석에 실제 `PerspectiveCamera`와 `positionCamera` 실행; API position·시선 방향·FOV 일치 |
| C3 계산 | theatre, 눈높이 1.2m, 325개 표본 |
| C3 위치 | 바닥 기준 `[x,y,z] = [0,2.4,8.8]`m |
| C3 camera | position `[0,3.5999999999999996,8.8]`, target `[0,1.88,-0.25]`, vertical FOV 60° |
| C3 sightline | visible 69%, lowerVisible 20%, 난간에 가린 표본 100개; distance 문자열 `9.1`, angle 0° |
| 모델 검수 상태 | `needs_site_review` 유지 |
| 기존 Three.js UI의 실제 렌더링 | 사용자가 viewer.html에서 생성 모델을 적용하고 C3 1인칭 WebGL 장면·전면 난간 표시를 확인; 눈높이 1.20m, visible 69%, lowerVisible 20%, 무대 전면 거리 9.1m |

가시 비율은 이 fixture의 무대 전면 표본에 대한 geometry 계산이며 실제 공연장 관람 품질의 정확도가 아니다. camera의 부동소수점 원시 값은 결과 JSON 그대로 기록했다. `floor`는 fixture에서 복사한 바닥 높이이고 엔진이 높이를 추론한 것이 아니다.

`viewer.html`은 기존 `src/main.js` 전체를 불러오고 생성된 `model.json`을 기존 `#import-model` handler에 전달하는 최소 실험 페이지다. 자체 renderer나 camera/sightline 구현은 없다. Vite 컴파일 통과 후 사용자가 브라우저에서 모델 적용·C3 선택·WebGL 렌더링을 직접 검증했다. 생성 모델은 원래 제품 UI의 **모델 파일 관리 → JSON 불러오기**로도 넣을 수 있다.

브라우저 검증 근거는 사용자 실행 보고와 [C3 검증 스크린샷](./vlm-spike-c3-browser-verified.png)이다. 스크린샷을 직접 열어 C3 선택, 눈높이 1.20m, 69%/하단 20%, 거리 9.1m, 전면 난간이 표시된 3D 장면과 `3D 준비됨` 상태를 확인했다. 에이전트가 브라우저를 재실행한 것은 아니다. `run-results.json`의 `webglRenderVerified: false`는 앞선 Node harness 실행 범위를 기록한 값이므로 그대로 유지하며, 이후의 사용자 브라우저 검증은 이 보고서와 스크린샷으로 구분한다. 실제 공연장 정확도나 현장 검수 완료를 의미하지 않는다.

### 입력 출처를 검증한 방법

이 샘플에서는 VLM의 20석 pixel 좌표와 무대 전면 기준점이 fixture의 기존 좌표와 모두 같다. 따라서 결과 좌표가 fixture 변환과 일치한다는 사실만으로 VLM 경로를 검증하지 않았다.

- fixture 좌석 순서를 뒤집고 모든 좌석 pixel·행 및 무대 pixel 기준점을 잘못된 값으로 바꿔도 결과가 같음을 테스트했다. adapter는 fixture pixel/row를 읽지 않고 실측 데이터를 좌석명으로 결합한다.
- VLM C3 x를 60px 이동시키면 기존 엔진의 C3 x와 camera x가 1m 이동함을 확인했다.
- VLM 무대 영역의 전면 y를 60px 이동시키면 C3 z가 1m 감소함을 확인했다.
- VLM에 가짜 floorM·section·stage depth·obstacle 값을 넣어도 결과에 반영되지 않음을 확인했다.
- 필요한 human floorM 누락, 미등록 좌석, railing의 별도 schema/이미지 크기는 실패하도록 확인했다.

이 변경값들은 입력 의존성 검증용 테스트이며 원본 VLM 결과나 저장된 변환 결과를 수정한 것이 아니다.

## 2. Data provenance

| 구분 | 데이터 | 출처 / 처리 |
| --- | --- | --- |
| A. VLM 이미지 추출 | seat_number A1–D5, center_px, row A–D | base VLM JSON에서 읽음; section null과 certainty는 metric/검수 사실로 사용하지 않음 |
| A. VLM 이미지 추출 | stage.region_px `[242,20]–[758,110]` | 이 영역의 pixel 정보를 실제 calibration 입력에 사용; center_px `[500,65]`는 API가 요구하지 않아 사용하지 않음 |
| B. Human-reviewed fixture | 좌석 floorM, section | engine-demo.json에서 좌석명으로 결합. A/B/C/D 높이 각각 0/0.24/2.4/3.05m; A·B 1층, C·D 2층 |
| B. Human-reviewed fixture | stageWidthM 8.6, depthM 3.6, heightM 0.6, targetHeightM 2.4, audienceSide 1 | 모두 fixture 제공. 이미지에 폭/축척 문자가 있더라도 이 실험의 metric 출처는 fixture |
| B. Human-reviewed fixture | rail: position `[0,2.9,8.0575]`, size `[8.75,1,0.1]`, layout `all` | VLM이 추출한 장애물이 아님 |
| B. Human-reviewed fixture | tower: position `[-1.95,1.9,1.5]`, size `[1.05,2.6,0.65]`, layout `concert` | 모델에 포함되지만 이번 C3 theatre 계산에서는 제외 |
| B. Human-reviewed fixture | name, inputType, rightsConfirmed, positionsReviewed, measurementsReviewed | 이 합성 샘플을 위한 기존 fixture의 선언을 복사. 새 현장 검수나 일반 VLM 자동 승인으로 해석하지 않음 |
| C. 기존 엔진 | metre/pixel `0.016666666666666666`, 좌석 x/z, schema 2 model, camera, sightline | convertPlan, model.js 및 기존 viewer 메서드 실행 결과 |
| C. 기존 엔진 상수/기본값 | 눈높이 1.2m, FOV 60°, 무대 전면 z=-0.25, 표본 25×13, target의 +0.08m, price 0, 공통 외관 | 실측 또는 AI 추출값이 아님. 기본 모델에서 유지되는 스타일·보조 필드도 재구성 증거가 아님 |
| D. 새 adapter/glue | 필드 이름 변경, row A–D → 0–3, 좌석명 기반 fixture join, 허용 필드만 복사 | metric 계산 및 sightline 알고리즘을 새로 구현하지 않음 |
| D. 새 adapter/glue | axis-aligned stage bbox의 아래쪽 두 모서리 → stageLeft `[242,110]`, stageRight `[758,110]` | 이 샘플의 객석 방향(+1)과 도면을 확인해 정한 규칙; 회전 도면·일반 polygon 지원이 아님 |
| D. 새 harness | 실제 PNG 헤더의 1000×930, HTTP 호출, 검증, SHA-256 및 JSON 저장 | 파일 메타데이터와 실행 bookkeeping; VLM 추출값이 아님 |

`engine-demo.json`은 요청에 따라 human-reviewed measurement fixture로 사용했다. 도면에는 **SYNTHETIC PLAN / NOT A REAL VENUE**가 명시되어 있어 실제 현장에서 측량했다는 증거로 취급하지 않는다. base JSON의 `obstacles: []`는 장애물 부재의 증거가 아니다. 최종 모델의 두 장애물은 전적으로 fixture가 제공했다.

## 3. 이번 샘플에서 줄일 수 있었던 수작업

- 20석의 좌석명·2D 중심 좌표·행을 변환 입력에 다시 타이핑하는 작업.
- 무대 영역 pixel 좌표를 다시 입력하는 작업. 이 샘플에 한정한 규칙으로 전면 양 끝점을 만들었다.

픽셀 위치 검토, 실측 보완, 좌석명 matching 확인은 여전히 필요하다. 시간 절약량, 인식 정확도 또는 기존 OCR 대비 우위는 측정하지 않았다. VLM 생성 당시 prompt/model/run 조건도 이 spike에서 재현하지 않았다.

## 4. 여전히 사람이 제공하거나 검토해야 하는 정보

실제 무대 폭·깊이·높이, 무대 표본 영역 높이, 좌석 바닥 높이와 단차, 구역 metadata, 객석 방향, obstacle의 중심·폭·높이·깊이와 공연별 배치, 자료 사용 권한, 좌석 중심/누락/중복과 무대 전면 선택의 적절성, 정투영·균일 축척 여부가 필요하다. 실제 공연장으로 적용하려면 현장 좌석 사진·실측과 대조해야 한다. 기존 엔진은 원근 사진과 축척 없는 예매 도면을 지원하지 않는다.

## 5. 장애물 샘플 결과 — 실험 B

`railing-plan.png`와 `railing-vlm-output.json`을 직접 확인했다. 이미지 크기는 **1254×1254**로 base의 **1000×930**과 다르다. 이 JSON은 `center_pixel`/`area_pixel`이라는 별도 schema를 쓴다.

- A1–D5 20석을 seat_number, center_pixel, row로 구조화했다. 좌석 section은 모두 null이다.
- `type: balcony_rail`, `label: BALCONY RAIL`인 obstacle 후보 1개를 기록했다.
- 2D 영역은 x=355–899, y=740–775px이다. 이미지에서 B행과 C행 사이 난간 도형과 그 아래 라벨을 직접 확인했다. 영역은 난간 도형에 해당하며 라벨 글자 전체를 포함하는 영역은 아니다.
- obstacle 필드는 type, label, area_pixel, certainty, notes뿐이다. 실제 높이·깊이·3D position/size 값은 생성하지 않았다. notes도 실제 높이·깊이·시야 차단 정도를 이미지에서 확인할 수 없다고 명시한다.
- 무대에도 pixel 영역과 중심만 있고 metric 치수는 없다. certainty의 “확실”은 VLM의 자기 보고이며 정확도 인증이 아니다.
- 이 샘플의 좌표는 fixture와 결합하지 않았고 convert에도 전달하지 않았다. 이미지에 인쇄된 축척 문자열도 base와 같은 metric 좌표계라는 근거로 사용하지 않았다.

관찰 범위는 **명시적으로 표현된 장애물 후보를 2D 도면에서 구조화할 가능성**이다. 라벨 없는 장애물, 실제 공연장 도면, 복잡한 난간 구조에 대한 탐지 정확도를 보여주지 않는다.

## 6. 안전하게 주장할 수 있는 것

이 합성 도면의 저장된 멀티모달 출력에서 좌석·무대 pixel 초안을 가져와 사람이 제공한 measurement fixture와 결합하면, 기존 SightCheck 변환·좌석 camera·geometry 기반 sightline 경로까지 연결할 수 있었다. 사용자가 생성 모델을 기존 UI에 적용해 C3 WebGL 1인칭 장면까지 확인했다. 기존 제품 소스와 OCR을 변경하지 않았다. AI 역할은 입력 초안 구조화, 사람 역할은 실측값과 검수 보완, 기존 엔진 역할은 metric 모델과 camera·sightline 계산이다.

## 7. 아직 주장하면 안 되는 것

- 실제 공연장 정확도, 임의 도면/회전 도면/원근 이미지에 대한 일반화.
- 자동 metric 3D reconstruction, 실측 없는 obstacle 높이·깊이·3D 위치 복원.
- AI가 좌석 시야를 생성하거나 관람 품질·시야를 판정했다는 주장.
- VLM 장애물 자동 인식의 정밀도·재현율, 누락 없는 탐지, OCR 대비 우위.
- JSON의 certainty 또는 fixture review flag가 실제 현장 검수를 증명한다는 주장.
- C3의 합성 fixture 브라우저 검증을 실제 공연장 시야 정확도 또는 모든 좌석·브라우저의 검증으로 확대하는 주장.

## 8. 다음으로 제안했던 가장 작은 실험 1개 — 완료

**생성 모델을 기존 UI에 적용하고 C3 1인칭 화면을 확인하는 실험을 사용자가 완료했다.** viewer 페이지에서 모델 적용 후 C3·눈높이 1.20m의 실제 WebGL 장면, 69%/하단 20%, 거리 9.1m와 전면 난간을 확인했고 위 스크린샷을 남겼다. 이로써 앞서 미검증이었던 renderer 단계의 합성 fixture 검증을 보완했다.

## 9. 변경 파일 목록

### 기존 파일

추적 중인 기존 제품 파일 변경 없음. 기존 `src/`, `server/`, `tests/`, package.json과 OCR 코드는 수정하지 않았다. 빌드가 재작성한 `public/licenses/` 5개 파일은 원래 상태로 복원했다. 시작 시 이미 untracked였던 사용자 제공 `scripts/experiments/vlm-spike/`의 `base-vlm-output.json`, `railing-plan.png`, `railing-vlm-output.json`은 내용 변경 없이 실험 재현 입력으로 포함한다. push는 하지 않는다.

로컬 작업 추적용 `CURRENT_TASK.md`를 생성하고 `.git/info/exclude`에 `/CURRENT_TASK.md`를 추가했다. 이는 제품 소스 변경이나 제출 산출물이 아니다. 설치/빌드 결과 `node_modules/`, `dist/`, `public/ocr/`는 기존 ignore 대상이다.

### 새 실험 파일 (`experiments/vlm-spike/`)

| 파일 | 역할 |
| --- | --- |
| adapter.mjs | base 샘플 전용 allowlist adapter |
| adapter.test.mjs | 입력 출처·변경 영향·측정값 누락·railing 분리 테스트 4개 |
| run-spike.mjs | 기존 HTTP API 및 viewer camera 메서드 실행, 결과 저장 |
| convert-input.json | VLM pixel + human fixture를 합친 실제 API 입력 |
| conversion-result.json | 기존 convert API 응답 전체 |
| model.json | 기존 UI에서 import할 schema 2 모델 |
| run-results.json | 실행 시각·입력 hash·20석/20 camera 검증·C3 결과·B 관찰 |
| viewer.html | 기존 제품 UI와 import handler 재사용; 사용자 C3 브라우저 검증 완료 |
| vlm-spike-c3-browser-verified.png | 사용자가 제공한 C3 브라우저 검증 증거 |
| experiment-report.md | 본 보고서 |

## 검증 및 재현

브라우저 검증 기록 반영 후 커밋 준비 단계에서 adapter 테스트 4개, 기존 `npm test` 10개, `npm run build`를 다시 실행해 모두 통과했다. 빌드에는 기존 500kB chunk 크기 경고만 남았다.

| 실행 | 결과 |
| --- | --- |
| `node --test experiments/vlm-spike/adapter.test.mjs` | 4/4 통과 |
| `node experiments/vlm-spike/run-spike.mjs` | 성공, convert/sightline 모두 HTTP 200; 결과 JSON 저장 |
| `npm test` | 기존 테스트 10/10 통과 |
| `npm run build` | OCR 자산 준비 + client/API 빌드 성공; minified chunk 500kB 초과 경고 |
| viewer.html을 input으로 지정한 별도 Vite build | 컴파일 성공; 같은 chunk 크기 경고. 실제 화면 검증은 아님 |
| 사용자 브라우저 검증 | 생성 모델 적용·C3 선택·WebGL 1인칭 장면 및 난간 확인; 1.20m, 69%/하단 20%, 거리 9.1m |

처음에는 설치된 `three`가 없어 실행이 실패했다. `npm ci`도 저장소에 lockfile이 없어 실패했으며, `npm install --package-lock=false --no-audit --no-fund`로 기존 manifest 의존성을 설치한 후 위 검증을 통과했다. 새 의존성·manifest·lockfile 변경은 없다. 테스트는 Node v24.20.0에서 실행했다. 기존 OCR unit test와 OCR 자산 빌드는 통과했지만 OCR 브라우저 인식을 별도로 재실행한 것은 아니다.

저장소 루트에서 재현:

```powershell
node --test experiments/vlm-spike/adapter.test.mjs
node experiments/vlm-spike/run-spike.mjs
npm test
npm run build
```

완료된 UI 확인을 재현하려면 개발 서버로 실행한다. 실험 HTML/JSON은 production build의 기본 배포 엔트리에 추가하지 않았다.

```powershell
npm run dev -- --port 4174
# http://127.0.0.1:4174/experiments/vlm-spike/viewer.html
```

페이지의 “VLM spike 모델을 기존 화면에 적용”을 클릭한다. import는 기존 앱과 동일하게 이 origin의 localStorage 모델을 저장하므로 기존 작업용 origin과 분리된 포트를 권장한다. 적용 후 화면 표시와 렌더링을 직접 확인해야 하며, 모델 적용 버튼의 성공 메시지만으로 WebGL 성공을 판단하지 않는다.
