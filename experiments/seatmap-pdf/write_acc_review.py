"""Persist visual review notes and generate a local audit report (no OCR)."""
from pathlib import Path
from html import escape
import json

BASE = Path(__file__).resolve().parent
OUT = BASE / "output/acc-audit"
summary = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
review = {
    "method": "Visual inspection of both image overviews and all seven PDF overlays; not an exhaustive seat annotation.",
    "theatre_2": {
        "visible_legend": {"regular_sales": 466, "first_floor_regular": 402, "second_floor_regular": 64,
                           "reserved": 46, "orchestra_pit": 40, "wheelchair": 6, "total": 512},
        "seat_symbols": "Gray rectangular cells with white numeric labels; light blue row-letter circles; blue wheelchair regions; green orchestra-pit markers.",
        "layout": "Central rows A-P, separate side BOX-1 and BOX-2 columns, two orchestra-pit rows, and second-floor rows Q-R. A console interrupts lower rows.",
        "text": "Arabic seat numbers, Latin row/zone labels, Korean floor labels and capacity legend. Repeated row labels at both aisles are not additional seats.",
        "assessment": "Suitable for a separate local OCR plus rectangle/color segmentation baseline; partition floors and zones before assigning identities."
    },
    "theatre_3": {
        "source_filename_count": 244,
        "copy_filename_count": 248,
        "visible_legend": {"regular_sales": 244, "reserved_wheelchair": 4, "total": 248},
        "source_filename_count_is_total": False,
        "copy_filename_count_is_total": True,
        "seat_symbols": "Gray rectangular numeric cells, light blue row-letter circles, and a blue wheelchair area within the last row.",
        "layout": "Central rows A-L with aisles and separate BOX-1 and BOX-2 columns; last row has gaps and accessibility symbols.",
        "text": "Arabic seat numbers, Latin row/zone labels, Korean title and capacity legend. Some accessibility positions require explicit manual interpretation.",
        "assessment": "Simpler initial OCR/CV baseline candidate than Theatre 2, but define whether the target is 244 regular seats or all 248 places before scoring."
    },
    "shared_findings": [
        "Both originals are CMYK JPEG raster images, not PDFs. Direct text extraction returned zero words and zero characters.",
        "150-DPI metadata describes image/print sampling, not the physical venue scale.",
        "Convert only derived copies to RGB/grayscale for OCR/CV. Preserve the original CMYK JPEG copies unchanged.",
        "Use per-cell cropping and polarity inversion for white digits on gray backgrounds; full-page text ordering alone does not establish seat identities.",
        "Mask titles, legends, stage and console; evaluate side boxes, wheelchair regions and floor labels separately.",
        "Assess detection precision/recall with annotated pixel boxes, exact seat-label accuracy, and full zone/row/number identity accuracy. Capacity count agreement is only a sanity check.",
        "OCR/OpenCV was not run, and no recognition accuracy or detection recall is claimed. A separately annotated baseline is the next experiment, not a completed result."
    ],
    "pdf_review": [
        "The contact sheet shows blue matched labels in horizontal blocks and red unmatched labels in side/rear blocks.",
        "All seven PDFs have embedded text and vector drawings, with zero embedded raster images on their sole page.",
        "The existing extractor searches horizontal top borders below block labels. Rotated or side-positioned labels in thrust, road and arena layouts violate that scope.",
        "Four automatic-check passes are not four ground-truth accuracy passes. Full seat ID and physical seat position validation remains unperformed."
    ],
    "next_baseline": [
        "Start with Theatre 3, preserving pixel coordinates and separating main seating from side boxes.",
        "Manually annotate regular cells, accessible places and row/zone labels, including ambiguous final-row symbols, before computing recognition scores.",
        "Compare local OCR alone with rectangle segmentation plus per-cell OCR; report unmatched/ambiguous candidates instead of assigning guessed identities.",
        "Then evaluate Theatre 2 on orchestra pit, floor 1, floor 2, boxes and wheelchair areas separately."
    ]
}
(OUT / "image-assessment.json").write_text(json.dumps(review, indent=2), encoding="utf-8")
pdf_rows = "".join(f"<tr><td>{escape(r['file'])}</td><td>{r['reported_seat_count']}</td><td>{r['seat_tokens']}</td><td>{r['matched']}</td><td>{r['unmatched']}</td><td>{'PASS' if r['automatic_checks_passed'] else 'FAIL'}</td><td><a href='theatre-1/{Path(r['file']).stem}/overlay.png'>Overlay</a> / <a href='theatre-1/{Path(r['file']).stem}/seats.json'>JSON</a> / <a href='theatre-1/{Path(r['file']).stem}/raw-layout.json'>Raw layout</a></td></tr>" for r in summary['pdf_results'])
image_rows = "".join(f"<tr><td>{r['file']}</td><td>{r['width_px']} x {r['height_px']}</td><td>{r['mode']}</td><td>{r['direct_text_words']}</td><td>Not measured</td></tr>" for r in summary['image_results'])
notes = "".join(f"<li>{escape(x)}</li>" for x in review['shared_findings'])
pdf_notes = "".join(f"<li>{escape(x)}</li>" for x in review['pdf_review'])
image_sections = ""
for n in [2, 3]:
    entry = review[f'theatre_{n}']
    image_sections += f"<h3>Theatre {n}</h3><p>{escape(entry['layout'])}</p><p>{escape(entry['seat_symbols'])}</p><p>{escape(entry['text'])}</p><p>{escape(entry['assessment'])}</p><img src='theatre-{n}/overview.png' alt='Theatre {n} source overview'>"
