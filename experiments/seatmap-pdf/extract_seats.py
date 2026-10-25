"""Extract unreviewed seat candidates from selected vector PDF seat maps.

A narrow baseline for ACC Theatre 1-style rectangular block plans, not a
general PDF/CAD parser or a metric seat-geometry extractor.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import fitz

SEAT_PATTERN = re.compile(r"^(?P<row>\d+)-(?P<number>\d+)$")
BLOCK_PATTERN = re.compile(r"^[A-Z]블록$")
REPORTED_COUNT_PATTERN = re.compile(r"총\s*좌석\s*:\s*(\d+)\s*석?")


@dataclass(frozen=True)
class Header:
    block: str
    x_center: float
    label_bottom: float
    left: float
    right: float


def _center_x(box):
    return (box[0] + box[2]) / 2


def _center_y(box):
    return (box[1] + box[3]) / 2


def _horizontal_rules(page):
    """Locate horizontal vector rectangles for block boundaries."""
    for drawing in page.get_drawings():
        rect = drawing["rect"]
        if rect.width >= 30 and rect.height <= 3:
            yield rect


def find_headers(page):
    """Use block-top border rules as conservative X bounds."""
    rules = list(_horizontal_rules(page))
    headers = []
    errors = []
    for word in page.get_text("words", sort=False):
        label = word[4]
        if not (BLOCK_PATTERN.fullmatch(label) or label == "FOH석"):
            continue
        x_center = _center_x(word)
        label_bottom = word[3]
        possible = [
            rule for rule in rules
            if rule.x0 <= x_center <= rule.x1
            and abs(rule.y0 - label_bottom) <= 8
        ]
        if not possible:
            errors.append({"header": label, "reason": "block_top_rule_not_found"})
            continue
        rule = min(possible, key=lambda r: (abs(r.y0 - label_bottom), -r.width))
        block = label[0] if label.endswith("블록") else "FOH"
        headers.append(Header(block, x_center, label_bottom, rule.x0, rule.x1))
    return headers, errors


def extract(pdf_path: Path) -> dict:
    with fitz.open(pdf_path) as document:
        if len(document) != 1:
            raise ValueError(f"Expected a one-page plan, found {len(document)} pages")
        page = document[0]
        headers, header_errors = find_headers(page)
        words = page.get_text("words", sort=False)
        seat_words = [w for w in words if SEAT_PATTERN.fullmatch(w[4])]

        seats = []
        unmatched = []
        for word in seat_words:
            cx, cy = _center_x(word), _center_y(word)
            available = [h for h in headers if h.label_bottom <= cy]
            if not available:
                unmatched.append({
                    "text": word[4],
                    "bbox_pt": list(word[:4]),
                    "reason": "no_header_above",
                })
                continue
            last_label_y = max(h.label_bottom for h in available)
            band = [h for h in headers if abs(h.label_bottom - last_label_y) <= 2]
            containing = [h for h in band if h.left <= cx <= h.right]
            if len(containing) != 1:
                unmatched.append({
                    "text": word[4],
                    "bbox_pt": list(word[:4]),
                    "reason": "block_ambiguous" if containing else "no_block_boundary",
                })
                continue
            header = containing[0]
            parts = SEAT_PATTERN.fullmatch(word[4])
            row, number = int(parts["row"]), int(parts["number"])
            bbox = [round(float(p), 3) for p in word[:4]]
            seats.append({
                "seat_id": f"{header.block}:{row}-{number}",
                "block": header.block,
                "row": row,
                "number": number,
                "label": word[4],
                "text_bbox_pt": bbox,
                "text_center_pt": [round(cx, 3), round(cy, 3)],
                "review_status": "unreviewed",
            })

        seats.sort(key=lambda s: (s["block"], s["row"], s["number"]))
        counts = Counter(seat["seat_id"] for seat in seats)
        duplicate_ids = sorted(k for k, count in counts.items() if count > 1)
        count_match = REPORTED_COUNT_PATTERN.search(page.get_text())
        reported = int(count_match[1]) if count_match else None
        summary = {
            "seat_tokens": len(seat_words),
            "matched": len(seats),
            "unmatched": len(unmatched),
            "duplicate_id_count": len(duplicate_ids),
            "reported_seat_count": reported,
            "token_count_equals_reported": (
                reported is not None and len(seat_words) == reported
            ),
            "needs_review": True,
            "automatic_checks_passed": (
                bool(headers)
                and not header_errors
                and not unmatched
                and not duplicate_ids
                and reported is not None
                and reported == len(seats)
            ),
        }
        return {
            "source_filename": pdf_path.name,
            "page_count": len(document),
            "page_size_pt": [page.rect.width, page.rect.height],
            "coordinate_system": (
                "PDF page points, top-left origin; not physical seat centers "
                "or metric coordinates"
            ),
            "extractor_scope": (
                "single-page vector PDF, horizontal block headers, "
                "rectangular seat grids"
            ),
            "block_headers": [vars(h) for h in headers],
            "header_errors": header_errors,
            "summary": summary,
            "duplicate_ids": duplicate_ids,
            "unmatched": unmatched,
            "seats": seats,
        }


def render_preview(pdf_path: Path, results: dict, output_path: Path) -> None:
    """Draw labels on an in-memory copy, never edit the input file."""
    with fitz.open(pdf_path) as document:
        page = document[0]
        for seat in results["seats"]:
            page.draw_rect(
                fitz.Rect(seat["text_bbox_pt"]),
                color=(0, 0.5, 0.9), width=0.45, overlay=True,
            )
        for missing in results["unmatched"]:
            page.draw_rect(
                fitz.Rect(missing["bbox_pt"]),
                color=(1, 0, 0), width=1.3, overlay=True,
            )
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        pix.save(output_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="One-page vector PDF seat plan")
    parser.add_argument(
        "--output-dir", type=Path, required=True,
        help="Untracked output directory",
    )
    args = parser.parse_args()
    if not args.pdf.is_file():
        parser.error(f"PDF does not exist: {args.pdf}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result = extract(args.pdf)
    prefix = args.pdf.stem
    json_path = args.output_dir / f"{prefix}.seats.json"
    preview_path = args.output_dir / f"{prefix}.preview.png"
    json_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    render_preview(args.pdf, result, preview_path)
    print(json.dumps({
        "summary": result["summary"],
        "json": str(json_path),
        "preview": str(preview_path),
    }, ensure_ascii=False))
    return 0 if result["summary"]["automatic_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
