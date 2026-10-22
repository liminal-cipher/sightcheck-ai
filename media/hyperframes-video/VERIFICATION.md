# Verification and source boundaries

## Grounding
- Proposal: repository-root 시야체크_AI_기획안_완성본.pdf, text read in full. Four stages and role separation used as the narrative backbone.
- Current README, src/scene.js, src/model.js, src/conversion.js, src/operator.js, src/public-viewer.js and server API/repository inspected.
- experiments/vlm-spike/experiment-report.md: stored VLM output plus synthetic human-reviewed measurements; no live VLM inference, automatic metric reconstruction or real venue accuracy claim.
- Historical media/promo-video/LOOK.md and media/promo-video/STORYBOARD.md supplied color/font/motion reference only. The existing composition and outputs were not edited or migrated.

## Visual provenance
- C3/D3/A2 and blocked sample images: fresh captures using current VenueViewer and its original synthetic DEFAULT_MODEL. All seat views use 60-degree FOV, 1.20m eye height and 1600×900 capture dimensions.
- vlm-overview.png: current VenueViewer rendering experiments/vlm-spike/model.json, with a video-only overview camera at [13,18,19], target [0,1.8,5.5], FOV 44 degrees. Product source unchanged.
- Product, review, publish and public viewer screenshots: current local UI. Operator/public data were generated using scripts/create-demo.mjs into this project's capture/demo-data directory. Publication mode is demo, not reviewed. No real reference photos or approved real-venue results were fabricated.
- Venue plan and logo copied from public/engine-plan.png and public/favicon.svg.
- C3 record (500,653) px; converted x=0, z=8.8m; reviewed synthetic floor=2.4m. Source: experiments/vlm-spike/convert-input.json and model.json. Those are example values, not accuracy metrics.
- Ray cross-section is an explicitly labeled explanatory diagram, not a measured venue section.
- score.wav is an original deterministic synthesized instrumental, no external music samples or voiceover.
- Font: existing Pretendard Variable copied together with its OFL license.

## Checks
- HyperFrames 0.8.137 lint: 0 errors; 14 maintainability warnings (reused images and monolithic scene nesting/dense timeline).
- HyperFrames check across 11 scene times: passed; browser ran, no runtime errors, no contrast errors, no persistent layout errors. Two informational crop-overflow findings are intentional slight image zooms inside clipped frames.
- Representative hook, product, comparison, sightline, all technical stages, performance change, publishing, trust and end frames visually inspected.
- Revised ray diagram stops blocked paths at the rail. Candidate C3 moves from plan to structured record. Preview responds HTTP 200.

## Human review before submission
Watch the full encoded MP4 once for Korean reading pace and instrumental sound level. Confirm the competition's AI-use disclosure requirements. The video deliberately states synthetic prototype, stored-output VLM experiment, demo publication, and unverified real-venue accuracy; do not remove those boundaries when submitting.

## Commands (from this directory)
```powershell
npx --yes hyperframes@0.8.137 preview --background
npx --yes hyperframes@0.8.137 render --fps 30 --quality looks --workers 2 --output output/sightcheck-ai-draft.mp4
npx --yes hyperframes@0.8.137 render --fps 30 --quality delivery --workers 2 --output output/sightcheck-ai-final.mp4
```

Rebuild source composition and score: `python scripts/build.py`.
Fresh UI capture requires repository Vite on port 4178 with SIGHTCHECK_DATA_DIR set to this project's capture/demo-data, then run capture scripts from the repository root. Existing video/node_modules/playwright-core is reused read-only; it is needed only to recapture, not to preview/render frozen assets.

## Encoded output verified
58.000 seconds; 1920×1080 H.264; 30/1 fps; 1740 frames; AAC stereo at 48kHz; 11,887,665 bytes. Render path: hardware GPU screenshot capture, HyperFrames deterministic seek, 2 workers. Runtime 68 seconds. Final encoded frame at 57.5s inspected; end card held correctly. Audio non-silent, mean -33.2dB / peak -16.2dB (restrained bed; human loudness review recommended).
SHA-256: 4C91E57A201AE7682C373B559F9713E2A44074CABE325D33C025C5534BEC91E4.

## Hybrid revision
- Preserved the original 58s timing, product UI, review/publish, trust and closing shots.
- Hook and C3/D3 comparison now render real Three.js seat cameras. 13–18s pulls the camera out from C3 to reveal calculated obstruction rays and stage samples.
- 18–34s replaces architecture cards with one continuous plan/candidate → reviewed measurement → actual venue → C3 seat-camera animation. Three concise phrases and secondary labels carry the explanation.
- 34–42s uses an actual A2 camera and animated performance-specific tower introduction.
- Actual rendering reuses media/promo-video/src/venue.js and current product engine read-only, bundled into assets/hybrid-3d.js. The VLM synthetic model supplies the technical scene. Candidate stage region uses pixel extent; physical stage depth comes from the reviewed model. Tower rise and venue growth are explanatory transitions, not construction/reconstruction claims.
- Final technical frames at 20,25,27.3,29.5,32 seconds and review/publish at 46 seconds inspected before rendering. Corrected transparent draw order so AI candidate points remain visible above the plan image.
- Original output/sightcheck-ai-draft.mp4 preserved. New deliverable: output/sightcheck-ai-hybrid-draft-v2.mp4.
- Rebuild hybrid HTML: python scripts/revise-hybrid.py
- Rebuild local Three.js bundle: node ../../node_modules/vite/bin/vite.js build --config scripts/vite-hybrid.config.mjs

## v3: technical labels only
Main narrative: 도면에서 구조를 읽고 / 실제 공간을 확인하고 / 좌석의 시야로 바꿉니다.
Secondary labels now distinguish VLM spatial candidates, OCR seat text, scale/steps/rail/performance structures and Three.js/WebGL/seat cameras/obstruction calculation. Human-provided metric dimensions and the 20-seat synthetic integration check are explicit. Saved VLM outputs, synthetic measurement input, no live VLM call and unverified real-venue accuracy remain explicit.
The edit script asserted that index.html outside the technical section is byte-identical. Three.js bundle, motion and all other scenes are unchanged. Representative revised frames inspected before v3 rendering; check passed.

## v4: light palette only
White/off-white surround, dark text and restrained lime accents. Visible text and animation scripts asserted unchanged against saved dark v3 HTML. Three.js venue content and cameras retained; canvas surround color only changed. Representative frames inspected before rendering; browser layout/contrast check passed. Full 1740-frame render succeeded: output/sightcheck-ai-hybrid-light-v4.mp4. ffprobe verified 58.000 seconds, 1920x1080, 30fps H.264 and AAC audio; 20127631 bytes. Previous outputs preserved. Reapply palette with scripts/apply-light.py after regenerating hybrid HTML, then bundle Three.js using the existing Vite config.

## Repository organization
Video sources now live in media/hyperframes-video/. Previous MP4s are in output/archive/; check reports and encoded-frame images are in output/verification/. The original HTML rebuild input is capture/index-original-draft.html. Run capture scripts from the repository root.

The frozen assets support preview/render without rebuilding the Three.js bundle. Rebuilding the bundle or recapturing uses `media/promo-video/`, originally from upstream commit `91bde61` (branch `claude/busy-rubin-84tui7`). Install that project's dependencies before recapturing. Its source paths were adapted to the new folder; original media assets remain unchanged. Generated demo data and encoded outputs are local-only. The checks above describe the original renders; after folder organization, the bundle build passed, but the HyperFrames browser smoke check timed out and no MP4 was rerendered.
