"""Tests for fake_data_generator module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fake_data_generator import (
    build_replacements,
    generate_fake_data,
    generate_fake_value,
    load_pii_input,
)

SAMPLE_PII = Path(__file__).parent / "test_data" / "sample_pii.json"
SAMPLE_OUTPUT = Path(__file__).parent / "test_data" / "sample_fake_output.json"

REQUIRED_REPLACEMENT_KEYS = {
    "page",
    "type",
    "original_text",
    "fake_text",
    "bbox",
}


@pytest.fixture
def sample_detections() -> list[dict]:
    return load_pii_input(SAMPLE_PII)


def test_deterministic_mapping_same_run(sample_detections: list[dict]) -> None:
    """Same original text must map to the same fake value within one run."""
    replacements, mapping = build_replacements(sample_detections)

    mehmet_entries = [r for r in replacements if r["original_text"] == "Mehmet Yılmaz"]
    assert len(mehmet_entries) == 2
    assert mehmet_entries[0]["fake_text"] == mehmet_entries[1]["fake_text"]
    assert mapping["Mehmet Yılmaz"] == mehmet_entries[0]["fake_text"]


def test_deterministic_mapping_across_runs() -> None:
    """Same original text must produce the same fake value on repeated calls."""
    first = generate_fake_value("PERSON", "Mehmet Yılmaz")
    second = generate_fake_value("PERSON", "Mehmet Yılmaz")
    assert first == second


def test_format_preservation_phone() -> None:
    original = "+90 532 111 22 33"
    fake = generate_fake_value("PHONE", original)

    assert fake.startswith("+90")
    assert fake[3] == " "
    assert fake[7] == " "
    assert fake[11] == " "
    assert fake[14] == " "
    assert sum(c.isdigit() for c in original) == sum(c.isdigit() for c in fake)


def test_format_preservation_iban() -> None:
    original = "TR33 0006 1005 1978 6457 8413 26"
    fake = generate_fake_value("IBAN", original)

    assert fake[:2] == "TR"
    for orig_char, fake_char in zip(original, fake):
        if not orig_char.isalnum():
            assert fake_char == orig_char


def test_format_preservation_student_id() -> None:
    original = "2020123456"
    fake = generate_fake_value("STUDENT_ID", original)

    assert len(fake) == len(original)
    assert fake.isdigit()


def test_format_preservation_turkish_id() -> None:
    original = "12345678901"
    fake = generate_fake_value("TURKISH_ID", original)

    assert len(fake) == 11
    assert fake.isdigit()


def test_signature_placeholder_and_metadata(sample_detections: list[dict]) -> None:
    replacements, _ = build_replacements(sample_detections)
    signature = next(r for r in replacements if r["type"] == "SIGNATURE")

    assert signature["fake_text"] == "Generated Signature"
    assert signature["metadata"]["placeholder"] is True
    assert signature["metadata"]["signature_generation"] == "pending"


def test_output_schema_validation(sample_detections: list[dict]) -> None:
    replacements, _ = build_replacements(sample_detections)

    assert isinstance(replacements, list)
    assert len(replacements) == len(sample_detections)

    for item in replacements:
        assert REQUIRED_REPLACEMENT_KEYS.issubset(item.keys())
        assert item["type"] in {
            "PERSON",
            "ORGANIZATION",
            "EMAIL",
            "PHONE",
            "TURKISH_ID",
            "IBAN",
            "STUDENT_ID",
            "SIGNATURE",
        }
        assert isinstance(item["original_text"], str)
        assert isinstance(item["fake_text"], str)
        assert item["fake_text"] != ""


def test_cli_pipeline(tmp_path: Path) -> None:
    output_path = tmp_path / "fake_data_output.json"
    mapping = generate_fake_data(SAMPLE_PII, output_path)

    assert output_path.exists()
    with output_path.open(encoding="utf-8") as file:
        data = json.load(file)

    assert "replacements" in data
    assert len(data["replacements"]) == 9
    assert len(mapping) == 8  # Mehmet Yılmaz appears twice but maps once


def test_sample_fake_output_matches_schema() -> None:
    """Bundled sample output must follow the expected schema."""
    with SAMPLE_OUTPUT.open(encoding="utf-8") as file:
        data = json.load(file)

    assert "replacements" in data
    for item in data["replacements"]:
        assert REQUIRED_REPLACEMENT_KEYS.issubset(item.keys())
