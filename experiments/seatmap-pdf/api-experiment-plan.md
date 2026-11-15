# Claude API 좌석 판독 실험 계획

결과를 보기 전에 고정하는 계획이다. 이 파일과 프롬프트를 커밋한 뒤에만 API 요청을 보낸다. 실행 중 계획과 다르게 진행한 부분은 [`experiment-report.md`](experiment-report.md)에 이유와 함께 적는다.

## 질문

1. 좌석 칸 판독에 어떤 모델과 effort를 쓸까?
2. 서브에이전트로 얻은 Opus 결과(블라인드 70개 모두 정답)가 API 호출에서도 재현될까?
3. 같은 조건으로 다시 돌리거나 프롬프트 표현을 바꾸면 답이 흔들릴까?

## 모델과 effort를 고른 이유

아래는 2026-11-16에 Anthropic 공식 문서와 출시 페이지에서 확인한 내용이다(출처는 이 절 끝). 벤치마크 점수는 Anthropic이 발표한 값이며 따로 검증하지 않았다.

| 항목 | Opus 5.5 | Sonnet 5.5 | Haiku 5.5 |
| --- | --- | --- | --- |
| API ID | `claude-opus-5-5` | `claude-sonnet-5-5` | `claude-haiku-5-5` |
| 출시일 | 2026-09-22 | 2026-09-28 | 2026-10-07 |
| 공식 설명 | 오래 걸리는 에이전트 코딩과 지식 작업용 | 속도와 지능의 균형이 가장 좋음 | 분류·추출·라우팅 같은 대량·저지연 작업용 |
| 가격 (100만 토큰당 입력/출력) | $4 / $20 | $2 / $10 | $0.10 / $0.50부터 (프롬프트 10만 토큰 이하) |
| Batch API | 50% 할인 | 50% 할인 | 50% 할인 |
| API 기본 effort | `medium` | `high` | `medium` |
| thinking | adaptive, 끌 수 없음 | adaptive | adaptive |
| Chartography 시각 추론 (도구 없음) | 64.4% | 61.6% | 46.4% |

### 이 실험과 관련된 공식 사양

- **해상도**: 세 모델 모두 이미지 입력을 지원한다. 셋 다 Claude 4.7 이후 모델이라 고해상도 등급이 적용된다. 긴 변은 2,576 px까지, 이미지 하나는 시각 토큰 4,784개까지다.
- **토큰 계산**: 이미지는 28×28 px 조각 하나가 시각 토큰 하나다. 상한을 넘으면 비율을 유지한 채 줄인다.
- **도면 전체 이미지**: 1754×2550 px는 63×92 = 5,796조각이라 상한을 넘는다. API가 약 4,730토큰 크기로 줄여서 읽으므로, 작은 글자가 원본보다 덜 선명할 수 있다.
- **확대 조각**: 236×236 px, 81토큰이라 줄이지 않는다. 문서는 200 px보다 작은 이미지에서 정확도가 떨어질 수 있다고 하는데, 확대 조각은 그보다 크다.
- **이미지 순서**: 문서는 이미지를 글보다 앞에 두기를 권한다. 이 실험은 서브에이전트 실행과 같은 순서(지시문 → 도면 전체 → 확대 조각)를 유지한다. 순서를 바꾸면 서브에이전트 결과와 비교할 때 차이의 원인이 하나 더 늘어나기 때문이다.
- **effort의 성격**: effort는 thinking을 포함한 모든 출력 토큰에 영향을 주는 신호이고, 정확한 토큰 상한은 아니다. 문서는 이전 모델의 설정을 그대로 쓰지 말고 자기 작업으로 effort를 비교해 보라고 권한다.

### 모델 선택

- **Opus 5.5**:
  - 공식 문서가 어떤 모델을 쓸지 모를 때 먼저 쓰라고 권하는 모델이다.
  - 서브에이전트 실행에서 블라인드 70개를 모두 맞혔으므로 기준선으로 쓴다.
