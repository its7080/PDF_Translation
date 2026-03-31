# PDF_Translation

This project translates **Hindi** and **English** text from PDFs into **Bengali**.

## What it does
- Extracts text from image-based/scanned PDFs using OCR.
- Detects whether a line is Hindi or English.
- Translates both Hindi and English lines into Bengali.
- Builds a readable output PDF with source text + Bengali translation.

## Accuracy improvements included
- Better OCR cleanup before language detection/translation.
- Stronger line filtering to reduce garbage OCR noise.
- Translation caching and safer retry logic with backoff.
- Native Hindi → Bengali translation (instead of Hindi → English pivoting).
- Automatic Bengali-quality fallback (`auto -> bn`) when primary translation output looks weak.

## Run
```bash
pip install -r requirement.txt

python pdf_translator_main.py input.pdf -o output.pdf

# optional: evaluate accuracy with a labeled dataset
python pdf_translator_main.py input.pdf -o output.pdf --eval-file eval_samples.json

# evaluate only (no OCR/PDF generation)
python pdf_translator_main.py --evaluate-only --eval-file eval_samples.json
```

### Evaluation dataset format
```json
[
  {"source": "यह एक किताब है", "lang": "hi", "target": "এটি একটি বই"},
  {"source": "This is a test", "lang": "en", "target": "এটি একটি পরীক্ষা"}
]
```

Use the included `eval_samples.json` as a starter baseline and replace entries with domain-specific lines from your own PDFs for better accuracy tracking.
