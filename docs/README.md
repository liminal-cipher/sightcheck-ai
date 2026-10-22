# 시야체크 기획·기술·UX 자료

이 폴더는 공모전 제출 기획안과 구현을 위한 검토 자료를 보관합니다. **현재 제출안은 2026.10.01 개정본**입니다.

- [기획안 개정본](proposals/proposal-revised.md) / [Word](proposals/proposal-revised.docx) / [PDF](proposals/proposal-revised.pdf)
- [입력 자료와 변환 API](technical/input-conversion-api.md)
- [기술 선택과 실증 계획](technical/technology-validation-plan.md)
- [참고 URL 메모](research/reference-links.md)

아래는 초기 검토 자료입니다. 실제 구현 범위와 실행 방법은 [프로젝트 README](../README.md)를 기준으로 확인하세요.

개정 제출안: 출처와 AI 활용 표시를 포함해 A4 3쪽. 본문 12pt, 줄 간격은 12pt 기준 160%(고정 19.2pt)입니다. Word에서 PDF로 출력하고 세 페이지의 잘림·그림·본문을 확인했습니다. 권장 서식의 '160%'와 Word의 글꼴 메트릭 배수 간 차이를 피하기 위해 고정 간격을 사용했습니다.

| 자료 | 내용 |
| --- | --- |
| [제출용 기획안 Markdown](proposals/proposal-submission.md) | 개요, 차별성, 실현 가능성, BM, 기대 효과, 윤리·안전 |
| [제출용 기획안 PDF](proposals/proposal-submission.pdf) | 제출 양식에 맞춘 문서 |
| [제출용 기획안 Word](proposals/proposal-submission.docx) | 편집 가능한 원본 |
| [권장 3D 구성](technical/recommended-3d-architecture.md) | 공유 모델, 좌석별 카메라, 화질·정확도·운영비·모바일 설계 |
| [기술·UX·BM 검토 노트](technical/technology-ux-business-review.md) | 기술 비교와 타깃·사업모델 검토 |
| [예약 UX 개념도](images/booking-ux-concept.png) | 예약 전 좌석 비교 흐름 |
| [초기 아이디어 기획](research/initial-idea.md) | 아이디어 발전 과정의 초기 기록 |

기획안에는 PaddleOCR·SAM 2, AI 문의 답변, 서버 이미지 캐시 등 후속 기능도 포함됩니다. 현재 MVP의 AI 기능은 **Tesseract.js 기반 영문·숫자 OCR**입니다. 새 변환 API는 검토한 축척 도면 좌표와 실측 높이·구조물로 1~300석 모델을 구성합니다. 원근 사진 복원은 구현 범위가 아닙니다. 기획상의 기능을 모두 구현했다는 의미는 아닙니다.

공연장·예매 플랫폼과의 협업은 제안 단계입니다. 실제 제휴, 현장 시야 정확도, 매출·문의 감소 효과를 검증한 자료는 아닙니다.

디자인 작업 링크: [Figma](https://www.figma.com/design/Z9Q0pOhlydm2IBQnzg1sJw/26-%EC%96%B4%EB%8F%84-ai-%EA%B3%B5%EB%AA%A8%EC%A0%84?node-id=1-10).
