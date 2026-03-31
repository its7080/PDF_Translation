import unittest

from pdf_translator_main import detect_lang, normalize_ocr_text, is_useful, bengali_ratio


class TranslationUtilsTests(unittest.TestCase):
    def test_detect_lang_hindi(self):
        self.assertEqual(detect_lang("यह हिंदी वाक्य है"), "hi")

    def test_detect_lang_english(self):
        self.assertEqual(detect_lang("This is an english sentence"), "en")

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


if __name__ == "__main__":
    unittest.main()
