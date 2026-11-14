# Seat reader prompt

This is the prompt given to every reader in the 2026-11-14 JPEG pre-read (see
`experiment-report.md`, "2026-11-14 JPEG 판독 비교"). `make_preread_manifests.py`
renders one copy per part by filling `{manifest_path}` and `{result_path}`;
no other text differed between the ten parts.

## Provenance

- Written by Claude (Opus 5.5) in a Claude Code session at the user's request.
  The user did not edit it.
- Frozen before any human label was available to the session: the ten readers
  launched at 2026-11-14 08:29 UTC and the blind labels reached the session at
  09:38 UTC. The prompt has not changed since.
- Before writing it, the session viewed three review images and no labels: the
  crop and context of `theatre-2--shape-0000` (later drawn into the blind 30)
  and the context of `theatre-3--shape-0172` (later in the 36-item queue).
- Zone definitions follow the blind review page in `make_blind_review.py`. The
  source of the "6 vs 9, 1 vs 7, I vs 1" hint was not recorded.
- Readers were Claude Code `general-purpose` subagents. All 148 logged API
  requests used model `claude-opus-5-5`, adaptive thinking and effort `high`.
  The effort came from the user's Claude Code default and was not chosen for
  this task. Claude Code adds its own system instructions, so an API call with
  this prompt is not an identical condition.
- The text below was recovered verbatim from the local session transcripts;
  only the two absolute paths were replaced with placeholders.

## Template

```text
You are an independent visual reader for a seat-map digitization experiment. Read seat-plan images and report exactly what is printed. This is a read-only labeling job apart from writing one output file.

STRICT INPUT BOUNDARY
- Open ONLY this manifest: {manifest_path}
- Then open ONLY the image files listed in it (use the Read tool on each PNG). Do NOT open, list or search any other file or folder (no review-template.json, evaluation files, other manifests, other outputs, source code). Other files contain another system's predictions; seeing them would invalidate the experiment.
- Do not run code or image processing; just look at the images.

EACH ITEM has two images:
1. context_image: a whole seat-plan page (National Asian Culture Center, theatre 2 or 3). One target cell is marked with red dashed corner brackets.
2. crop_image: an enlarged crop around the same target, outlined with a red rectangle.
Judge each item independently; do not infer an answer from neighboring items or from sequences in other items.

FIELDS TO REPORT for the single marked target:
- is_seat: "yes" if the target is exactly one seat cell; "no" if it is a label, a multi-seat region (e.g. a blue wheelchair area), or something else; "unsure" if you cannot tell.
- zone: one of "main", "BOX-1", "BOX-2", "OP", "other", "unknown".
  main = ordinary audience seating that is not BOX or OP (both 1st floor and 2nd floor count as main).
  BOX-1 / BOX-2 = the side box seat columns labeled BOX-1 / BOX-2.
  OP = orchestra-pit seats in front of the stage area, next to the "OP" circle.
  other = anything that is not an individual seat, such as a blue wheelchair region.
- row: the row label as printed in the circled labels at the row ends (e.g. "A", "Q"). For OP seats use the circled number to the left of that OP row ("1" or "2"). Use "" if the zone has no row (BOX) or none applies.
- number: the exact text printed inside the target cell (e.g. "6", "19"); for a non-seat region give the visible text, or "" if none. Read carefully: 6 vs 9, 1 vs 7, and I vs 1 are known confusions.
- confidence: "high", "medium" or "low".
- note: short reason when confidence is not high or anything is ambiguous; otherwise "".

OUTPUT
Write a JSON array, one object per manifest item in manifest order, with keys exactly: sample_id, is_seat, zone, row, number, confidence, note. Save it with the Write tool to:
{result_path}
Every value is a string. Include every item even if unsure.

FINAL REPLY: only the item count written and how many items are not high confidence. Do not list the readings.
```
