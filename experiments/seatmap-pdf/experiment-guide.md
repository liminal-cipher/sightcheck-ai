# ACC seat-map experiment: commands and tools

This guide holds the commands and tool behavior. Results, reasons and limits
are in [the experiment report](experiment-report.md) (Korean).

- PDF (theatre 1): seven plans, 3,760 seat texts connected to blocks; the user
  checked every block in color overlays.
- JPEG (theatres 2 and 3): CV finds 506 and 244 gray seat cells (matching the
  legends). Claude Sonnet 5.5 read all 750 cells; the structure check found no
  contradictions. Accuracy evidence comes from 70 prediction-blind labels and is
  limited to that purposive sample.
- Not measured: CV detection recall, position error, and any venue other than
  ACC theatres 1-3.

## Run locally

Run from the repository root in PowerShell. Inputs and the saved
`output/acc-audit` baseline must already exist. The runner reads that baseline;
it does not repeat input preparation or run the original extractor.

```powershell
$seatmapPython = 'experiments/seatmap-pdf/.venv/Scripts/python.exe'
# Only needed when setting up the experiment environment:
& $seatmapPython -m pip install -r experiments/seatmap-pdf/cv-requirements.txt

& $seatmapPython experiments/seatmap-pdf/run_experiment.py
& $seatmapPython -m unittest discover -s experiments/seatmap-pdf -p 'test_*.py' -v

# Rebuild PDF comparison and review/report using existing image results:
& $seatmapPython experiments/seatmap-pdf/run_experiment.py --skip-images
```

Node.js and the repository's existing `tesseract.js` dependency are required.
For a fresh checkout, create the isolated environment with
`python -m venv experiments/seatmap-pdf/.venv`, install the requirements above,
and run `pnpm install --frozen-lockfile` (the root has no npm lockfile), followed
by `npm run prepare:ocr` to prepare the existing local
OCR dependencies. Dependency setup may download packages; recognition itself
uses only local resources.
The OCR worker, WASM core and English language file are read locally from
`node_modules` and `public/ocr/eng.traineddata.gz`. OCR makes no paid API calls
and does not download language data. Korean legend text is not recognized by
this English-only experiment. `local-ocr.mjs` does not import the product OCR
parser. Dependencies are isolated in the experiment's existing `.venv`; no
product dependency files were changed.

Private input files and cached audit results are intentionally absent from Git.
The independent PDF/image commands below work with locally supplied inputs;
the comparison runner additionally requires the saved `output/acc-audit`
summary and per-PDF `seats.json` files. `audit_acc.py` and `write_acc_review.py`
preserve the earlier audit workflow, not the improved algorithm. If recreating
that earlier audit in a new local environment, its private `input/manifest.json`
must contain a `files` array with `source_path`, `copy_path`, `theatre`, `sha256`,
`source_mtime_ns`, and `expected_count_from_filename`; `copy_filename_seat_count`
is optional. These values must describe the local files and verified metadata,
not guessed values. Run `audit_acc.py` and then `write_acc_review.py` only when
intentionally recreating that audit: they write to `output/acc-audit`.
Do not commit the manifest, source paths, cached audit, or generated images.

Individual runs:

```powershell
& $seatmapPython experiments/seatmap-pdf/extract_layout.py experiments/seatmap-pdf/input/theatre-1/arena-944.pdf --output-dir experiments/seatmap-pdf/output/single-pdf
& $seatmapPython experiments/seatmap-pdf/image_baseline.py experiments/seatmap-pdf/input/theatre-3/theatre-3-248.jpg --output-dir experiments/seatmap-pdf/output/single-image
```

The original 2026-10-20 PDF baseline (`extract_seats.py`, kept unchanged)
writes a JSON and a review PNG per PDF and exits with code 2 when seats are
unmatched, duplicated or do not match the printed total:

```powershell
python -m pip install -r experiments/seatmap-pdf/requirements.txt
python experiments/seatmap-pdf/extract_seats.py "C:\path\to\프로시니엄형 - 608석(기본).pdf" --output-dir experiments/seatmap-pdf/output
```

## Results and interpretation

| PDF | Before matched / unmatched | After matched / unmatched |
| --- | ---: | ---: |
| arena-944 | 608 / 336 | 944 / 0 |
| thrust-832 | 608 / 224 | 832 / 0 |
| road-560 | 0 / 560 | 560 / 0 |
| proscenium-608 | 608 / 0 | 608 / 0 |
| split-large-384 | 384 / 0 | 384 / 0 |
| split-small-224 | 224 / 0 | 224 / 0 |
| split-small-208 | 208 / 0 | 208 / 0 |

