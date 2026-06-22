"""
Person 2 - PII Detection module for PDF Anonymizer

Input:
    JSON produced by extractor/pdf-extractor.py
    A list of pages. Each page has blocks with text, bbox, font, size, color.

Output:
    JSON with detected sensitive fields and their PDF coordinates.

Run:
    python pii_detector.py sample_output.json -o pii_output.json
    python pii_detector.py sample_output.json -o pii_output.json --enable-ner
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

BBox = List[float]
Page = Dict[str, Any]
Block = Dict[str, Any]
Detection = Dict[str, Any]

# Shared PII type names used by Person 2 and Person 3.
# Keep these values aligned with the fake-data generation module.
PII_PERSON = "PERSON"
PII_TURKISH_ID = "TURKISH_ID"
PII_STUDENT_ID = "STUDENT_ID"
PII_SIGNATURE = "SIGNATURE"


@dataclass(frozen=True)
class RegexRule:
    name: str
    pii_type: str
    pattern: re.Pattern
    confidence: float
    method: str = "regex"
    group: int = 0
    validator: Optional[Callable[[str], bool]] = None


# -----------------------------
# Small geometry helpers
# -----------------------------

def _to_bbox(value: Any) -> Optional[BBox]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        x0, y0, x1, y1 = [float(v) for v in value]
    except (TypeError, ValueError):
        return None
    return [x0, y0, x1, y1]


def union_bbox(boxes: Iterable[BBox]) -> BBox:
    boxes = list(boxes)
    return [
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    ]


def bbox_iou(a: BBox, b: BBox) -> float:
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    denom = area_a + area_b - inter
    return inter / denom if denom else 0.0


def estimate_sub_bbox(block: Block, start: int, end: int) -> Optional[BBox]:
    """Estimate bbox for substring inside one extracted text block.

    PyMuPDF gives span-level bboxes, not per-character bboxes. For regex matches
    inside a span, this proportional estimate is good enough for anonymization
    redaction/replacement.
    """
    text = str(block.get("text", ""))
    bbox = _to_bbox(block.get("bbox"))
    if bbox is None:
        return None

    if not text:
        return bbox

    text_len = max(len(text), 1)
    start = max(0, min(start, text_len))
    end = max(start, min(end, text_len))

    x0, y0, x1, y1 = bbox
    width = x1 - x0
    sx = x0 + width * (start / text_len)
    ex = x0 + width * (end / text_len)
    return [sx, y0, ex, y1]


# -----------------------------
# Line grouping / span mapping
# -----------------------------

def group_blocks_into_lines(page: Page, y_tolerance: float = 4.0) -> List[Dict[str, Any]]:
    """Group PDF text blocks into visual lines.

    The extractor currently returns PyMuPDF spans. A value can be split across
    multiple spans, e.g. bold label + normal value: "Name:" + "Can Koksal".
    Line grouping lets Person 2 detect those cases while still mapping the match
    back to coordinates.
    """
    raw_blocks = page.get("blocks", []) or []
    blocks: List[Block] = []

    for block in raw_blocks:
        text = str(block.get("text", ""))
        bbox = _to_bbox(block.get("bbox"))
        if text.strip() and bbox:
            copied = dict(block)
            copied["bbox"] = bbox
            blocks.append(copied)

    blocks.sort(key=lambda b: ((_to_bbox(b.get("bbox")) or [0, 0, 0, 0])[1],
                               (_to_bbox(b.get("bbox")) or [0, 0, 0, 0])[0]))

    groups: List[List[Block]] = []
    centers: List[float] = []

    for block in blocks:
        bbox = _to_bbox(block.get("bbox"))
        if not bbox:
            continue
        cy = (bbox[1] + bbox[3]) / 2

        matched_idx = None
        for idx, center in enumerate(centers):
            if abs(cy - center) <= y_tolerance:
                matched_idx = idx
                break

        if matched_idx is None:
            groups.append([block])
            centers.append(cy)
        else:
            groups[matched_idx].append(block)
            centers[matched_idx] = sum(((_to_bbox(b.get("bbox")) or [0, 0, 0, 0])[1] +
                                        (_to_bbox(b.get("bbox")) or [0, 0, 0, 0])[3]) / 2
                                       for b in groups[matched_idx]) / len(groups[matched_idx])

    lines: List[Dict[str, Any]] = []
    for group in groups:
        group.sort(key=lambda b: (_to_bbox(b.get("bbox")) or [0, 0, 0, 0])[0])
        text_parts: List[str] = []
        segments: List[Dict[str, Any]] = []
        cursor = 0

        for block in group:
            text = str(block.get("text", ""))
            if text_parts:
                text_parts.append(" ")
                cursor += 1
            start = cursor
            text_parts.append(text)
            cursor += len(text)
            end = cursor
            segments.append({"block": block, "start": start, "end": end})

        line_text = "".join(text_parts)
        line_bbox = union_bbox([_to_bbox(b.get("bbox")) for b in group if _to_bbox(b.get("bbox"))])
        lines.append({"text": line_text, "segments": segments, "bbox": line_bbox})

    return lines


def bbox_for_line_span(line: Dict[str, Any], start: int, end: int) -> Optional[BBox]:
    boxes: List[BBox] = []
    for segment in line.get("segments", []):
        seg_start, seg_end = int(segment["start"]), int(segment["end"])
        if end <= seg_start or start >= seg_end:
            continue

        local_start = max(start, seg_start) - seg_start
        local_end = min(end, seg_end) - seg_start
        box = estimate_sub_bbox(segment["block"], local_start, local_end)
        if box:
            boxes.append(box)

    return union_bbox(boxes) if boxes else None


# -----------------------------
# Validators and normalizers
# -----------------------------

def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def only_digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def is_valid_turkish_tc_id(value: str) -> bool:
    digits = only_digits(value)
    if len(digits) != 11 or digits[0] == "0" or len(set(digits)) == 1:
        return False

    nums = [int(d) for d in digits]
    d10 = ((sum(nums[0:9:2]) * 7) - sum(nums[1:8:2])) % 10
    d11 = sum(nums[:10]) % 10
    return nums[9] == d10 and nums[10] == d11


def valid_phone(value: str) -> bool:
    digits = only_digits(value)
    if digits.startswith("90"):
        digits = digits[2:]
    if digits.startswith("0"):
        digits = digits[1:]
    return len(digits) == 10 and digits[0] in "2345"


def clean_entity_text(text: str) -> str:
    return normalize_spaces(text.strip(" \t\n\r:;-–—,."))


# -----------------------------
# Regex and heuristic rules
# -----------------------------

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?90[\s.\-/]*)?(?:0?[\s.\-/]*)?"
    r"(?:\(?[2-5]\d{2}\)?[\s.\-/]*)"
    r"\d{3}[\s.\-/]*\d{2}[\s.\-/]*\d{2}(?!\d)"
)

TC_RE = re.compile(r"(?<!\d)[1-9]\d{10}(?!\d)")

IBAN_TR_RE = re.compile(r"\bTR\d{2}(?:[\s\-]?\d{4}){5}[\s\-]?\d{2}\b", re.IGNORECASE)

STUDENT_INDEX_CONTEXT_RE = re.compile(
    r"(?i)\b(?:index|student\s*(?:id|no\.?|number)|öğrenci\s*(?:no\.?|numarası|numarasi)|"
    r"okul\s*no\.?|school\s*no\.?|album\s*no\.?|matriculation\s*no\.?)"
    r"\s*[:#\-–]?\s*([A-Z0-9][A-Z0-9\-/]{3,24})\b"
)

PERSON_LABEL_RE = re.compile(
    r"(?i)\b(?:full\s*name|name\s*surname|name|ad\s*soyad|ad[ıi]?\s*soyad[ıi]?|isim\s*soyisim|isim)"
    r"\s*[:\-–]\s*([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü'’\-]+(?:\s+[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü'’\-]+){1,3})"
)

ORG_LABEL_RE = re.compile(
    r"(?i)\b(?:organization|organisation|company|institution|university|school|kurum|şirket|sirket|üniversite|universite)"
    r"\s*[:\-–]\s*([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü0-9 &'’.,\-]{2,80})"
)

# A standalone organisation suffix heuristic. Conservative on purpose.
ORG_SUFFIX_RE = re.compile(
    r"\b([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü0-9 &'’.,\-]{2,70}\s+"
    r"(?:A\.Ş\.|AS|AŞ|Ltd\.?|LLC|Inc\.?|University|Üniversitesi|Universitesi|College|Bankası|Bank))\b"
)

SIGNATURE_KEYWORD_RE = re.compile(r"(?i)\b(signature|signed\s*by|imza|ıslak\s*imza|islak\s*imza)\b")
HANDWRITING_KEYWORD_RE = re.compile(r"(?i)\b(handwriting|handwritten|el\s*yazısı|el\s*yazisi)\b")

REGEX_RULES: List[RegexRule] = [
    RegexRule("email", "EMAIL", EMAIL_RE, 0.99),
    RegexRule("phone", "PHONE", PHONE_RE, 0.92, validator=valid_phone),
    RegexRule("turkish_tc_id", PII_TURKISH_ID, TC_RE, 0.98, validator=is_valid_turkish_tc_id),
    RegexRule("iban_tr", "IBAN", IBAN_TR_RE, 0.97),
    RegexRule("student_index_context", PII_STUDENT_ID, STUDENT_INDEX_CONTEXT_RE, 0.88, group=1),
]

HEURISTIC_RULES: List[RegexRule] = [
    RegexRule("person_label", PII_PERSON, PERSON_LABEL_RE, 0.76, method="label_heuristic", group=1),
    RegexRule("organization_label", "ORGANIZATION", ORG_LABEL_RE, 0.73, method="label_heuristic", group=1),
    RegexRule("organization_suffix", "ORGANIZATION", ORG_SUFFIX_RE, 0.70, method="suffix_heuristic", group=1),
]


# -----------------------------
# Detection builders
# -----------------------------

def make_detection(
    *,
    page_no: int,
    pii_type: str,
    original_text: str,
    bbox: BBox,
    confidence: float,
    method: str,
    rule: str,
    font: Optional[str] = None,
    size: Optional[float] = None,
    color: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Detection:
    item: Detection = {
        "page": page_no,
        "type": pii_type,
        "original_text": original_text,
        "bbox": [round(float(v), 2) for v in bbox],
        "confidence": round(float(confidence), 3),
        "method": method,
        "rule": rule,
    }
    if font is not None:
        item["font"] = font
    if size is not None:
        try:
            item["size"] = round(float(size), 2)
        except (TypeError, ValueError):
            pass
    if color is not None:
        item["color"] = color
    if extra:
        item.update(extra)
    return item


def style_for_span(line: Dict[str, Any], start: int, end: int) -> Tuple[Optional[str], Optional[float], Optional[int]]:
    # Use the style of the segment with the largest overlap.
    best = None
    best_overlap = 0
    for segment in line.get("segments", []):
        seg_start, seg_end = int(segment["start"]), int(segment["end"])
        overlap = max(0, min(end, seg_end) - max(start, seg_start))
        if overlap > best_overlap:
            best_overlap = overlap
            best = segment.get("block")
    if not best:
        return None, None, None
    return best.get("font"), best.get("size"), best.get("color")


def detect_with_rules(page_no: int, lines: List[Dict[str, Any]], rules: List[RegexRule]) -> List[Detection]:
    detections: List[Detection] = []

    for line in lines:
        line_text = line.get("text", "")
        if not line_text.strip():
            continue

        for rule in rules:
            for match in rule.pattern.finditer(line_text):
                try:
                    raw_value = match.group(rule.group)
                    start, end = match.span(rule.group)
                except IndexError:
                    continue

                value = clean_entity_text(raw_value)
                if not value:
                    continue

                if rule.validator and not rule.validator(value):
                    continue

                bbox = bbox_for_line_span(line, start, end)
                if not bbox:
                    continue

                font, size, color = style_for_span(line, start, end)
                detections.append(make_detection(
                    page_no=page_no,
                    pii_type=rule.pii_type,
                    original_text=value,
                    bbox=bbox,
                    confidence=rule.confidence,
                    method=rule.method,
                    rule=rule.name,
                    font=font,
                    color=color,
                    size=size,
                ))

    return detections


def expanded_field_bbox(page: Page, label_bbox: BBox, mode: str) -> BBox:
    """Estimate the fill/signature area next to or under a label.

    For a text label like "Signature:" there may be no value text to replace.
    This gives Person 4 a practical target region. It is intentionally marked
    as heuristic with lower confidence.
    """
    page_width = float(page.get("width", 595) or 595)
    page_height = float(page.get("height", 842) or 842)
    x0, y0, x1, y1 = label_bbox

    if x1 < page_width * 0.70:
        target = [x1 + 6, max(0, y0 - 8), min(page_width - 24, x1 + 220), min(page_height - 24, y1 + 36)]
    else:
        target = [x0, y1 + 4, min(page_width - 24, x0 + 240), min(page_height - 24, y1 + 56)]

    if mode == "handwriting":
        target[3] = min(page_height - 24, target[3] + 20)

    return [round(float(v), 2) for v in target]


def detect_signature_and_handwriting_fields(page: Page, page_no: int, lines: List[Dict[str, Any]]) -> List[Detection]:
    detections: List[Detection] = []

    for line in lines:
        text = line.get("text", "")
        for regex, pii_type, rule_name, mode, confidence in [
            (SIGNATURE_KEYWORD_RE, PII_SIGNATURE, "signature_keyword", "signature", 0.66),
            (HANDWRITING_KEYWORD_RE, "HANDWRITING_FIELD", "handwriting_keyword", "handwriting", 0.62),
        ]:
            for match in regex.finditer(text):
                label_bbox = bbox_for_line_span(line, match.start(), match.end())
                if not label_bbox:
                    continue
                target_bbox = expanded_field_bbox(page, label_bbox, mode)
                detections.append(make_detection(
                    page_no=page_no,
                    pii_type=pii_type,
                    original_text=clean_entity_text(match.group(0)),
                    bbox=target_bbox,
                    confidence=confidence,
                    method="field_heuristic",
                    rule=rule_name,
                    extra={"label_bbox": [round(float(v), 2) for v in label_bbox]},
                ))

    return detections


def detect_possible_signature_images(page: Page, page_no: int, text_detections: List[Detection]) -> List[Detection]:
    """Mark nearby images as possible signature images if a signature label exists.

    The extractor only exposes image bboxes, not image content. So this is only
    a helpful heuristic, not a true visual signature detector.
    """
    signature_labels = [d for d in text_detections if d.get("type") == PII_SIGNATURE]
    if not signature_labels:
        return []

    detections: List[Detection] = []
    for img in page.get("images", []) or []:
        bbox = _to_bbox(img.get("bbox"))
        if not bbox:
            continue

        # Nearby if centers are close vertically or if image overlaps a predicted signature field.
        should_mark = False
        for sig in signature_labels:
            sig_box = _to_bbox(sig.get("bbox"))
            if not sig_box:
                continue
            same_area = bbox_iou(bbox, sig_box) > 0.05
            vertical_close = abs(((bbox[1] + bbox[3]) / 2) - ((sig_box[1] + sig_box[3]) / 2)) < 80
            horizontal_close = bbox[0] <= sig_box[2] + 60 and bbox[2] >= sig_box[0] - 60
            if same_area or (vertical_close and horizontal_close):
                should_mark = True
                break

        if should_mark:
            detections.append(make_detection(
                page_no=page_no,
                pii_type="SIGNATURE_IMAGE",
                original_text="<image>",
                bbox=bbox,
                confidence=0.70,
                method="image_bbox_heuristic",
                rule="image_near_signature_label",
            ))

    return detections


# -----------------------------
# Optional spaCy NER
# -----------------------------

def load_spacy_pipeline(model_name: Optional[str] = None):
    try:
        import spacy  # type: ignore
    except ImportError:
        return None, "spaCy is not installed"

    candidates = [model_name] if model_name else [
        "tr_core_news_trf",
        "tr_core_news_lg",
        "tr_core_news_sm",
        "en_core_web_trf",
        "en_core_web_lg",
        "en_core_web_sm",
        "pl_core_news_lg",
        "pl_core_news_sm",
    ]

    errors = []
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return spacy.load(candidate), None
        except Exception as exc:  # pragma: no cover - depends on local models
            errors.append(f"{candidate}: {exc}")

    return None, "; ".join(errors) if errors else "No model name provided"


def map_spacy_label(label: str) -> Optional[str]:
    label = label.upper()
    if label in {"PERSON", "PER"}:
        return PII_PERSON
    if label in {"ORG", "ORGANIZATION"}:
        return "ORGANIZATION"
    if label in {"GPE", "LOC", "LOCATION"}:
        return "LOCATION"
    return None


def detect_with_spacy(page_no: int, lines: List[Dict[str, Any]], nlp: Any) -> List[Detection]:
    detections: List[Detection] = []
    for line in lines:
        text = line.get("text", "")
        if not text.strip():
            continue
        doc = nlp(text)
        for ent in doc.ents:
            pii_type = map_spacy_label(ent.label_)
            if not pii_type:
                continue
            value = clean_entity_text(ent.text)
            if len(value) < 2:
                continue

            bbox = bbox_for_line_span(line, int(ent.start_char), int(ent.end_char))
            if not bbox:
                continue

            font, size, color = style_for_span(line, int(ent.start_char), int(ent.end_char))
            detections.append(make_detection(
                page_no=page_no,
                pii_type=pii_type,
                original_text=value,
                bbox=bbox,
                confidence=0.82,
                method="spacy_ner",
                rule=f"spacy_{ent.label_}",
                font=font,
                color=color,
                size=size,
            ))
    return detections


# -----------------------------
# Deduplication and public API
# -----------------------------

def deduplicate(detections: List[Detection]) -> List[Detection]:
    """Remove duplicate detections while keeping the strongest one."""
    sorted_items = sorted(
        detections,
        key=lambda d: (d.get("page", 0), d.get("type", ""), -float(d.get("confidence", 0))),
    )

    kept: List[Detection] = []
    for item in sorted_items:
        item_box = _to_bbox(item.get("bbox"))
        if not item_box:
            continue

        duplicate_idx = None
        for idx, existing in enumerate(kept):
            existing_box = _to_bbox(existing.get("bbox"))
            if not existing_box:
                continue

            same_page = item.get("page") == existing.get("page")
            same_type = item.get("type") == existing.get("type")
            same_text = clean_entity_text(str(item.get("original_text", ""))).lower() == clean_entity_text(str(existing.get("original_text", ""))).lower()
            strong_overlap = bbox_iou(item_box, existing_box) > 0.55

            if same_page and same_type and (same_text or strong_overlap):
                duplicate_idx = idx
                break

        if duplicate_idx is None:
            kept.append(item)
        else:
            if float(item.get("confidence", 0)) > float(kept[duplicate_idx].get("confidence", 0)):
                kept[duplicate_idx] = item

    kept.sort(key=lambda d: (d.get("page", 0), (d.get("bbox") or [0, 0, 0, 0])[1], (d.get("bbox") or [0, 0, 0, 0])[0]))
    return kept


def summarize(detections: List[Detection]) -> Dict[str, int]:
    summary: Dict[str, int] = {}
    for detection in detections:
        key = str(detection.get("type", "UNKNOWN"))
        summary[key] = summary.get(key, 0) + 1
    return dict(sorted(summary.items()))


def detect_pii(
    layout_pages: List[Page],
    *,
    enable_ner: bool = False,
    spacy_model: Optional[str] = None,
    min_confidence: float = 0.0,
) -> Dict[str, Any]:
    nlp = None
    ner_status = "disabled"
    if enable_ner:
        nlp, error = load_spacy_pipeline(spacy_model)
        ner_status = "enabled" if nlp else f"unavailable: {error}"

    detections: List[Detection] = []

    for page in layout_pages:
        page_no = int(page.get("page", page.get("page_no", 0)) or 0)
        lines = group_blocks_into_lines(page)

        page_detections: List[Detection] = []
        page_detections.extend(detect_with_rules(page_no, lines, REGEX_RULES))
        page_detections.extend(detect_with_rules(page_no, lines, HEURISTIC_RULES))
        page_detections.extend(detect_signature_and_handwriting_fields(page, page_no, lines))

        if nlp is not None:
            page_detections.extend(detect_with_spacy(page_no, lines, nlp))

        page_detections.extend(detect_possible_signature_images(page, page_no, page_detections))
        detections.extend(page_detections)

    detections = deduplicate(detections)
    if min_confidence > 0:
        detections = [d for d in detections if float(d.get("confidence", 0)) >= min_confidence]

    return {
        "schema_version": "person2-pii-v1",
        "source": "Person 2 - PII Detection",
        "ner_status": ner_status,
        "detections": detections,
        "summary": summarize(detections),
    }


# -----------------------------
# CLI
# -----------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Detect PII from PDF extractor JSON output")
    parser.add_argument("input_json", help="Path to JSON produced by pdf-extractor.py")
    parser.add_argument("-o", "--output", default="pii_output.json", help="Output JSON path")
    parser.add_argument("--enable-ner", action="store_true", help="Enable optional spaCy NER if installed")
    parser.add_argument("--spacy-model", default=None, help="spaCy model name, e.g. en_core_web_sm")
    parser.add_argument("--min-confidence", type=float, default=0.0, help="Filter low confidence detections")
    args = parser.parse_args()

    input_path = Path(args.input_json)
    with input_path.open("r", encoding="utf-8") as f:
        layout_pages = json.load(f)

    if not isinstance(layout_pages, list):
        raise ValueError("Input JSON must be a list of page objects produced by pdf-extractor.py")

    result = detect_pii(
        layout_pages,
        enable_ner=args.enable_ner,
        spacy_model=args.spacy_model,
        min_confidence=args.min_confidence,
    )

    output_path = Path(args.output)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"PII output saved to: {output_path}")
    print(f"Total detections: {len(result['detections'])}")
    print(f"Summary: {result['summary']}")
    print(f"NER: {result['ner_status']}")


if __name__ == "__main__":
    main()
