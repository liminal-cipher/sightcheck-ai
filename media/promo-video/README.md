# 시야체크 홍보 영상

원본 출처는 팀원 저장소 `PhrenO0/sightcheck-ai`의 `claude/busy-rubin-84tui7` 브랜치, 커밋 `91bde61`입니다. 기존 `video/`를 `media/promo-video/`로 옮기면서 실행·참조 경로만 수정했습니다. 원본 영상·이미지·글꼴은 그대로 보존했습니다.

54초짜리 1920×1080 60fps 제품 홍보 영상과 그 영상을 만드는 코드입니다. 영상 편집 프로그램은 쓰지 않았습니다. HTML 페이지에 장면을 그리고, 브라우저로 프레임을 한 장씩 캡처한 뒤 ffmpeg로 묶었습니다.

- 완성본: [`output/sightcheck-promo-1080p60.mp4`](output/sightcheck-promo-1080p60.mp4)
- 룩 카드(색·글꼴·모션 규칙): [LOOK.md](LOOK.md)
- 장면 구성과 자막: [STORYBOARD.md](STORYBOARD.md)

## 만드는 방식

```
src/timeline.json ─┬─ index.html + src/scenes.js ── Playwright가 t초마다 __seek(t) 호출 → PNG ─┐
                   │        └─ src/venue.js: 앱의 실제 3D 공연장(../../src/scene.js)을 불러와 카메라 연출  ├─ ffmpeg → MP4
                   └─ scripts/audio.py: 같은 타임라인으로 음악·효과음 합성 → soundtrack.wav ─────────┘
```

1. **실제 제품을 그대로 씁니다.** 3D 장면은 앱의 `VenueViewer`와 `analyzeSightline`을 직접 불러와 그립니다. 화면의 69%, 100%, 84%, 325개 같은 수치는 렌더 시점에 앱의 계산 함수가 낸 값입니다. 제품 공개 장면의 UI는 빌드한 앱을 Playwright로 연 캡처입니다.
2. **이징은 세 가지뿐입니다.** 등장 `cubic-bezier(0, 0, 0, 1)`(화면 밖·투명 상태에서 들어올 때만, 0.5초 안팎), 이동 `cubic-bezier(0.65, 0, 0.35, 1)`, 퇴장 `cubic-bezier(0.55, 0, 0.9, 0.45)`(끝나면 화면 밖이거나 완전히 투명). 규칙은 [LOOK.md](LOOK.md)에 있습니다.
3. **시간만으로 화면이 정해집니다.** 모든 장면은 `update(t)`에서 시간 t만 보고 상태를 계산합니다. 그래서 어느 프레임을 어떤 순서로 캡처해도 결과가 같고, 여러 작업자로 나눠 렌더할 수 있습니다.
4. **음악도 같은 타임라인을 읽습니다.** 컷, 클릭, 타워 상승, OCR 인식 시점에 효과음이 맞습니다. 음악은 코드로 합성했고 외부 음원은 없습니다.

## 실행

Node 20.19+ 또는 22.12+, Python 3, ffmpeg(libx264), Playwright용 Chromium이 필요합니다.

```sh
# 레포 루트에서 앱 의존성 설치·빌드 (UI 캡처에 필요)
npm install && npm run build

cd media/promo-video
npm install
pip install numpy scipy

npm run capture-ui       # 실제 앱 화면 캡처 → assets/ui/
npm run audio            # 사운드트랙 합성 → out/soundtrack.wav
npm run render:draft     # 30fps 초안 → out/draft.mp4 (약 8분)
npm run render           # 60fps 최종 → out/sightcheck-promo.mp4 (약 15분)
```

미리보기: `npm run preview` 후 `http://127.0.0.1:4300/media/promo-video/`를 엽니다. 하단 슬라이더로 시간을 옮길 수 있고, `?t=24.5`로 특정 시점을, `?play`로 재생을 엽니다.

QC용 정지 프레임: `node scripts/stills.mjs out/stills 3 14.5 27` 후 `python3 scripts/sheet.py`로 컨택트 시트를 만듭니다.

## 고치는 법

| 바꿀 것 | 위치 |
| --- | --- |
| 자막 문구 | `index.html`의 `data-text` 속성. `*강조*`는 연두색, `\n`은 줄바꿈 |
| 장면 길이·순서 | `src/timeline.json` (음악도 이 파일을 읽으므로 `npm run audio`를 다시 실행) |
| 장면 안 타이밍 | `src/scenes.js`의 각 장면 `update(t)` |
| 카메라 동선 | `src/scenes.js`의 `seatPose()`, `bezier3()` 호출부 |
| 색·글꼴 | `index.html`의 `:root` 토큰 (LOOK.md와 함께 수정) |
| 이징 | `src/engine.js`의 `ease.enter`·`ease.move`·`ease.exit`. 장면 코드는 `appear()`·`move()`·`vanish()`만 씁니다 |
| 음악 교체 | 원하는 음원을 `out/soundtrack.wav`로 저장한 뒤 `npm run render` |

## 렌더 환경 메모

- 클라우드 컨테이너처럼 GPU가 없는 환경에서는 WebGL이 SwiftShader(CPU)로 돌아서 프레임당 0.2~0.6초가 걸립니다. 작업자를 4개로 늘려도 빨라지지 않아 기본값을 2로 두었습니다.
- WebGL 캔버스를 2D 캔버스로 복사하면 프레임당 400ms가 추가됩니다. 그래서 WebGL 캔버스를 장면에 직접 붙이고, 비교 장면의 둥근 패널은 CSS `clip-path`로 잘랐습니다.
- 앱 UI 캡처 때 Chromium이 Google Fonts를 받지 못하는 환경을 대비해 Noto Sans KR을 로컬 파일로 주입합니다.

## 정직성 원칙

- 화면 속 공연장·공연·가격은 앱과 같은 가상 시제품입니다. 엔드카드에 이를 고지합니다.
- 수치는 "가리지 않은 표본" 비율이며 실제 시야를 보증하지 않습니다. 치수 보정 장면의 69 → 77 → 92 → 100%도 난간 높이별 실제 계산값입니다.
- 제휴사 로고, 사용자 수, 정확도 같은 검증하지 않은 주장은 넣지 않았습니다.

## 라이선스

- Pretendard (`assets/fonts/`): SIL Open Font License 1.1. 라이선스 전문은 `assets/fonts/Pretendard-LICENSE.txt`.
- Noto Sans KR: SIL OFL 1.1. npm 패키지(`@fontsource-variable/noto-sans-kr`)로 받아 UI 캡처에만 씁니다.
- three.js(MIT), Playwright(Apache-2.0)는 레포의 기존 의존성 또는 개발 의존성입니다.
- 음악·효과음은 `scripts/audio.py`로 합성했습니다.
