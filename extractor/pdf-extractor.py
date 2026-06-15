import fitz  # PyMuPDF
import json
import sys
import io

try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


def extract_text_with_layout(pdf_path):
    doc = fitz.open(pdf_path)
    result = []

    for page_num, page in enumerate(doc):
        page_data = {
            "page": page_num + 1,
            "width": page.rect.width,
            "height": page.rect.height,
            "blocks": [],
            "images": []
        }

        text_dict = page.get_text("dict")

        for block in text_dict["blocks"]:
            if block["type"] == 0:
                for line in block["lines"]:
                    for span in line["spans"]:
                        page_data["blocks"].append({
                            "text": span["text"],
                            "bbox": span["bbox"],
                            "font": span["font"],
                            "size": round(span["size"], 2),
                            "color": span["color"],
                        })
            elif block["type"] == 1:
                page_data["images"].append({
                    "bbox": block["bbox"],
                    "width": block.get("width"),
                    "height": block.get("height"),
                })

        result.append(page_data)

    doc.close()
    return result


def is_scanned_pdf(pdf_path, text_threshold=20):
    doc = fitz.open(pdf_path)
    total_text_len = 0
    page_count = len(doc)

    for page in doc:
        total_text_len += len(page.get_text().strip())

    doc.close()
    avg_text_per_page = total_text_len / page_count if page_count else 0
    return avg_text_per_page < text_threshold


def ocr_pdf(pdf_path, dpi=300):
    if not OCR_AVAILABLE:
        print("ERROR: pytesseract/Pillow not installed. Run: pip3 install pytesseract pillow")
        sys.exit(1)

    doc = fitz.open(pdf_path)
    result = []
    zoom = dpi / 72

    for page_num, page in enumerate(doc):
        page_data = {
            "page": page_num + 1,
            "width": page.rect.width,
            "height": page.rect.height,
            "blocks": [],
            "images": []
        }

        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_bytes))

        ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

        n_boxes = len(ocr_data["text"])
        for i in range(n_boxes):
            word = ocr_data["text"][i].strip()
            if not word:
                continue

            x = ocr_data["left"][i] / zoom
            y = ocr_data["top"][i] / zoom
            w = ocr_data["width"][i] / zoom
            h = ocr_data["height"][i] / zoom

            page_data["blocks"].append({
                "text": word,
                "bbox": [x, y, x + w, y + h],
                "font": "OCR",
                "size": round(h, 2),
                "color": 0,
                "confidence": ocr_data["conf"][i],
            })

        result.append(page_data)

    doc.close()
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract.py <pdf_file>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    scanned = is_scanned_pdf(pdf_path)

    if scanned:
        print("This PDF appears to be scanned. Running OCR...")
        data = ocr_pdf(pdf_path)
    else:
        data = extract_text_with_layout(pdf_path)

    output_path = "output.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Output saved to: {output_path}")
    print(f"Total pages: {len(data)}")
    print(f"Mode: {'OCR' if scanned else 'native text extraction'}")