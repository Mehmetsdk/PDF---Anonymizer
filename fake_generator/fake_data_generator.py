"""
Fake Data Generator for PDF Anonymizer (Person 3).

Reads PII detections from pii_output.json and produces deterministic,
format-preserving replacement values in fake_data_output.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from faker import Faker

# Supported PII types from Person 2.
PII_TYPES = {
    "PERSON",
    "ORGANIZATION",
    "EMAIL",
    "PHONE",
    "TURKISH_ID",
    "IBAN",
    "STUDENT_ID",
    "SIGNATURE",
}

SIGNATURE_PLACEHOLDER = "Generated Signature"


def _seed_from_text(text: str) -> int:
    """Derive a stable integer seed from original text for deterministic output."""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _faker_for_text(text: str, locale: str = "tr_TR") -> Faker:
    """Return a Faker instance seeded from the original text."""
    fake = Faker(locale)
    fake.seed_instance(_seed_from_text(text))
    return fake


def _digit_at(seed: int, index: int, exclude_zero: bool = False) -> str:
    """Generate a deterministic digit for a given position."""
    value = (seed + index * 7919) % 10
    if exclude_zero and value == 0:
        value = 1
    return str(value)


def _generate_turkish_id(original: str) -> str:
    """
    Generate a valid-looking 11-digit Turkish ID (TC Kimlik No).

    Preserves non-digit separators from the original when present.
    """
    seed = _seed_from_text(original)
    digits = [_digit_at(seed, 0, exclude_zero=True)]
    for i in range(1, 9):
        digits.append(_digit_at(seed, i))
    odd_sum = sum(int(digits[i]) for i in range(0, 9, 2))
    even_sum = sum(int(digits[i]) for i in range(1, 8, 2))
    tenth = (odd_sum * 7 - even_sum) % 10
    digits.append(str(tenth))
    digits.append(str(sum(int(d) for d in digits) % 10))
    new_digits = "".join(digits)

    return _preserve_digit_structure(original, new_digits)


def _preserve_digit_structure(original: str, new_digits: str) -> str:
    """Map new digits onto the separator pattern of the original string."""
    digit_iter = iter(new_digits)
    result: list[str] = []
    for char in original:
        if char.isdigit():
            result.append(next(digit_iter, "0"))
        else:
            result.append(char)
    return "".join(result)


def _generate_student_id(original: str) -> str:
    """Generate a numeric replacement with the same length as the original."""
    seed = _seed_from_text(original)
    length = len(original)
    digits = []
    for i in range(length):
        # First digit may be non-zero if original started non-zero.
        exclude_zero = i == 0 and original[0].isdigit() and original[0] != "0"
        digits.append(_digit_at(seed, i, exclude_zero=exclude_zero))
    return "".join(digits)


def _generate_phone(original: str) -> str:
    """Generate a Turkish phone number while preserving separators and structure."""
    seed = _seed_from_text(original)
    digit_positions = [i for i, c in enumerate(original) if c.isdigit()]
    if not digit_positions:
        fake = _faker_for_text(original)
        return fake.phone_number()

    # Preserve Turkish country code (+90) when present.
    preserve_positions: set[int] = set()
    normalized = re.sub(r"[\s\-()]", "", original)
    if normalized.startswith("+90") and len(normalized) >= 3:
        plus_index = original.find("+")
        if plus_index != -1:
            for offset in range(1, 3):
                pos = plus_index + offset
                if pos < len(original) and original[pos] == "9" and offset == 1:
                    preserve_positions.add(pos)
                if pos < len(original) and original[pos] == "0" and offset == 2:
                    preserve_positions.add(pos)

    replaceable = [p for p in digit_positions if p not in preserve_positions]
    new_digits = [_digit_at(seed, i) for i in range(len(replaceable))]

    # Turkish mobile numbers start with 5 after the country code.
    if new_digits:
        new_digits[0] = "5"

    result = list(original)
    for pos, digit in zip(replaceable, new_digits):
        result[pos] = digit
    return "".join(result)


def _generate_iban(original: str) -> str:
    """Generate a valid-looking Turkish IBAN while preserving formatting."""
    seed = _seed_from_text(original)
    # Turkish IBAN: TR + 24 digits (26 characters without spaces).
    body_digits = "".join(_digit_at(seed, i) for i in range(24))
    new_iban = f"TR{body_digits}"

    return _preserve_iban_structure(original, new_iban)


def _preserve_iban_structure(original: str, new_iban: str) -> str:
    """Apply IBAN digit/letter values onto the original separator layout."""
    clean_new = re.sub(r"\s", "", new_iban.upper())
    char_iter = iter(clean_new)
    result: list[str] = []
    for char in original:
        if char.isalnum():
            result.append(next(char_iter, "0"))
        else:
            result.append(char)

    # Append any remaining characters if original had fewer slots.
    remainder = "".join(char_iter)
    if remainder and not any(c.isalnum() for c in original):
        result.append(remainder)
    return "".join(result)


def _generate_email(original: str) -> str:
    """Generate a realistic email, preserving local/domain structure when possible."""
    fake = _faker_for_text(original)
    generated = fake.email()

    if "@" not in original:
        return generated

    local, _, domain = original.partition("@")
    fake_local, _, fake_domain = generated.partition("@")

    # Keep similar local-part length and domain suffix pattern.
    if "." in domain:
        tld = domain.rsplit(".", 1)[-1]
        if len(tld) <= 3:
            fake_domain = fake_domain.rsplit(".", 1)[0] + "." + tld

    target_local_len = max(len(local), 3)
    if len(fake_local) > target_local_len:
        fake_local = fake_local[:target_local_len]
    elif len(fake_local) < target_local_len:
        fake_local = fake_local + "x" * (target_local_len - len(fake_local))

    return f"{fake_local}@{fake_domain}"


def _generate_person(original: str) -> str:
    """Generate a realistic Turkish person name."""
    fake = _faker_for_text(original)
    return fake.name()


_SENSITIVE_SURNAMES = {
    "öcalan", "ocalan", "pkk", "apocular",
}

_COMPANY_SUFFIXES = ["A.S.", "Ltd. Sti.", "Grup", "Holding", "Teknoloji", "Insaat", "Danismanlik"]
_COMPANY_PREFIXES = [
    "Anadolu", "Akdeniz", "Bogazici", "Karadeniz", "Toros", "Ege", "Marmara",
    "Yildiz", "Atlas", "Altin", "Günes", "Demir", "Celik", "Kartal", "Bahar",
]

def _generate_organization(original: str) -> str:
    """Generate a realistic company name, avoiding politically sensitive surnames."""
    fake = _faker_for_text(original)
    for attempt in range(10):
        candidate = fake.company()
        lower = candidate.lower()
        if not any(s in lower for s in _SENSITIVE_SURNAMES):
            return candidate
        # Reseed with a different offset and try again
        fake.seed_instance(_seed_from_text(original) + attempt + 1)
    # Fallback: build a safe name from controlled word lists
    seed = _seed_from_text(original)
    prefix = _COMPANY_PREFIXES[seed % len(_COMPANY_PREFIXES)]
    suffix = _COMPANY_SUFFIXES[(seed // len(_COMPANY_PREFIXES)) % len(_COMPANY_SUFFIXES)]
    return f"{prefix} {suffix}"


def _generate_signature(original: str) -> str:
    """Replace signatures with a placeholder (metadata added at replacement level)."""
    return SIGNATURE_PLACEHOLDER


def generate_fake_value(pii_type: str, original_text: str) -> str:
    """Generate a fake replacement value for a single PII detection."""
    generators = {
        "PERSON": _generate_person,
        "ORGANIZATION": _generate_organization,
        "EMAIL": _generate_email,
        "PHONE": _generate_phone,
        "TURKISH_ID": _generate_turkish_id,
        "IBAN": _generate_iban,
        "STUDENT_ID": _generate_student_id,
        "SIGNATURE": _generate_signature,
    }

    generator = generators.get(pii_type.upper())
    if generator is None:
        raise ValueError(f"Unsupported PII type: {pii_type}")

    return generator(original_text)


def _extract_original_text(detection: dict[str, Any]) -> str:
    """Read original text from Person 2 output (supports common field names)."""
    for key in ("original_text", "text", "value"):
        if key in detection and detection[key] is not None:
            return str(detection[key])
    raise ValueError(f"Detection missing text field: {detection}")


def build_replacements(
    detections: list[dict[str, Any]],
    mapping: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """
    Build replacement records from PII detections.

    Uses a mapping cache so the same original_text always gets the same fake_text.
    """
    if mapping is None:
        mapping = {}

    replacements: list[dict[str, Any]] = []

    for detection in detections:
        original_text = _extract_original_text(detection)
        pii_type = str(detection.get("type", "")).upper()

        if pii_type not in PII_TYPES:
            raise ValueError(f"Unsupported PII type: {pii_type}")

        if original_text not in mapping:
            mapping[original_text] = generate_fake_value(pii_type, original_text)

        replacement: dict[str, Any] = {
            "page": detection.get("page"),
            "type": pii_type,
            "original_text": original_text,
            "fake_text": mapping[original_text],
            "bbox": detection.get("bbox"),
        }

        if pii_type == "SIGNATURE":
            replacement["metadata"] = {
                "placeholder": True,
                "signature_generation": "pending",
                "original_length": len(original_text),
            }

        replacements.append(replacement)

    return replacements, mapping


def load_pii_input(path: Path) -> list[dict[str, Any]]:
    """Load PII detections from JSON file."""
    with path.open(encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("detections", "pii", "items", "results"):
            if key in data and isinstance(data[key], list):
                return data[key]
        if "replacements" in data and isinstance(data["replacements"], list):
            return data["replacements"]

    raise ValueError("Unsupported pii_output.json structure")


def save_fake_output(path: Path, replacements: list[dict[str, Any]]) -> None:
    """Write fake data output JSON."""
    output = {"replacements": replacements}
    with path.open("w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)


def generate_fake_data(
    input_path: Path,
    output_path: Path,
) -> dict[str, str]:
    """
    Main pipeline: read pii_output.json and write fake_data_output.json.

    Returns the mapping cache for testing or downstream use.
    """
    detections = load_pii_input(input_path)
    replacements, mapping = build_replacements(detections)
    save_fake_output(output_path, replacements)
    return mapping


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate fake replacement data for detected PII.",
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to pii_output.json from Person 2",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("fake_data_output.json"),
        help="Path for fake_data_output.json (default: fake_data_output.json)",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entry point."""
    args = parse_args()
    mapping = generate_fake_data(args.input, args.output)
    print(f"Generated {len(mapping)} unique fake values -> {args.output}")


if __name__ == "__main__":
    main()
