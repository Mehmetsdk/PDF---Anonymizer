# Person 2 — PII Detection

This module consumes the JSON produced by `pdf-extractor.py` and detects sensitive data with coordinates.

## Input

A list of pages:

```json
[
  {
    "page": 1,
    "width": 595,
    "height": 842,
    "blocks": [
      {
        "text": "Email: can@example.com",
        "bbox": [50, 100, 230, 115],
        "font": "Arial",
        "size": 11,
        "color": 0
      }
    ],
    "images": []
  }
]
```

## Run

```bash
python pii_detector.py sample_output.json -o pii_output.json
```

Optional spaCy NER:

```bash
pip install spacy
python -m spacy download en_core_web_sm
python pii_detector.py sample_output.json -o pii_output.json --enable-ner --spacy-model en_core_web_sm
```

## Output

```json
{
  "schema_version": "person2-pii-v1",
  "source": "Person 2 - PII Detection",
  "ner_status": "disabled",
  "detections": [
    {
      "page_no": 1,
      "type": "EMAIL",
      "original_text": "can@example.com",
      "bbox": [100.0, 100.0, 210.0, 115.0],
      "confidence": 0.99,
      "method": "regex",
      "rule": "email",
      "font": "Arial",
      "size": 11.0
    }
  ],
  "summary": {
    "EMAIL": 1
  }
}
```

## Supported types

- `EMAIL`
- `PHONE`
- `TC_ID`
- `IBAN`
- `STUDENT_INDEX`
- `PERSON_NAME`
- `ORGANIZATION`
- `LOCATION` with spaCy NER
- `SIGNATURE_FIELD`
- `HANDWRITING_FIELD`
- `SIGNATURE_IMAGE`

## Notes for Person 3 and Person 4

Person 3 should use `type` + `original_text` to generate replacement fake values.

Person 4 should use `page_no` + `bbox` to redact/replace the detected value in the PDF. For signature and handwriting fields, `bbox` is a heuristic target area and `label_bbox` is the label location.
