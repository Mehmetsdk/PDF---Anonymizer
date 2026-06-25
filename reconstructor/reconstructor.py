import fitz  # PyMuPDF
import json
import os
import sys
from pathlib import Path
from signature_gen import generate_signature_png

# Unicode-capable font for Turkish characters (Ş Ğ İ Ö Ü Ç ş ğ ı ö ü ç)
_UNICODE_FONT_PATHS = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\calibri.ttf",
    r"C:\Windows\Fonts\tahoma.ttf",
    r"C:\Windows\Fonts\verdana.ttf",
]
_UNICODE_FONT = next((p for p in _UNICODE_FONT_PATHS if os.path.exists(p)), None)


def int_to_rgb(color_int):
    r = ((color_int >> 16) & 0xFF) / 255.0
    g = ((color_int >> 8) & 0xFF) / 255.0
    b = (color_int & 0xFF) / 255.0
    return (r, g, b)


def reconstruct_pdf(original_pdf_path, anonymization_map_path, output_path):
    with open(anonymization_map_path, "r", encoding="utf-8") as f:
        redactions = json.load(f)

    doc = fitz.open(original_pdf_path)

    by_page = {}
    for r in redactions:
        page_idx = r["page"] - 1  # extractor uses 1-indexed pages
        by_page.setdefault(page_idx, []).append(r)

    for page_idx, page_redactions in by_page.items():
        page = doc[page_idx]

        # Collect background color for each bbox before redacting
        bg_colors = {}
        for r in page_redactions:
            bbox = fitz.Rect(r["bbox"])
            bg_colors[id(r)] = _sample_background_color(page, bbox)

        # Add redaction annotations and apply (removes original text/graphics)
        for r in page_redactions:
            bbox = fitz.Rect(r["bbox"])
            # Expand bbox slightly horizontally to catch edge characters
            redact_bbox = bbox + (-4, 0, 4, 0)
            fill = bg_colors[id(r)]
            page.add_redact_annot(redact_bbox, fill=fill)
        page.apply_redactions()

        # Insert fake content at each redacted area
        for r in page_redactions:
            bbox = fitz.Rect(r["bbox"])
            if r.get("is_signature"):
                _insert_signature(page, bbox, r.get("fake_text", ""))
            else:
                _insert_text(page, bbox, r)

    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    print(f"Anonymized PDF saved to: {output_path}")


def _sample_background_color(page, bbox):
    """Sample the dominant color just outside the text bbox to use as fill."""
    # Slightly expand the rect and render a tiny pixmap to get bg color
    sample_rect = fitz.Rect(bbox.x0, bbox.y0, bbox.x0 + 2, bbox.y0 + 2)
    clip = sample_rect & page.rect
    if clip.is_empty:
        return (1, 1, 1)  # default white
    pix = page.get_pixmap(clip=clip, matrix=fitz.Matrix(1, 1))
    if pix.n < 3:
        return (1, 1, 1)
    samples = pix.samples
    r, g, b = samples[0] / 255.0, samples[1] / 255.0, samples[2] / 255.0
    return (r, g, b)


def _insert_text(page, bbox, redaction):
    color = int_to_rgb(redaction.get("color", 0))
    size = redaction.get("size", 11)
    fake_text = redaction["fake_text"]

    # Extend bbox to the right page margin so fake text always has room
    page_width = page.rect.width
    insert_bbox = fitz.Rect(bbox.x0, bbox.y0, min(page_width - 30, max(bbox.x1, bbox.x0 + 200)), bbox.y1)

    for font_size in [size, size * 0.9, size * 0.8, size * 0.7, size * 0.6]:
        kwargs = dict(fontsize=font_size, color=color, align=fitz.TEXT_ALIGN_LEFT)
        if _UNICODE_FONT:
            kwargs["fontname"] = "unicode_font"
            kwargs["fontfile"] = _UNICODE_FONT
        result = page.insert_textbox(insert_bbox, fake_text, **kwargs)
        if result >= 0:
            break


def _insert_signature(page, bbox, fake_name):
    sig_path = generate_signature_png(fake_name, int(bbox.width), int(bbox.height))
    page.insert_image(bbox, filename=sig_path)
    Path(sig_path).unlink(missing_ok=True)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python reconstructor.py <original.pdf> <anonymization_map.json> <output.pdf>")
        sys.exit(1)
    reconstruct_pdf(sys.argv[1], sys.argv[2], sys.argv[3])
