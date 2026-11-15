# Seat reader prompt (API, one item per request)

Used by `claude_preread.py`, which sends one request per review item. It is
the per-item form of `seat-reader.md`.

## Provenance

- Derived by Claude (Opus 5.5) in a Claude Code session on 2026-11-15 from
  `seat-reader.md`. The user did not edit it.
- Written before any API run and before the second blind set
  (`blind2-review.html`) was labeled.
- What changed from `seat-reader.md`, and why:
  - Removed the file-reading boundary, the Write-tool output instruction and
    the final-reply instruction. Each request carries only its own two images
    and the answer comes back through a JSON schema (`output_config.format`).
  - Removed "Judge each item independently ..." because a request holds a
    single item; this also removes the adjacent-item answer swaps seen with
    Haiku in the subagent run.
  - Removed `sample_id` and the "every value is a string" rule; the script
    attaches `sample_id` and the schema fixes the types.
- Field definitions are copied verbatim, including the wheelchair example
  under `is_seat` and `other`. It is known to be misleading for numbered
  wheelchair cells (see `experiment-report.md`), but it stays unchanged so the
  API run is comparable with the subagent run. A revised wording needs a new
  blind sample.
- `claude_preread.py` records the SHA-256 of the text block below in each
  run's `run.json`.

## Template

```text
You are an independent visual reader for a seat-map digitization experiment. Read seat-plan images and report exactly what is printed.

THE ITEM has two images, attached below in this order:
1. context_image: a whole seat-plan page (National Asian Culture Center, theatre 2 or 3). One target cell is marked with red dashed corner brackets.
2. crop_image: an enlarged crop around the same target, outlined with a red rectangle.

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
```
