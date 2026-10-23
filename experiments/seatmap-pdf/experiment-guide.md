# ACC seat-map experiment: phases A–C

The improved PDF baseline connects all 3,760 text candidates across seven plans.
The image baseline finds 506 gray square candidates in Theatre 2 and 244 in
Theatre 3. These are candidate and integrity counts, **not recognition accuracy**.
All 550 manual-review samples remain pending. No population accuracy or recall
has been measured.

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
and run `npm ci` followed by `npm run prepare:ocr` to prepare the existing local
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

## Manual review

Open `output/phase-abc/report.html` for comparison tables and full overlays, then
`output/phase-abc/review.html` for annotated crops. JSON, CSV, raw OCR and RGB
working images live in the respective output subfolders. Overlay colors:
green assigned candidate; red unresolved; magenta duplicate identity; blue
accessibility region; orange possible missing shape. Green is not ground truth.

The 550 deterministic samples include each PDF block's extrema, corners and
center; image row-band extrema, unresolved OCR strata, BOX columns and every
blue region. These are purposefully selected, not an unbiased random sample.
Review the full image too: candidate-only crops cannot reveal all missed seats.

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

24 synthetic/contract/evaluation tests pass. Actual seven-plan comparison checks
that all previous IDs and text centers survive. Image overlays were inspected
for unresolved glyphs, BOX/floor separation and blue-region handling; this is
qualitative diagnosis, not completed ground-truth annotation.
The local review page also passed a headless browser smoke test covering sample
loading, applicable fields, navigation persistence, JSON export/import and crop
loading. Synthetic smoke-test edits were isolated from the pending review data.

The experiment code and sanitised reports are integrated into `main` under
`experiments/seatmap-pdf`, preserving the original experiment commits. Run the
commands above from the main repository folder; a separate worktree is not
required. Source PDF/JPEG files and prior outputs remain local and ignored.
See [the experiment report](experiment-report.md) for the original baseline
and follow-up results.
No pixel-to-meter conversion or physical venue scale is inferred.
