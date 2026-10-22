"""Read-only ACC inventory and evaluation using the unchanged baseline extractor."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import platform
import fitz
from PIL import Image, ImageOps, ImageDraw, __version__ as pillow_version
from extract_seats import extract, render_preview

BASE = Path(__file__).resolve().parent
OUTPUT = BASE / "output" / "acc-audit"
OUTPUT.mkdir(parents=True, exist_ok=True)
manifest = json.loads((BASE / "input/manifest.json").read_text(encoding="utf-8"))
summary = {"executed_at_utc": datetime.now(timezone.utc).isoformat(),
           "environment": {"python": platform.python_version(), "pymupdf": fitz.VersionBind, "pillow": pillow_version},
           "pdf_results": [], "image_results": [],
           "limits": ["Counts are integrity checks, not seat-level accuracy.",
                      "No metric venue coordinates are inferred.",
                      "Image OCR and OpenCV recognition performance is not measured."]}
previews = []
for record in manifest["files"]:
    source = Path(record["source_path"])
    copied = BASE / "input" / f"theatre-{record['theatre']}" / Path(record["copy_path"]).name
    assert hashlib.sha256(source.read_bytes()).hexdigest() == record["sha256"]
    assert hashlib.sha256(copied.read_bytes()).hexdigest() == record["sha256"]
    if copied.suffix.lower() == ".pdf":
        dest = OUTPUT / "theatre-1" / copied.stem
        dest.mkdir(parents=True, exist_ok=True)
        result = extract(copied)
        (dest / "seats.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        render_preview(copied, result, dest / "overlay.png")
        with fitz.open(copied) as doc:
            page = doc[0]
            words = page.get_text("words", sort=False)
            blocks = page.get_text("blocks", sort=False)
            vectors = page.get_drawings()
            (dest / "raw-layout.json").write_text(json.dumps({"words": words, "blocks": blocks,
                "coordinate_unit": "PDF points", "origin": "top-left", "physical_coordinates": False}, ensure_ascii=False, indent=2), encoding="utf-8")
            (dest / "text.txt").write_text(page.get_text(), encoding="utf-8")
            page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).save(dest / "page.png")
            stats = {"words": len(words), "text_blocks": len(blocks), "vector_drawings": len(vectors),
                     "embedded_images": len(page.get_images()), "page_size_pt": list(page.rect)[2:]}
        row = {"file": copied.name, "source_filename_seat_count": record["expected_count_from_filename"], "filename_seat_count": record.get("copy_filename_seat_count", record["expected_count_from_filename"]),
               **result["summary"], **stats,
               "block_counts": dict(Counter(s["block"] for s in result["seats"])),
               "unmatched_reasons": dict(Counter(s["reason"] for s in result["unmatched"])),
               "header_errors": result["header_errors"],
               "seat_token_coverage": result["summary"]["matched"] / result["summary"]["seat_tokens"] if result["summary"]["seat_tokens"] else None,
               "seat_level_ground_truth_evaluated": False}
        summary["pdf_results"].append(row)
        previews.append((copied.stem, dest / "overlay.png"))
    else:
        dest = OUTPUT / f"theatre-{record['theatre']}"
        dest.mkdir(parents=True, exist_ok=True)
        with Image.open(copied) as image:
            image.verify()
        with Image.open(copied) as image:
            row = {"file": copied.name, "format": image.format, "width_px": image.width, "height_px": image.height,
                   "mode": image.mode, "dpi_metadata": [float(v) for v in image.info["dpi"]] if image.info.get("dpi") else None,
                   "source_filename_seat_count": record["expected_count_from_filename"], "filename_seat_count": record.get("copy_filename_seat_count", record["expected_count_from_filename"]),
                   "ocr_run": False, "recognition_accuracy": None, "physical_scale_known": False}
            thumb = image.convert("RGB")
            thumb.thumbnail((1300, 1300))
            thumb.save(dest / "overview.png")
        with fitz.open(copied) as document:
            row["container_is_pdf"] = document.is_pdf
            row["direct_text_words"] = sum(len(page.get_text("words")) for page in document)
            row["direct_text_chars"] = sum(len(page.get_text()) for page in document)
        summary["image_results"].append(row)
for record in manifest["files"]:
    source = Path(record["source_path"])
    assert source.stat().st_mtime_ns == record["source_mtime_ns"]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == record["sha256"]
summary["originals_unchanged"] = True
summary["copy_hashes_verified"] = len(manifest["files"])
(OUTPUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
canvas = Image.new("RGB", (1500, 3 * 430), "#dddddd")
draw = ImageDraw.Draw(canvas)
for i, (label, path) in enumerate(previews):
    with Image.open(path) as image:
        image.thumbnail((490, 395))
        x, y = (i % 3) * 500, (i // 3) * 430
        canvas.paste(image, (x + (500-image.width)//2, y+25))
        draw.text((x+10, y+5), label, fill="black")
canvas.save(OUTPUT / "pdf-contact-sheet.png")
print(json.dumps(summary, ensure_ascii=True, indent=2))