All previous assignments retain their block/row/number IDs and rounded text
centers. Counts, identity uniqueness and agreement with the printed total are
automatic integrity checks. They do not prove that a token names the correct
physical seat. The original `extract_seats.py`, its tests and `acc-audit` output
remain unchanged. Use `extract_layout.py` for the improved baseline.

| Image | Gray shape candidates | Accepted number OCR | Assigned identity candidates | Unmatched shapes | Blue regions |
| --- | ---: | ---: | ---: | ---: | ---: |
| Theatre 2 | 506 | 465 | 366 | 140 | 6 |
| Theatre 3 | 244 | 220 | 202 | 42 | 2 |

Both source JPEGs are CMYK, width 1754 px; heights are 2550 and 2480 px.
Derived RGB copies are saved alongside results. Theatre 2's printed legend
separates 466 regular, 40 orchestra-pit and 6 wheelchair seats. Gray shape
candidates include the orchestra-pit seats; they are not all regular-sale seats.
Theatre 3's legend separates 244 regular seats and 4 wheelchair spaces (248
total). Its two connected blue regions are **not** two wheelchair seats, nor
are they split into four objects using the legend count. Accessibility-region
seat counts remain unknown.

## Algorithms and observed failures

`extract_layout.connected_rules` groups touching thin PDF vector rules. A block
label's text direction determines whether to search an adjacent horizontal or
vertical boundary. The boundary's span clips its connected region. This allows
side labels on K–N and road blocks, and below-grid labels on arena O/P. It also
separates C/D in the 208-seat plan, where lower boundaries connect across an
intentional gap. The method does not depend on filenames, hardcoded venue
coordinates, block totals or expected number sequences. It leaves conflicting
regions, missing boundaries and duplicate identities unresolved.

The supported geometry is axis-aligned boundaries with horizontal or 90-degree
labels. Arbitrarily slanted text/grids, broken or overly connected vectors and
irregular shared borders need more work. A bounded border-only fallback retains
the old synthetic top-rule contract; it is weaker evidence than a closed grid
and is recorded separately. PDF positions describe text, not seat-shape centers.

`image_baseline.detect_shapes` thresholds neutral midtone pixels, extracts outer
OpenCV contours and estimates the modal square size. This suits these uniformly
gray cells and avoids OCR-dependent shape detection. It will need changes for
colored, circular, touching or low-contrast seats. Pale row markers and saturated
blue regions are detected separately. Thin stage outlines are rejected by region
size and fill ratio.

Numbers are cropped, contrast-inverted and enlarged in mosaics. Sparse OCR
handles many two-digit numbers, but skips some single characters; uncertain tiles
are retried with single-line or single-character segmentation. The first run
still misses some `6`/`9` glyphs and row `I`; Theatre 2 also has unresolved O/R
row markers and orchestra-pit labels. Full-page OCR merges neighboring digits
into long strings. Its valid BOX labels can still locate the two side columns.

Row assignment requires two agreeing OCR row markers. BOX assignment follows a
contiguous vertical column and stops at a large gap: an early prototype incorrectly
extended BOX columns into the second floor; a regression test now covers this.
Low-confidence OCR, conflicting rows and duplicate identities abstain. No row
name is filled from alphabetic order. A gap is only a review hint: aisles and
deliberately removed seats can look like missing detections. No gap candidates
were found with the current conservative one-cell-gap thresholds; that is not
evidence of perfect detection recall.

## PDF block overlays

For a whole-layout check of PDF block assignment, render one image per layout
from the saved `theatre-1/<layout>/seats.json` results. The original PDFs are
opened read-only; images go to `output/phase-abc/block-overlays/`:

```powershell
& $seatmapPython experiments/seatmap-pdf/render_block_overlay.py
```

Each seat text box is filled with its assigned block's color and each block
region is outlined in the same color; unmatched seats get a thick red outline.
A reviewer checks that no box contains a seat of another color. This covers
block assignment only, not seat text reading or physical seat positions.

## JPEG reading comparison

Blind labels come first so they can score both readers. This page draws a
seeded random subset of the JPEG review samples and hides every prediction:

```powershell
& $seatmapPython experiments/seatmap-pdf/make_blind_review.py --count 30
```

Save the page's JSON as `output/phase-abc/blind-review-result.json`. To split
the samples for model readers and render one prompt per part from
`prompts/seat-reader.md` (seed 7, ten parts, as in the 2026-11-14 run):

```powershell
& $seatmapPython experiments/seatmap-pdf/make_preread_manifests.py
```

