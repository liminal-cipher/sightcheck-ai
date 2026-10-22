---
format: 1920x1080
duration: 58s
message: 예매하기 전, 내 자리의 시야부터.
arc: Hook → product → mechanism → change → review → trust → end
mode: autonomous
music: original local electronic score
---

## Frame 1 — The difference (0–5)
- duration: 5s
- asset_candidates: assets/c3.png, assets/d3.png
Same floor, similar seat, different view. Two equally framed actual prototype views reveal the rail.

## Frame 2 — Choose your perspective (5–9)
- duration: 4s
- asset_candidates: assets/product.png
Actual product screen enters; selected C3 and its eye-level view are highlighted.

## Frame 3 — Compare (9–13)
- duration: 4s
- asset_candidates: assets/c3.png, assets/d3.png
Identical 60-degree FOV and 1.2m eye height; C3 and D3 side by side.

## Frame 4 — Calculate obstruction (13–18)
- duration: 5s
- asset_candidates: assets/c3-samples.png
Actual blocked-stage samples plus animated explanatory eye→rail→stage rays. Explicit synthetic-prototype calculation label.

## Frame 5 — Plan to candidate records (18–23)
- duration: 5s
- asset_candidates: assets/venue-plan.png
Four stages at top. Plan moves into structured VLM seat/stage candidates; Tesseract.js produces text/label candidates. Stored VLM output experiment clearly labeled.

## Frame 6 — Human measurement (23–27)
- duration: 4s
- asset_candidates: assets/venue-plan.png
C3 candidate connects to scale, floor/steps, rail/structure dimensions and performance layout, all human-supplied/reviewed. Metric values cannot be inferred automatically.

## Frame 7 — Existing spatial engine (27–34)
- duration: 7s
- asset_candidates: assets/vlm-overview.png, assets/c3.png
Coordinate conversion → metric spatial model → seat cameras → sightline/obstacle calculation; then reviewed viewer/widget route. Existing engine computes. Stored VLM + synthetic measurement input boundary stays visible.

## Frame 8 — Performance-specific change (34–42)
- duration: 8s
- asset_candidates: assets/a2-theatre.png, assets/a2-concert.png
Same A2, basic stage vs live setup with camera tower. Registered structure changes the calculated view. No accuracy metrics.

## Frame 9 — Review and publish (42–49)
- duration: 7s
- asset_candidates: assets/operator.png, assets/publish.png, assets/public.png
Actual operator workflow; representative-seat photo/condition comparison, review record, approved version, public viewer/iframe. Demo publication is explicitly labeled; no fabricated photo verification.

## Frame 10 — Trust model (49–54)
- duration: 5s
- asset_candidates: none; designed typography
AI Draft / Human Reviewed / 3D Estimated Sightline. Separate roles and unverified real-venue accuracy statement.

## Frame 11 — End (54–58)
- duration: 4s
- asset_candidates: assets/logo.svg
시야체크 AI. 예매하기 전, 내 자리의 시야부터. Hold clean closing frame.

## Hybrid visual revision
18–34s is now a continuous Three.js transformation, replacing Frames 5–7's card layouts: 도면에서 구조를 읽고 → 사람이 실제 공간을 확인하고 → 좌석의 시야로 바꿉니다. The plan's candidate points lift to reviewed floor levels, resolve into the actual venue and become the C3 camera. Hook/compare use real 3D cameras, the calculation shot pulls back through the venue, and performance change animates the camera tower. All other scene timing and claims remain unchanged.
