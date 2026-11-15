# Seat reader prompt, paraphrase 1

A rewording of `seat-reader-api.md` for the prompt-sensitivity check in
`api-experiment-plan.md`. Run it with `claude_preread.py --prompt`.

## Provenance

- Written by Claude (Opus 5.5) in a Claude Code session on 2026-11-15, before
  any API run. The user did not edit it.
- The meaning is meant to match `seat-reader-api.md`: same fields, same
  allowed values, same zone and row rules, including the wheelchair example.
  Only the wording and sentence order change. The answer schema is the same
  because `claude_preread.py` sets it.

## Template

```text
This is a seat-map digitization experiment. Your job is to transcribe one marked cell from a seat plan exactly as printed.

You will see two images:
1. context_image - the full seat-plan page of a theatre at the National Asian Culture Center (theatre 2 or theatre 3). Red dashed corner brackets mark the target cell.
2. crop_image - a close-up of that same target, drawn inside a red rectangle.

Report the following for the marked target only:
- is_seat: answer "yes" when the target is a single seat cell, "no" when it is something else (a label, an area covering several seats such as a blue wheelchair area, or anything else), and "unsure" when it cannot be determined.
- zone: choose "main", "BOX-1", "BOX-2", "OP", "other" or "unknown".
  BOX-1 and BOX-2 are the box-seat columns at the sides, labeled BOX-1 and BOX-2.
  OP is the orchestra-pit seating in front of the stage, beside the circle marked "OP".
  main is every other ordinary audience seat, on the first floor or the second floor.
  other is for anything that is not a single seat, for example a blue wheelchair region.
- row: the row letter shown in the circled labels at the ends of the row, such as "A" or "Q". For an OP seat, give the circled number at the left of its OP row ("1" or "2"). Leave it as "" when the zone has no rows (BOX) or when no row applies.
- number: exactly what is printed inside the target cell, such as "6" or "19". For a target that is not a seat, give whatever text is visible, or "" if there is none. Take care with look-alike characters: 6 and 9, 1 and 7, I and 1 are often confused.
- confidence: "high", "medium" or "low".
- note: when confidence is below high or something is ambiguous, a short reason; otherwise "".
```