Model readings go in `output/phase-abc/subagent-preread/result-*.json`, one array per
file with `sample_id`, `is_seat`, `zone`, `row`, `number`, `confidence` and
`note`. Then score both readers on the blind labels and build the queue:

```powershell
& $seatmapPython experiments/seatmap-pdf/compare_readings.py
& $seatmapPython experiments/seatmap-pdf/make_queue_review.py --model-only 20
```

To compare other readers on only the human-confirmed items, list their sample
IDs in a text file, pass it with `--only` and a separate `--dest` per reader,
then score each reader folder:

```powershell
& $seatmapPython experiments/seatmap-pdf/make_preread_manifests.py --only experiments/seatmap-pdf/output/phase-abc/labelled-ids.txt --parts 4 --dest experiments/seatmap-pdf/output/phase-abc/subagent-sonnet
& $seatmapPython experiments/seatmap-pdf/score_readers.py opus=subagent-preread sonnet=subagent-sonnet
```

`score_readers.py` reports blind labels as the primary score and queue
verdicts separately, because queue verdicts were given with a model reading
visible. It rewrites `reader-scores.json` with only the readers passed, so pass
every reader you want to keep in that file.

`compare_readings.py` scores only blind-labeled items. Other items are routed
to the queue when the OCR and model readings differ, plus seeded spot checks of
agreements. The queue page shows both readings, so its verdicts confirm data
but are not accuracy measurements.

A second blind set skips the items already labeled and fixes how many items
come from each OCR sampling category, so rare cells such as BOX seats are
represented. The categories come from the OCR stratum, never from a reader's
answer. Use a new `--name` so the first set's files stay untouched:

```powershell
& $seatmapPython experiments/seatmap-pdf/make_blind_review.py --name blind2 --seed 20261115 --exclude experiments/seatmap-pdf/output/phase-abc/labelled-ids.txt --quota BOX-1=7 --quota BOX-2=7 --quota blue-region=1 --quota row_or_zone_unresolved=7 --quota number_ocr_uncertain=9 --quota main=9
& $seatmapPython experiments/seatmap-pdf/score_readers.py --blind blind-review-result.json --blind blind2-review-result.json opus=subagent-preread
```

Save that page's JSON as `output/phase-abc/blind2-review-result.json`. Each
blind set is scored separately because the sets were drawn differently.

### Claude API runs

`claude_preread.py` sends one request per item with
`prompts/seat-reader-api.md`, an explicit model and effort, adaptive thinking
and a JSON schema for the answer. It writes `result-01.json` into the run
folder, so `score_readers.py` can score it like a subagent folder. `plan`
needs no API key and sends nothing; it prints an upper cost estimate and saves
`request-preview.json`. A run folder is tied to its settings in `run.json`, so
another model or effort needs another `--name`.

```powershell
& $seatmapPython -m pip install -r experiments/seatmap-pdf/api-requirements.txt
& $seatmapPython experiments/seatmap-pdf/claude_preread.py plan --name api-opus-high --model opus --effort high --ids experiments/seatmap-pdf/output/phase-abc/blind2-review-samples.json
# With ANTHROPIC_API_KEY set: half price, usually finished within an hour.
& $seatmapPython experiments/seatmap-pdf/claude_preread.py submit --name api-opus-high --model opus --effort high --ids experiments/seatmap-pdf/output/phase-abc/blind2-review-samples.json
& $seatmapPython experiments/seatmap-pdf/claude_preread.py collect --name api-opus-high
& $seatmapPython experiments/seatmap-pdf/score_readers.py --blind blind-review-result.json --blind blind2-review-result.json opus-api=api-opus-high
```

`--ids` can be repeated to join several ID lists, and `--prompt` selects
another prompt file, such as the paraphrases used for the stability check.
The planned runs, the decision rule and the budget are fixed in
[`api-experiment-plan.md`](api-experiment-plan.md).

`run` sends the same requests directly instead of as a batch, skipping items
that already have an answer. `submit` and `run` refuse to send when the upper
estimate is above `--max-cost` (USD 10 by default). The estimate counts image
tokens with the documented 28×28-pixel patch rule and high-resolution limits,
and assumes a generous output length (`--assume-output-tokens`), so real costs
are usually lower; `collect` and `run` print the measured token usage. In the
2026-11 runs the input estimate came out about 9% low, while output averaged
about 40-120 tokens per item, far below the default assumption of 4,000.

### Full-map reading

`make_cell_items.py` prepares the same two images for every gray seat cell of
theatres 2 and 3 (750 cells), not only for the review samples. It draws them
with the review-sample code, reuses the saved images of cells that are already
samples, and writes `cell-items.json`. `--verify` redraws the reused cells and
fails unless every pixel matches. New images go to `output/phase-abc/
cell-contexts/` (about 1 MB each) and `cell-crops/`; delete `cell-contexts/`
after the run and rebuild it when needed.

