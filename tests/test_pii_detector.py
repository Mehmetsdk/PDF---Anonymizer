import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "extractor"))

from pii_detector import detect_pii  # noqa: E402


def test_detects_core_pii_from_mock_input():
    data = json.loads((ROOT / "extractor" / "mock_person2_input.json").read_text(encoding="utf-8"))
    result = detect_pii(data)
    types = {item["type"] for item in result["detections"]}

    assert "PERSON" in types
    assert "EMAIL" in types
    assert "PHONE" in types
    assert "TURKISH_ID" in types
    assert "STUDENT_ID" in types
    assert "ORGANIZATION" in types
    assert "SIGNATURE" in types


def test_plain_text_has_no_false_positive_regex_pii():
    data = [
        {
            "page": 1,
            "width": 595,
            "height": 842,
            "blocks": [
                {
                    "text": "Monthly newsletter with product updates and upcoming events.",
                    "bbox": [50, 80, 420, 95],
                    "font": "Arial",
                    "size": 11,
                    "color": 0,
                }
            ],
            "images": [],
        }
    ]

    result = detect_pii(data)
    assert result["detections"] == []


def test_uses_person3_shared_type_names():
    data = json.loads((ROOT / "extractor" / "mock_person2_input.json").read_text(encoding="utf-8"))
    result = detect_pii(data)
    types = {item["type"] for item in result["detections"]}

    assert {"PERSON", "TURKISH_ID", "STUDENT_ID", "SIGNATURE"}.issubset(types)
    assert not types.intersection({"PERSON_NAME", "TC_ID", "STUDENT_INDEX", "SIGNATURE_FIELD"})
