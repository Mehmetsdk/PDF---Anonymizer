"""Creates test_data/sample_application.pdf with valid PII for testing."""
import fitz
from pathlib import Path

OUTPUT = Path(__file__).parent / "sample_application.pdf"

doc = fitz.open()
page = doc.new_page(width=595, height=842)  # A4

lines = [
    ("APPLICATION FORM", 50, 60, 16, True),
    ("Name: Ahmet Yilmaz", 50, 100, 12, False),
    ("Phone: +90 532 123 45 67", 50, 125, 12, False),
    ("Email: ahmet.yilmaz@example.com", 50, 150, 12, False),
    ("TC ID: 12345678950", 50, 175, 12, False),   # valid checksum TC ID
    ("IBAN: TR33 0006 1005 1978 6457 8413 26", 50, 200, 12, False),
    ("Student ID: 20210123456", 50, 225, 12, False),
    ("Company: ABC Teknoloji A.S.", 50, 250, 12, False),
    ("Date: 23.06.2026", 50, 300, 12, False),
]

for text, x, y, size, bold in lines:
    page.insert_text((x, y), text, fontsize=size)

doc.save(str(OUTPUT), garbage=4, deflate=True)
doc.close()
print(f"Saved: {OUTPUT}")


def verify_tc_checksum(tc: str) -> bool:
    if len(tc) != 11 or not tc.isdigit() or tc[0] == "0":
        return False
    digits = [int(c) for c in tc]
    d10 = ((sum(digits[:9:2]) * 7) - sum(digits[1:8:2])) % 10
    d11 = (sum(digits[:10])) % 10
    return digits[9] == d10 and digits[10] == d11

print("TC ID valid:", verify_tc_checksum("12345678950"))