`claude_preread.py --cells` reads that list instead of `--ids`. `submit`
splits a large list into several batches under the request-size limit and
`collect` waits until all of them have ended. The run folder plugs straight
into `score_readers.py` and `check_seatmap.py`:

```powershell
& $seatmapPython experiments/seatmap-pdf/make_cell_items.py --verify
& $seatmapPython experiments/seatmap-pdf/claude_preread.py submit --name api-sonnet-high-cells --model sonnet --effort high --cells experiments/seatmap-pdf/output/phase-abc/cell-items.json --assume-output-tokens 300 --max-cost 8
& $seatmapPython experiments/seatmap-pdf/claude_preread.py collect --name api-sonnet-high-cells
& $seatmapPython experiments/seatmap-pdf/check_seatmap.py --source api-sonnet-high-cells --source ocr --compare ocr --expect theatre-2:total=506 --expect theatre-2:OP=40 --expect theatre-3:total=244
```

### Structure check

`check_seatmap.py` flags readings that contradict the plan itself, so a
reviewer only needs to open the flagged cells of a full-map reading. It needs
no ground truth. Cell positions come from the CV shape detection in
`<theatre>/seats.json`; only gray seat cells are checked, not blue wheelchair
regions. Readings come from sources in priority order (a reading folder,
`ocr`, `labels`), and the checks are:

- no ID appears twice;
- numbers run in order along each row (or down each BOX column);
- touching cells differ by the row's usual step;
- each cell sits on its row's line;
- row letters run down the page;
- the seat count matches the legend, when `--expect` gives it;
- with `--compare ocr`, the OCR reading agrees wherever both readers answered.

For an unseen plan the primary source is a full model reading. `labels` holds
the experiment's human labels; in a review workflow the reviewer's corrections
take that place and are re-checked against the rest of the map. Leave it out
when measuring the checker, because labeled cells cannot raise flags.

`--inject N` plants N realistic single errors (look-alike digits, neighboring
numbers, neighboring row letters), one at a time, and reports how many raise a
structural flag on the planted cell:

```powershell
& $seatmapPython experiments/seatmap-pdf/check_seatmap.py --source api-sonnet-high-cells --expect theatre-2:total=506 --expect theatre-2:OP=40 --expect theatre-3:total=244 --inject 300
```

Before the full reading, the same measurement used the partial
`subagent-preread` reading filled in with `ocr`.

The legend counts are gray seat cells only: theatre 2 lists 466 regular and 40
OP seats, theatre 3 lists 244 regular seats; wheelchair seats are blue regions
and are not counted here. The report goes to
`output/phase-abc/structure-check.json` (`--name` changes the file stem).

### Whole-map review page

`make_map_review.py` draws every detected cell on each plan, colored by the
same checks: red for flagged cells, amber dashed for unread cells, green for
reviewed cells and dark blue dashed for wheelchair regions. Clean cells are
left unmarked. The default list, “확인할 칸”, holds the flagged and unread cells
not yet reviewed, and the page opens the first flagged cell (or the first cell
in the list). A cell shows a zoomed view, its reading, its OCR reading and the
flag reasons. The form starts with the current reading, so “저장하고 다음 칸”
(or Enter) confirms it as is or saves a correction. `n` and `p` step through
the current list, top to bottom and left to right, and wrap around at the
ends. They are ignored while typing in a form field.

```powershell
& $seatmapPython experiments/seatmap-pdf/make_map_review.py --source api-sonnet-high-cells --source ocr --compare ocr --expect theatre-2:total=506 --expect theatre-2:OP=40 --expect theatre-3:total=244
```

Open `output/phase-abc/map-review.html`. The page keeps reviews in browser
storage and saves them with “결과 파일로 저장” as `map-review-result.json`. Place the
file in `output/phase-abc/` and pass it first to re-check the corrected map:

```powershell
& $seatmapPython experiments/seatmap-pdf/check_seatmap.py --source map-review-result.json --source api-sonnet-high-cells --source ocr --compare ocr
```

The page does not re-run the checks itself.

## Manual review

To refresh only the review screen and PDF/JPEG context images from existing results
and the original local PDFs (read-only),
without rewriting review JSON, evaluations or seat crops:

```powershell
& $seatmapPython experiments/seatmap-pdf/run_experiment.py --review-only
```

