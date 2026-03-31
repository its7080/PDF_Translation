import unittest
import json
import tempfile
import os

from pdf_translator_main import (
    detect_lang, normalize_ocr_text, is_useful, bengali_ratio,
    postprocess_bengali_text, load_glossary, translate_mixed_line
)


class TranslationUtilsTests(unittest.TestCase):
    def test_detect_lang_hindi(self):
        self.assertEqual(detect_lang("यह हिंदी वाक्य है"), "hi")

    def test_detect_lang_english(self):
        self.assertEqual(detect_lang("This is an english sentence"), "en")

    def test_detect_lang_mixed(self):
        self.assertEqual(detect_lang("यह किताब mixed"), "mixed")

    def test_normalize_ocr_text(self):
        raw = "  Hello   —   world  “quote”  "
        self.assertEqual(normalize_ocr_text(raw), 'Hello - world "quote"')

    def test_is_useful_filters_noise(self):
        self.assertFalse(is_useful("@@@###"))
        self.assertFalse(is_useful("a1"))
        self.assertTrue(is_useful("This is useful text"))
        self.assertTrue(is_useful("यह उपयोगी है"))

    def test_bengali_ratio(self):
        self.assertGreater(bengali_ratio("এটি বাংলা বাক্য"), 0.5)
        self.assertEqual(bengali_ratio("This is English"), 0.0)

    def test_postprocess_bengali_text(self):
        raw = "বাংলাে  পরিক্ষা ।"
        self.assertEqual(postprocess_bengali_text(raw), "বাংলা পরীক্ষা।")

    def test_load_glossary(self):
        payload = {"Physics": "পদার্থবিজ্ঞান"}
        with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
            path = f.name
        try:
            glossary = load_glossary(path)
            self.assertEqual(glossary["Physics"], "পদার্থবিজ্ঞান")
        finally:
            os.unlink(path)

    def test_translate_mixed_line(self):
        class DummyEngine:
            def hindi_to_bengali(self, text):
                return "হিন্দি"
            def english_to_bengali(self, text):
                return "ইংরেজি"

        out = translate_mixed_line("यह test", DummyEngine())
        self.assertIn("হিন্দি", out)
        self.assertIn("ইংরেজি", out)


if __name__ == "__main__":
    unittest.main()
