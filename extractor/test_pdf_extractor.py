import os
import json
import unittest
import fitz

from pdf_extractor import extract_text_with_layout, is_scanned_pdf


class TestPdfExtractor(unittest.TestCase):

    def setUp(self):
        self.test_pdf_path = "test_sample.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Hello World, this is a test document with enough text.", fontsize=12)
        doc.save(self.test_pdf_path)
        doc.close()

    def tearDown(self):
        if os.path.exists(self.test_pdf_path):
            os.remove(self.test_pdf_path)

    def test_extract_text_with_layout_returns_correct_page_count(self):
        result = extract_text_with_layout(self.test_pdf_path)
        self.assertEqual(len(result), 1)

    def test_extract_text_with_layout_contains_expected_text(self):
        result = extract_text_with_layout(self.test_pdf_path)
        all_text = " ".join(block["text"] for block in result[0]["blocks"])
        self.assertIn("Hello World", all_text)

    def test_extract_text_with_layout_block_has_required_fields(self):
        result = extract_text_with_layout(self.test_pdf_path)
        block = result[0]["blocks"][0]
        for field in ("text", "bbox", "font", "size", "color"):
            self.assertIn(field, block)

    def test_is_scanned_pdf_returns_false_for_text_pdf(self):
        self.assertFalse(is_scanned_pdf(self.test_pdf_path))

    def test_output_is_json_serializable(self):
        result = extract_text_with_layout(self.test_pdf_path)
        json.dumps(result)


if __name__ == "__main__":
    unittest.main()