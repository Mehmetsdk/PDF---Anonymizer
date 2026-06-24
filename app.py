import json
import os
import sys
import tempfile
from pathlib import Path

import requests
import streamlit as st

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "extractor"))
sys.path.insert(0, str(ROOT / "fake_generator"))
sys.path.insert(0, str(ROOT / "reconstructor"))

from pdf_extractor import extract_text_with_layout, is_scanned_pdf, ocr_pdf
from pii_detector import detect_pii
from fake_data_generator import build_replacements
from reconstructor import reconstruct_pdf
from pipeline import _build_anonymization_map

# n8n webhook URL — set via environment variable or sidebar input
N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "")


def _trigger_n8n(webhook_url: str, filename: str, pii_count: int, summary: dict):
    """Send anonymization result to n8n webhook (fire-and-forget)."""
    try:
        requests.post(webhook_url, json={
            "event": "anonymization_complete",
            "filename": filename,
            "pii_detected": pii_count,
            "summary": summary,
        }, timeout=5)
    except Exception:
        pass  # webhook failure should never block the user


st.set_page_config(page_title="PDF Anonymizer", page_icon="lock", layout="centered")

st.title("PDF Anonymizer")
st.write("Upload a PDF to replace all sensitive data with realistic fake values while preserving the original layout.")

# Sidebar — n8n configuration
with st.sidebar:
    st.header("Notifications (n8n)")
    webhook_url = st.text_input(
        "n8n Webhook URL",
        value=N8N_WEBHOOK_URL,
        placeholder="https://your-n8n.example.com/webhook/...",
        help="When anonymization finishes, a notification is sent to this URL. Leave empty to disable.",
    )

uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])

if uploaded_file:
    st.info(f"File uploaded: **{uploaded_file.name}** ({round(len(uploaded_file.getvalue()) / 1024, 1)} KB)")

    if st.button("Anonymize PDF", type="primary"):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / uploaded_file.name
            input_path.write_bytes(uploaded_file.getvalue())
            output_path = tmp / f"{input_path.stem}_anonymized.pdf"

            progress = st.progress(0, text="Starting...")

            # Step 1
            progress.progress(10, text="[1/4] Extracting layout from PDF...")
            if is_scanned_pdf(str(input_path)):
                layout = ocr_pdf(str(input_path))
                scanned = True
            else:
                layout = extract_text_with_layout(str(input_path))
                scanned = False
            total_blocks = sum(len(p["blocks"]) for p in layout)
            progress.progress(30, text=f"[1/4] Extracted {total_blocks} text blocks.")

            # Step 2
            progress.progress(35, text="[2/4] Detecting PII...")
            pii_result = detect_pii(layout)
            detections = pii_result["detections"]
            progress.progress(55, text=f"[2/4] Found {len(detections)} PII detections.")

            # Step 3
            progress.progress(60, text="[3/4] Generating fake replacements...")
            replacements, mapping = build_replacements(detections)
            progress.progress(75, text=f"[3/4] Generated {len(mapping)} unique fake values.")

            # Step 4
            progress.progress(80, text="[4/4] Reconstructing anonymized PDF...")
            anonymization_map = _build_anonymization_map(replacements, detections)
            anon_map_path = tmp / "anonymization_map.json"
            anon_map_path.write_text(
                json.dumps(anonymization_map, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            reconstruct_pdf(str(input_path), str(anon_map_path), str(output_path))
            progress.progress(100, text="Done!")

            # Trigger n8n webhook if configured
            if webhook_url.strip():
                _trigger_n8n(
                    webhook_url.strip(),
                    uploaded_file.name,
                    len(detections),
                    pii_result.get("summary", {}),
                )

            # Results
            st.success("Anonymization complete!")

            col1, col2, col3 = st.columns(3)
            col1.metric("Pages", len(layout))
            col2.metric("PII Detected", len(detections))
            col3.metric("Unique Fakes", len(mapping))

            if pii_result.get("summary"):
                st.subheader("Detected PII Types")
                for pii_type, count in pii_result["summary"].items():
                    st.write(f"- **{pii_type}**: {count}")
            else:
                st.warning("No PII detected in this document.")

            if scanned:
                st.info("Scanned PDF detected — OCR was used for text extraction.")

            st.download_button(
                label="Download Anonymized PDF",
                data=output_path.read_bytes(),
                file_name=f"{input_path.stem}_anonymized.pdf",
                mime="application/pdf",
                type="primary",
            )