- **Sonnet 5.5**:
  - 가격이 Opus의 절반이다.
  - 발표된 시각 추론 점수는 Opus보다 2.8%p 낮다.
  - 서브에이전트 실행(effort `medium`)에서 블라인드 30개를 모두 맞혔다.
- **Haiku 5.5**:
  - 이 작업은 공식 설명의 "추출" 유형에 가깝다.
  - 입력 가격이 Opus의 1/40이라, 750칸 전체나 다른 공연장으로 넓힐 때 비용 차이가 가장 크다.
  - 발표된 시각 추론 점수는 셋 중 가장 낮다.
  - 서브에이전트 실행의 블라인드 오답 4개는 이웃 항목과 답이 뒤바뀐 경우였다. 항목마다 따로 호출해서 실제로 읽는 능력을 다시 본다.

넣지 않은 모델:
- **Fable 5.2**: 가격이 Opus의 두 배다. 공식 문서는 Opus 5.5를 높은 effort로 써도 부족할 때 쓰라고 한다. Opus가 이미 70개를 모두 맞혔으므로 이 표본으로는 더 나아지는지 잴 수 없다.
- **이전 세대**:
  - Sonnet 5는 Sonnet 5.5와 가격이 같지만 발표된 시각 추론 점수가 15.6%다.
  - Haiku 4.5는 Claude 4.7 이전 모델이라 이미지를 긴 변 1,568 px로 줄여 읽는다.

### effort 선택

- `low`, `medium`, `high`로 나누면 세 모델의 API 기본값(Opus·Haiku `medium`, Sonnet `high`)과 서브에이전트 실행 조건(Opus `high`)이 모두 들어간다.
- `xhigh`와 `max`는 넣지 않는다.
  - 문서는 이 단계를 오래 걸리는 작업에 쓰거나, 자기 평가에서 이득이 확인될 때만 쓰라고 한다.
  - 이 실험은 칸 하나를 읽는 짧은 작업이다.
  - Opus `high`가 이미 70개를 다 맞혀서, 더 높은 단계의 이득을 이 표본으로 확인할 수 없다.

### 출처