The seat enlargement's red rectangle extends beyond the candidate bbox by
`SEAT_HIGHLIGHT_PADDING` in `run_experiment.py`: 1.5 PDF points (3 rendered pixels
at scale 2) or 3 JPEG pixels on each side. Crop size, origin and position mapping
are unchanged. To update existing seat crops alone, preserving context images
and all review/evaluation JSON:

```powershell
& $seatmapPython experiments/seatmap-pdf/run_experiment.py --crops-only
```

PDF samples retain the seat enlargement and add a block context image. Its bounds
include the predicted region's `bbox_pt`, the complete `label_bbox_pt` and the
selected seat, with proportional space for nearby boundaries. This includes side
and rear labels regardless of text direction. Blue outlines show predicted block
extents; thin orange corners outside the source vector cell locate the selected seat
candidate without covering source ink. If no enclosing cell is found, the marker
is omitted with a notice. Neither mark
confirms correctness. Open the image at full size to inspect it; position clicks
still belong to the original seat crop. Missing predicted regions use the full
page. JPEG samples add a full-plan image from the saved RGB copy, preserving
row labels, BOX columns and floor divisions. Orange exterior corners locate the
selected candidate without covering source ink. Open at full size to read labels.
Predicted zones and rows are explicitly unverified; no inferred zone boundary or
floor assignment is added. Blue regions remain region candidates, not individual
seats. Seat crops, position annotation and the exported JSON schema are unchanged.

Open `output/phase-abc/report.html` for comparison tables and full overlays, then
`output/phase-abc/review.html` for annotated crops. JSON, CSV, raw OCR and RGB
working images live in the respective output subfolders. Overlay colors:
green assigned candidate; red unresolved; magenta duplicate identity; blue
accessibility region; orange possible missing shape. Green is not ground truth.

The 550 deterministic samples (341 PDF, 209 JPEG) include each PDF block's
extrema, corners and center; image row-band extrema, unresolved OCR strata, BOX
columns and every blue region. These are purposefully selected, not an unbiased
random sample. Review the full image too: candidate-only crops cannot reveal all
missed seats. This shape/position review was never completed: the PDF samples
were replaced by the full block overlays, and 106 JPEG samples were labeled
through the blind and queue pages instead.

For each sample, mark shape correctness (JPEG square candidates only), text
correctness and block/row/number correctness separately. Click the intended
center to record position error; PDF text anchors use page points and JPEG shape
anchors use pixels. Enter corrected block/row/number/text or notes when needed.
Use `uncertain` when the source is insufficient. Export the review JSON and keep
it inside ignored `output/`; the page does not autosave. Import an exported file
to resume. Regenerating reports resets the template, never the separately exported
review file.

```powershell
& $seatmapPython experiments/seatmap-pdf/evaluate_review.py experiments/seatmap-pdf/output/phase-abc/review-completed.json --output experiments/seatmap-pdf/output/phase-abc/review-evaluation.json
```

Evaluation reports applicable reviewed denominators, wrong automatic matches,
unmatched samples, correction IDs and position errors separately by document
and unit. Pending and uncertain samples do not become failures or successes.
Record independently observed missed objects with document, kind, center, unit
and notes in the review page. Full recall still needs a complete independent
inventory of a defined region; this tool does not estimate it from printed totals.

## Small learning exercises

1. Change the relative thresholds in `image_baseline.gap_candidates`. Add a test
   with a deliberate aisle and a one-seat hole. Explain why increasing sensitivity
   also raises false missing-seat alarms; keep `is_seat` false.
2. Extend `test_layout.GeometryTests.test_conflicting_labels_abstain` with a rotated
   competing label. Inspect how boundary contact and label direction interact.
   A safe test should accept abstention instead of rewarding a guessed block.

## Scope and validation

The original recorded run passed 24 synthetic/contract/evaluation tests.
On 2026-10-26, all 33 local tests passed, including the nine additional
review-context tests. On 2026-11-20, all 69 Python tests passed. Actual
seven-plan comparison checks
that all previous IDs and text centers survive. Image overlays were inspected
for unresolved glyphs, BOX/floor separation and blue-region handling; this is
qualitative diagnosis, not completed ground-truth annotation.
The local review page also passed a headless browser smoke test covering sample
loading, applicable fields, navigation persistence, JSON export/import and crop
loading. Synthetic smoke-test edits were isolated from the pending review data.

The experiment code and sanitized reports are integrated into `main` under
`experiments/seatmap-pdf`, preserving the original experiment commits. Run the
commands above from the main repository folder; a separate worktree is not
required. Source PDF/JPEG files and prior outputs remain local and ignored.
See [the experiment report](experiment-report.md) for the original baseline
and follow-up results.
No pixel-to-meter conversion or physical venue scale is inferred.
