# PDF Anonymizer

A web application that replaces sensitive personal data (PII) in PDF documents with realistic fake values while preserving the original layout.

**Live Demo:** https://pdf---anonymizer-rutwhuxacs6yfkjjauyv6u.streamlit.app

## What it does

Upload a PDF containing sensitive information — names, phone numbers, emails, TC ID numbers, IBANs, student IDs, company names, or signatures — and the tool will:

1. Extract the text layout from the PDF
2. Detect all PII using regex and NER rules
3. Replace each item with a realistic fake value (Turkish locale)
4. Reconstruct the PDF with the same fonts, sizes, and positioning

## Team

| Person | Module | Responsibility |
|--------|--------|----------------|
| Aysel | Part 1 — PDF Extractor | Text and layout extraction, OCR for scanned PDFs |
| Can | Part 2 — PII Detector | Regex + NER detection of sensitive fields |
| Sami | Part 3 — Fake Data Generator | Realistic fake value generation (Faker, tr_TR) |
| Mehmet | Part 4 — PDF Reconstructor | Redaction and fake text insertion via PyMuPDF |

## Usage

### Web UI (recommended)

Visit the live app: https://pdf---anonymizer-rutwhuxacs6yfkjjauyv6u.streamlit.app

Upload a PDF, click **Anonymize PDF**, then download the result.

### Command line

```bash
pip install -r requirements.txt
python pipeline.py input.pdf -o output.pdf
```

### Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Supported PII Types

| Type | Example |
|------|---------|
| Person name | Ahmet Yilmaz |
| Phone number | +90 532 123 45 67 |
| Email address | ahmet@example.com |
| TC ID (Turkish national ID) | 12345678950 |
| IBAN | TR33 0006 1005 1978 6457 84 |
| Student ID | 20210123456 |
| Company name | ABC Teknoloji A.S. |
| Signature | (image replaced with generated signature) |

## Project Structure

```
PDF---Anonymizer/
├── app.py                  # Streamlit web UI
├── pipeline.py             # Full pipeline (CLI)
├── Dockerfile              # Coolify / Docker deployment
├── requirements.txt
├── extractor/              # Part 1 — PDF text extraction
├── extractor/pii_detector.py  # Part 2 — PII detection
├── fake_generator/         # Part 3 — Fake data generation
├── reconstructor/          # Part 4 — PDF reconstruction
└── test_data/              # Sample PDFs and JSON files
```
