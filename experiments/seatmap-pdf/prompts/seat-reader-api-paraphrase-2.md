# Seat reader prompt, paraphrase 2

A second rewording of `seat-reader-api.md` for the prompt-sensitivity check in
`api-experiment-plan.md`. It is terser than paraphrase 1 and lists the zones
as a table. Run it with `claude_preread.py --prompt`.

## Provenance

- Written by Claude (Opus 5.5) in a Claude Code session on 2026-11-15, before
  any API run. The user did not edit it.
- The meaning is meant to match `seat-reader-api.md`: same fields, same
  allowed values, same zone and row rules, including the wheelchair example.
  The answer schema is the same because `claude_preread.py` sets it.
- Two small additions: a gloss for `unknown` ("cannot tell"), which the
  original lists without a definition, and "Do not guess beyond what the
  images show", a restatement of "report exactly what is printed".

## Template

```text
Task: read one marked cell on a theatre seat plan and copy what is printed there. Do not guess beyond what the images show.

Images (in this order):
- context_image: whole seat-plan page, National Asian Culture Center theatre 2 or 3. Target = the cell inside red dashed corner brackets.
- crop_image: enlarged view of the same target, inside a red rectangle.

Answer these fields for that one target.

is_seat
  yes    = exactly one seat cell
  no     = a label, a region spanning several seats (e.g. a blue wheelchair area), or anything else
  unsure = cannot tell

zone
  main    = normal audience seats that are neither BOX nor OP; 1st and 2nd floor both count
  BOX-1   = side box-seat column labeled BOX-1
  BOX-2   = side box-seat column labeled BOX-2
  OP      = orchestra-pit seats in front of the stage, next to the "OP" circle
  other   = not an individual seat, e.g. a blue wheelchair region
  unknown = cannot tell

row
  The row label in the circles at the row ends (e.g. "A", "Q").
  OP seats: the circled number left of the OP row ("1" or "2").
  "" for BOX seats or when no row applies.

number
  The exact text inside the target cell (e.g. "6", "19").
  Not a seat: the visible text, or "" if none.
  Check carefully: 6/9, 1/7 and I/1 are easy to confuse.

confidence
  high, medium or low

note
  Short reason if confidence is not high or anything is ambiguous; otherwise "".
```
