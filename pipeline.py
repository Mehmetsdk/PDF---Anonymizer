"""
PDF Anonymizer — Full Pipeline
Chains all 4 modules: extract → detect PII → generate fakes → reconstruct
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "extractor"))
sys.path.insert(0, str(ROOT / "fake_generator"))
sys.path.insert(0, str(ROOT / "reconstructor"))

from pdf_extractor import extract_text_with_layout, is_scanned_pdf, ocr_pdf  # Person 1
from pii_detector import detect_pii                                           # Person 2
from fake_data_generator import build_replacements                            # Person 3
from reconstructor import reconstruct_pdf                                     # Person 4 (us)


def _build_anonymization_map(replacements, detections):
    """
    Merge fake replacements (Person 3) with style info (Person 2).
    Person 3 output doesn't carry font/size/color — we pull them from
    Person 2's detections so the reconstructor can preserve visual style.
    """
    lookup = {}
    for d in detections:
        key = (d.get("page"), str(d.get("original_text", "")).strip())
        lookup[key] = d

    result = []
    for r in replacements:
        key = (r.get("page"), str(r.get("original_text", "")).strip())
        det = lookup.get(key, {})
        pii_type = str(r.get("type", ""))
        result.append({
            "page": r["page"],
            "bbox": r["bbox"],
            "original_text": r["original_text"],
            "fake_text": r["fake_text"],
            "pii_type": pii_type,
            "font": det.get("font"),
            "size": det.get("size"),
            "color": det.get("color", 0),
            "is_handwritten": pii_type == "HANDWRITING_FIELD",
            "is_signature": pii_type in ("SIGNATURE", "SIGNATURE_FIELD", "SIGNATURE_IMAGE"),
        })
    return result


def run_pipeline(
    pdf_path: Path,
    output_path: Path,
    work_dir: Path,
    enable_ner: bool = False,
):
    work_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Extract layout ──────────────────────────────────────────────
    print("[1/4] Extracting layout from PDF...")
    if is_scanned_pdf(str(pdf_path)):
        print("      Scanned PDF detected — running OCR...")
        layout = ocr_pdf(str(pdf_path))
    else:
        layout = extract_text_with_layout(str(pdf_path))

    layout_path = work_dir / "layout.json"
    layout_path.write_text(
        json.dumps(layout, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"      {sum(len(p['blocks']) for p in layout)} text blocks saved → {layout_path}")

    # ── Step 2: Detect PII ─────────────────────────────────────────────────
    print("[2/4] Detecting PII...")
    pii_result = detect_pii(layout, enable_ner=enable_ner)
    detections = pii_result["detections"]

    pii_path = work_dir / "pii_output.json"
    pii_path.write_text(
        json.dumps(pii_result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"      {len(detections)} detections found → {pii_path}")
    for pii_type, count in pii_result.get("summary", {}).items():
        print(f"        {pii_type}: {count}")

    if not detections:
        print("      No PII detected — output PDF will be a copy of the original.")
        import shutil
        shutil.copy2(pdf_path, output_path)
        return

    # ── Step 3: Generate fake data ─────────────────────────────────────────
    print("[3/4] Generating fake replacements...")
    replacements, mapping = build_replacements(detections)

    fake_path = work_dir / "fake_data_output.json"
    fake_path.write_text(
        json.dumps({"replacements": replacements}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"      {len(mapping)} unique fake values generated → {fake_path}")

    # ── Step 4: Reconstruct PDF ────────────────────────────────────────────
    print("[4/4] Reconstructing anonymized PDF...")
    anonymization_map = _build_anonymization_map(replacements, detections)

    anon_map_path = work_dir / "anonymization_map.json"
    anon_map_path.write_text(
        json.dumps(anonymization_map, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    reconstruct_pdf(str(pdf_path), str(anon_map_path), str(output_path))

    print(f"\nDone!")
    print(f"  Anonymized PDF   → {output_path}")
    print(f"  Intermediate files → {work_dir}/")


def main():
    parser = argparse.ArgumentParser(
        description="PDF Anonymizer — replaces sensitive data while preserving layout."
    )
    parser.add_argument("input_pdf", help="Path to the original PDF")
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output PDF path (default: <input>_anonymized.pdf)",
    )
    parser.add_argument(
        "--work-dir",
        default=None,
        help="Directory for intermediate JSON files (default: <input>_pipeline/)",
    )
    parser.add_argument(
        "--enable-ner",
        action="store_true",
        help="Enable spaCy NER for better person/org detection (requires spaCy model)",
    )
    args = parser.parse_args()

    pdf_path = Path(args.input_pdf)
    if not pdf_path.exists():
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)

    output_path = (
        Path(args.output)
        if args.output
        else pdf_path.parent / f"{pdf_path.stem}_anonymized.pdf"
    )
    work_dir = (
        Path(args.work_dir)
        if args.work_dir
        else pdf_path.parent / f"{pdf_path.stem}_pipeline"
    )

    run_pipeline(pdf_path, output_path, work_dir, enable_ner=args.enable_ner)


if __name__ == "__main__":
    main()
