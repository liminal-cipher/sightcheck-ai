"""Self-contained tests from synthetic vector grids, never source PDFs."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import fitz

from extract_seats import extract


def make_pdf(path: Path, count_label: int = 5,
             include_rules: bool = True, pages: int = 1):
    document = fitz.open()
    for page_index in range(pages):
        page = document.new_page(width=400, height=500)
        if page_index:
            continue
        for label, x0, x1, y, values in [
            ("A블록", 20, 120, 100, ["1-1", "1-2", "2-1"]),
            ("B블록", 140, 320, 100, ["1-1", "1-2"]),
        ]:
            page.insert_text(
                (x0 + 30, y), label, fontname="korea", fontsize=10,
            )
            if include_rules:
                bbox = next(
                    w for w in page.get_text("words") if w[4] == label
                )
                top = bbox[3]
                page.draw_rect(
                    fitz.Rect(x0, top, x1, top + 1),
                    color=(0, 0, 0), fill=(0, 0, 0),
                )
            for idx, token in enumerate(values):
                page.insert_text(
                    (x0 + 10 + idx * 25, y + 18),
                    token, fontsize=8,
                )
        page.insert_text(
            (20, 400), f"총좌석: {count_label}석",
            fontname="korea", fontsize=10,
        )
    document.save(path)
    document.close()


class SeatMapExtractionTests(unittest.TestCase):
    def test_uses_block_identity_for_repeated_numbers(self):
        with tempfile.TemporaryDirectory() as temp:
            pdf = Path(temp) / "synthetic.pdf"
            make_pdf(pdf)
            result = extract(pdf)
            self.assertEqual(result["summary"]["seat_tokens"], 5)
            self.assertTrue(result["summary"]["automatic_checks_passed"])
            self.assertEqual(
                {s["seat_id"] for s in result["seats"]},
                {"A:1-1", "A:1-2", "A:2-1", "B:1-1", "B:1-2"},
            )
            self.assertTrue(all(
                seat["review_status"] == "unreviewed"
                for seat in result["seats"]
            ))

    def test_missing_rules_are_not_guessed(self):
        with tempfile.TemporaryDirectory() as temp:
            pdf = Path(temp) / "synthetic.pdf"
            make_pdf(pdf, include_rules=False)
            result = extract(pdf)
            self.assertFalse(result["summary"]["automatic_checks_passed"])
            self.assertEqual(result["summary"]["matched"], 0)
            self.assertEqual(result["summary"]["unmatched"], 5)
            self.assertEqual(len(result["header_errors"]), 2)

    def test_count_mismatch_is_flagged(self):
        with tempfile.TemporaryDirectory() as temp:
            pdf = Path(temp) / "synthetic.pdf"
            make_pdf(pdf, count_label=6)
            result = extract(pdf)
            self.assertFalse(result["summary"]["automatic_checks_passed"])
            self.assertEqual(result["summary"]["reported_seat_count"], 6)
            self.assertEqual(result["summary"]["matched"], 5)

    def test_multi_page_pdf_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            pdf = Path(temp) / "synthetic.pdf"
            make_pdf(pdf, pages=2)
            with self.assertRaisesRegex(ValueError, "one-page plan"):
                extract(pdf)


if __name__ == "__main__":
    unittest.main()