- [Models overview](https://platform.claude.com/docs/en/models/overview)
- [Claude Opus 5.5](https://platform.claude.com/docs/en/models/opus-5-5/overview)
- [Introducing Claude Sonnet 5.5](https://www.anthropic.com/claude-sonnet-5-5)
- [Introducing Claude Haiku 5.5](https://www.anthropic.com/claude-haiku-5-5)
- [Vision](https://platform.claude.com/docs/en/build-with-claude/vision)
- [Effort](https://platform.claude.com/docs/en/build-with-claude/effort)

## 표본

- 블라인드 30개: 시드 20261114, JPEG 표본 209개에서 무작위로 뽑았다.
- 블라인드 40개: 시드 20261115, 아직 사람이 보지 않은 143개에서 OCR 표집 범주별 개수를 정해 뽑았다.
- 둘 다 사용자가 예측을 보지 않고 표기했다. 합쳐서 70개를 모든 실행에 쓴다.
- 확인 큐 36개는 Opus 판독을 보면서 정한 정답이라 이 실험에 쓰지 않는다.
- 이 70개를 보고 프롬프트를 고치지 않는다. 사람이 보지 않은 나머지 103개는 프롬프트를 고칠 때 새 블라인드 표본으로 쓰려고 남겨 둔다.

## 고정 조건

| 항목 | 값 |
| --- | --- |
| 실행 도구 | `claude_preread.py` (항목 하나당 요청 하나, Message Batch) |
| 기본 프롬프트 | [`prompts/seat-reader-api.md`](prompts/seat-reader-api.md) |
| 답 형식 | JSON 스키마 (`output_config.format`), 필드는 서브에이전트 실행과 같음 |
| thinking | adaptive |
| max_tokens | 16000 (thinking 포함) |
| SDK | `anthropic` Python 2.8.0 |

프롬프트 해시는 실행 폴더마다 `run.json`에 남는다.

## 1단계: 모델 × effort

9개 실행. Opus, Sonnet, Haiku 각각 effort `low`, `medium`, `high`.

```powershell
$ids = '--ids', 'experiments/seatmap-pdf/output/phase-abc/blind-review-samples.json', '--ids', 'experiments/seatmap-pdf/output/phase-abc/blind2-review-samples.json'
foreach ($m in 'opus', 'sonnet', 'haiku') { foreach ($e in 'low', 'medium', 'high') {
  & $seatmapPython experiments/seatmap-pdf/claude_preread.py submit --name "api-$m-$e" --model $m --effort $e --max-cost 5 @ids
} }
```

## 2단계: 안정성

1단계에서 아래 규칙으로 고른 조건 하나만으로 실행한다.

- 같은 조건으로 두 번 더 실행: `--name <조건>-r2`, `<조건>-r3`
- 바꿔 쓴 프롬프트로 한 번씩 실행:
  - [`prompts/seat-reader-api-paraphrase-1.md`](prompts/seat-reader-api-paraphrase-1.md)
  - [`prompts/seat-reader-api-paraphrase-2.md`](prompts/seat-reader-api-paraphrase-2.md)

## 채점과 지표

`score_readers.py`로 블라인드 30개와 40개를 따로 채점한다.

- 좌석이면 구역·행·번호가 모두 맞아야 정답이다. 좌석이 아니면 좌석 여부만 본다.
- 답 없음, 잘린 응답, 오류는 오답으로 센다.

주 지표는 70개 중 오답 수다.

보조 지표:
- 측정 비용: `collect`가 출력하는 실제 토큰 수에 정가를 곱한 값
- 확신 high인데 틀린 답의 수
- 2단계 반복 실행: 세 번 모두 같은 답을 낸 항목의 비율
- 2단계 바꿔 쓴 프롬프트: 각각의 오답 수

참고 비교: API Opus `high`와 서브에이전트 Opus(effort `high`)의 차이. Claude Code의 시스템 지시와 여러 항목을 묶어 처리한 방식이 결과에 영향을 줬는지 본다.

## 결과를 보기 전에 정한 선택 규칙

1. 70개에서 오답이 0개인 조건 중 측정 비용이 가장 낮은 조건을 고른다.
2. 오답 0개인 조건이 없으면 오답이 가장 적은 조건을 고르고, 같으면 더 싼 조건을 고른다.
3. 고른 조건에서 확신 high인데 틀린 답이 하나라도 있으면, "확신만으로 사람 검토 대상을 거를 수 없다"고 기록한다.
4. 2단계에서 다음 중 하나라도 해당하면 결과가 프롬프트나 실행에 따라 흔들린다고 기록하고, 전체 750칸 판독에 쓰기 전에 사용자와 다시 정한다.
   - 반복 실행에서 답이 달라진 항목이 있다.
   - 바꿔 쓴 프롬프트의 오답이 기본 프롬프트보다 2개 이상 많다.

해석 한계:
- 70개 모두 맞아도 정확도의 단측 95% 하한은 약 96%다.
- 오답 한두 개의 차이는 우연과 구분할 수 없다.
- 두 블라인드 세트 모두 어려운 사례 위주의 목적 표집에서 뽑았으므로 도면 전체 정확도가 아니다.

## 예산

| 단계 | 실행 | 상한 추정 (Batch 가격) |
| --- | ---: | ---: |
| 1단계 | 9 | 약 $16 |
| 2단계 | 4 | 최대 약 $14 (Opus를 고른 경우) |

추정 방식:
- 이미지 토큰은 위의 공식 계산(28×28 조각, 고해상도 상한)으로 셌다.
- 항목당 출력(thinking 포함)은 4,000토큰으로 넉넉하게 가정했다. 실제로는 이보다 적게 들 것이다. 각 실행에 `--max-cost 5`를 건다. 측정 비용 합계가 $40을 넘을 것 같으면 멈추고 사용자와 상의한다.

## 이 계획에 넣지 않은 것

- 750칸 전체 판독: 이 실험에서 조건을 고른 뒤 따로 계획한다.
- 프롬프트 수정(예: 휠체어석 문구): 남겨 둔 103개에서 새 블라인드 표본을 만든 뒤에 시험한다.