html = f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>ACC local seat-map audit</title>
<style>body{{font:16px/1.55 system-ui;max-width:1200px;margin:40px auto;padding:0 24px;color:#182432}}table{{border-collapse:collapse;width:100%;margin:20px 0}}td,th{{padding:9px;text-align:left;border:1px solid #ccd4dc}}th{{background:#edf2f6}}img{{max-width:100%;max-height:1100px;object-fit:contain}}.notice{{padding:18px;background:#fff0cf}}code{{background:#edf2f6}}</style>
<h1>ACC local seat-map audit</h1><p>Executed: {summary['executed_at_utc']}. Originals: 7 PDFs + 2 JPEGs; all 9 copy hashes match. Source bytes and modification times are unchanged.</p>
<p><a href='../../input/manifest.json'>Local source/copy SHA-256 manifest</a> | <a href='summary.json'>Measured results</a> | <a href='image-assessment.json'>Visual assessment</a></p>
<p class="notice"><strong>Theatre 3 count discrepancy:</strong> the source filename says 244, while the visible legend says 244 regular seats + 4 wheelchair places = 248 total. The copied filename is theatre-3-248.jpg to match the visible total; the original source filename remains unchanged. These are source legend values, not detected-seat counts.</p>
<h2>Theatre 1: unchanged PyMuPDF baseline</h2><p>Extractor source: ca5ff922d0716456790342e9e96d7347cef732fb. Python {summary['environment']['python']}; PyMuPDF {summary['environment']['pymupdf']}. Four synthetic unit tests passed.</p>
<table><tr><th>PDF</th><th>Reported</th><th>Seat text tokens</th><th>Block matched</th><th>Unmatched</th><th>Automatic integrity</th><th>Local evidence</th></tr>{pdf_rows}</table>
<ul>{pdf_notes}</ul><img src='pdf-contact-sheet.png' alt='Seven PDF overlays, blue matched and red unmatched'>
<h2>Theatres 2 and 3: image feasibility</h2><table><tr><th>Copy</th><th>Pixels</th><th>Color mode</th><th>Direct text words</th><th>OCR/CV accuracy</th></tr>{image_rows}</table><ul>{notes}</ul>{image_sections}
<h2>Boundaries</h2><p>No paid APIs, commits, pushes, or product-code changes. Inputs and outputs are ignored by Git. PDF text centers are in page points; image locations are pixels. Neither is a surveyed seat center or meter-scale venue coordinate. No full manual seat-level ground truth was evaluated.</p></html>"""
(OUT / "report.html").write_text(html, encoding="utf-8")
print(str(OUT / "report.html"))
