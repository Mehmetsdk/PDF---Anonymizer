# PDF Extractor (Person 1)

Extracts text, layout, and image information from PDF files. Automatically falls back to OCR (Tesseract) for scanned PDFs.

## Setup

```bash
pip3 install -r requirements.txt
```

Tesseract OCR also needs to be installed at the system level:

- **macOS:** `brew install tesseract`
- **Windows:** `choco install tesseract` (or download the installer from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki))
- **Linux (Debian/Ubuntu):** `sudo apt install tesseract-ocr`

## Usage

```bash
python3 pdf_extractor.py <pdf_file> -o <output_file>
```

Example:

```bash
python3 pdf_extractor.py samplepdf.pdf -o output.json
```

## Output Format

Each page in the output JSON contains:

```json
{
  "page": 1,
  "width": 612.0,
  "height": 792.0,
  "blocks": [
    {
      "text": "some text",
      "bbox": [x0, y0, x1, y1],
      "font": "FontName",
      "size": 12.0,
      "color": 0
    }
  ],
  "images": [
    {
      "bbox": [x0, y0, x1, y1],
      "width": 100,
      "height": 50
    }
  ]
}
```

- `blocks`: text spans (used for PII detection and rewriting)
- `images`: image/signature/handwriting regions (location info only)
- In OCR mode, `blocks` entries also include a `confidence` field (0–100)

See `sample_output.json` for a real example.

## Tests

```bash
python3 -m unittest test_pdf_extractor.py
```
