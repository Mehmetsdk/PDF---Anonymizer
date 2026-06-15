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

    assert "PERSON_NAME" in types
    assert "EMAIL" in types
    assert "PHONE" in types
    assert "TC_ID" in types
    assert "STUDENT_INDEX" in types
    assert "ORGANIZATION" in types
    assert "SIGNATURE_FIELD" in types


def test_sample_newsletter_has_no_false_positive_regex_pii():
    data = json.loads((ROOT / "extractor" / "sample_output.json").read_text(encoding="utf-8"))
    result = detect_pii(data)
    assert result["detections"] == []
