# PDF Anonymizer — Fake Data Generator (Person 3)

This module generates realistic fake replacement values for personally identifiable information (PII) detected in PDF documents. It is the bridge between **Person 2 (PII Detection)** and **Person 4 (PDF Reconstruction)**.

## Purpose

The Fake Data Generator:

- Reads `pii_output.json` produced by Person 2
- Creates deterministic, format-preserving fake values for each PII type
- Writes `fake_data_output.json` for Person 4 to apply during PDF reconstruction

The same original value always maps to the same fake value (e.g. `Mehmet Yılmaz` → `Ahmet Kaya` everywhere in the document).

## Installation

Requires Python 3.11+.

```bash
pip install -r requirements.txt
```

## Usage

```bash
python fake_data_generator.py pii_output.json -o fake_data_output.json
```

| Argument | Description |
|----------|-------------|
| `input` | Path to `pii_output.json` from Person 2 |
| `-o`, `--output` | Output path (default: `fake_data_output.json`) |

### Programmatic use

```python
from pathlib import Path
from fake_data_generator import generate_fake_data

mapping = generate_fake_data(
    Path("pii_output.json"),
    Path("fake_data_output.json"),
)
```

## Supported PII Types

| Type | Replacement strategy |
|------|---------------------|
| `PERSON` | Turkish name via Faker (`tr_TR`) |
| `ORGANIZATION` | Company name via Faker |
| `EMAIL` | Realistic email, structure preserved when possible |
| `PHONE` | Turkish phone number, separators preserved |
| `TURKISH_ID` | Valid-looking 11-digit TC Kimlik No |
| `IBAN` | Valid-looking Turkish IBAN, formatting preserved |
| `STUDENT_ID` | Same-length numeric string |
| `SIGNATURE` | `"Generated Signature"` + metadata for future generation |

## Example Input

`pii_output.json` from Person 2 (see `test_data/sample_pii.json`):

```json
{
  "detections": [
    {
      "page": 1,
      "type": "PERSON",
      "text": "Mehmet Yılmaz",
      "bbox": [100, 120, 250, 140]
    },
    {
      "page": 1,
      "type": "PHONE",
      "text": "+90 532 111 22 33",
      "bbox": [100, 240, 280, 260]
    }
  ]
}
```

The loader also accepts `original_text` instead of `text`, or a top-level list of detections.

## Example Output

`fake_data_output.json`:

```json
{
  "replacements": [
    {
      "page": 1,
      "type": "PERSON",
      "original_text": "Mehmet Yılmaz",
      "fake_text": "Ahmet Kaya",
      "bbox": [100, 120, 250, 140]
    },
    {
      "page": 1,
      "type": "PHONE",
      "original_text": "+90 532 111 22 33",
      "fake_text": "+90 545 888 77 66",
      "bbox": [100, 240, 280, 260]
    }
  ]
}
```

> Note: Actual `fake_text` values are deterministic but depend on the hashing/Faker seed logic. Run the generator on `test_data/sample_pii.json` to produce the bundled `sample_fake_output.json`.

## Testing

```bash
pytest
```

Tests cover:

- Deterministic mapping (same input → same output)
- Format preservation (phone, IBAN, student ID, Turkish ID)
- Output schema validation

## Project Structure

```
Task 3/
├── fake_data_generator.py      # Main module + CLI
├── requirements.txt
├── README.md
├── test_fake_data_generator.py
└── test_data/
    ├── sample_pii.json         # Example Person 2 output
    └── sample_fake_output.json # Example Person 3 output
```

## Integration

| Component | Input | Output |
|-----------|-------|--------|
| Person 2 | PDF / `output.json` | `pii_output.json` |
| **Person 3 (this module)** | `pii_output.json` | `fake_data_output.json` |
| Person 4 | `fake_data_output.json` + original PDF | Anonymized PDF |
