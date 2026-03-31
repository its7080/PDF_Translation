"""
PDF Language Translator v2
============================
Correctly handles IMAGE-BASED PDFs (like scanned books, designed notes).

Workflow:
  1. Convert each PDF page to a high-res image (pdf2image)
  2. OCR with Tesseract to extract text
  3. Detect language per line (Hindi / English)
  4. Translate: Hindi → Bengali, English → Bengali (via deep-translator / Google)
  5. Output a clean, formatted PDF with colour-coded translations

Dependencies — install ONCE:
    pip install pypdf pdfplumber pdf2image pytesseract deep-translator reportlab Pillow

System tools (install once):
    Ubuntu/Debian:  sudo apt install tesseract-ocr tesseract-ocr-hin poppler-utils
    macOS:          brew install tesseract tesseract-lang poppler
    Windows:        https://github.com/UB-Mannheim/tesseract/wiki  +  poppler for Windows

Usage:
    python pdf_translator_main.py input.pdf
    python pdf_translator_main.py input.pdf -o output.pdf
    python pdf_translator_main.py input.pdf --pages 3-10   # specific page range
    python pdf_translator_main.py input.pdf --dpi 300      # higher DPI for better OCR
"""

import argparse
import os
import re
import sys
import time
import json
from pathlib import Path

# ── Dependency auto-install ────────────────────────────────────────────────────
convert_from_path = None
pytesseract = None
Image = None
GoogleTranslator = None
TRANSLATOR_AVAILABLE = False
A4 = ParagraphStyle = colors = SimpleDocTemplate = Paragraph = Spacer = None
HRFlowable = PageBreak = cm = pdfmetrics = TTFont = None


def _install(pkg):
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

def ensure_runtime_dependencies(require_ocr: bool = False,
                                require_translator: bool = False,
                                require_pdf: bool = False):
    """Import heavy runtime dependencies lazily so utility tests can run offline."""
    global convert_from_path, pytesseract, Image, GoogleTranslator, TRANSLATOR_AVAILABLE
    global A4, ParagraphStyle, colors, SimpleDocTemplate, Paragraph, Spacer
    global HRFlowable, PageBreak, cm, pdfmetrics, TTFont

    if require_ocr and convert_from_path is None:
        try:
            from pdf2image import convert_from_path as _convert_from_path
        except ImportError:
            print("Installing pdf2image..."); _install("pdf2image")
            from pdf2image import convert_from_path as _convert_from_path
        convert_from_path = _convert_from_path

    if require_ocr and (pytesseract is None or Image is None):
        try:
            import pytesseract as _pytesseract
            from PIL import Image as _Image
        except ImportError:
            print("Installing pytesseract + Pillow..."); _install("pytesseract Pillow")
            import pytesseract as _pytesseract
            from PIL import Image as _Image
        pytesseract = _pytesseract
        Image = _Image

    if require_translator and GoogleTranslator is None:
        try:
            from deep_translator import GoogleTranslator as _GoogleTranslator
            GoogleTranslator = _GoogleTranslator
            TRANSLATOR_AVAILABLE = True
        except ImportError:
            print("Installing deep-translator..."); _install("deep-translator")
            try:
                from deep_translator import GoogleTranslator as _GoogleTranslator
                GoogleTranslator = _GoogleTranslator
                TRANSLATOR_AVAILABLE = True
            except Exception:
                TRANSLATOR_AVAILABLE = False
                print("⚠️  deep-translator not available. Translations will be skipped.")

    if require_pdf and A4 is None:
        try:
            from reportlab.lib.pagesizes import A4 as _A4
            from reportlab.lib.styles import ParagraphStyle as _ParagraphStyle
            from reportlab.lib import colors as _colors
            from reportlab.platypus import (SimpleDocTemplate as _SimpleDocTemplate, Paragraph as _Paragraph,
                Spacer as _Spacer, HRFlowable as _HRFlowable, PageBreak as _PageBreak)
            from reportlab.lib.units import cm as _cm
            from reportlab.pdfbase import pdfmetrics as _pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont as _TTFont
        except ImportError:
            print("Installing reportlab..."); _install("reportlab")
            from reportlab.lib.pagesizes import A4 as _A4
            from reportlab.lib.styles import ParagraphStyle as _ParagraphStyle
            from reportlab.lib import colors as _colors
            from reportlab.platypus import (SimpleDocTemplate as _SimpleDocTemplate, Paragraph as _Paragraph,
                Spacer as _Spacer, HRFlowable as _HRFlowable, PageBreak as _PageBreak)
            from reportlab.lib.units import cm as _cm
            from reportlab.pdfbase import pdfmetrics as _pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont as _TTFont
        A4 = _A4
        ParagraphStyle = _ParagraphStyle
        colors = _colors
        SimpleDocTemplate = _SimpleDocTemplate
        Paragraph = _Paragraph
        Spacer = _Spacer
        HRFlowable = _HRFlowable
        PageBreak = _PageBreak
        cm = _cm
        pdfmetrics = _pdfmetrics
        TTFont = _TTFont


# ══════════════════════════════════════════════════════════════════════════════
#  FONT SETUP  (FreeSans supports Unicode including Bengali and Devanagari)
# ══════════════════════════════════════════════════════════════════════════════

def register_fonts():
    """Register a Unicode-capable font for reportlab."""
    # Preferred Bengali-friendly font (project-local path)
    kalpurush_path = Path(__file__).parent / "fonts" / "kalpurush.ttf"
    if kalpurush_path.exists():
        try:
            pdfmetrics.registerFont(TTFont("Kalpurush", str(kalpurush_path)))
            return "Kalpurush", "Kalpurush"
        except Exception:
            pass

    candidates = [
        ("/usr/share/fonts/truetype/freefont/FreeSans.ttf",     "UniFont",     False),
        ("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", "UniFontBold", False),
        ("C:/Windows/Fonts/arial.ttf",                          "UniFont",     False),
        ("C:/Windows/Fonts/arialbd.ttf",                        "UniFontBold", False),
        ("/System/Library/Fonts/Supplemental/Arial.ttf",        "UniFont",     False),
    ]
    registered = False
    for path, name, _ in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                registered = True
            except Exception:
                pass
    if not registered:
        print("⚠️  Unicode font not found. Bengali text may not render correctly.")
        return "Helvetica", "Helvetica-Bold"
    return "UniFont", "UniFontBold"


# ══════════════════════════════════════════════════════════════════════════════
#  LANGUAGE DETECTION
# ══════════════════════════════════════════════════════════════════════════════

DEVANAGARI = re.compile(r'[\u0900-\u097F]')
LATIN      = re.compile(r'[a-zA-Z]')
BENGALI    = re.compile(r'[\u0980-\u09FF]')

def detect_lang(text: str) -> str:
    """Return 'hi', 'en', or 'skip'."""
    hi = len(DEVANAGARI.findall(text))
    en = len(LATIN.findall(text))
    total = hi + en
    if total == 0:
        return 'skip'
    return 'hi' if hi / total > 0.45 else 'en'


def normalize_ocr_text(line: str) -> str:
    """Normalize OCR artifacts that reduce detection/translation quality."""
    line = re.sub(r'\s+', ' ', line).strip()
    # Common OCR confusions around punctuation/dashes.
    line = line.replace('—', '-').replace('–', '-').replace('“', '"').replace('”', '"')
    line = line.replace('‘', "'").replace('’', "'")
    return line


BN_COMMON_CORRECTIONS = {
    "বাংলাে": "বাংলা",
    "পরিক্ষা": "পরীক্ষা",
    "বই .": "বই।",
}


def postprocess_bengali_text(text: str) -> str:
    """Fix common Bengali spacing/punctuation/spelling artifacts."""
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s+([,.;:!?])', r'\1', text)
    text = text.replace(" ।", "।")
    for wrong, right in BN_COMMON_CORRECTIONS.items():
        text = text.replace(wrong, right)
    return text


def bengali_ratio(text: str) -> float:
    letters = len(re.findall(r'[\u0900-\u097F\u0980-\u09FFa-zA-Z]', text))
    if letters == 0:
        return 0.0
    return len(BENGALI.findall(text)) / letters


def is_useful(line: str) -> bool:
    """Reject very short or mostly-garbled OCR lines."""
    line = line.strip()
    if len(line) < 2:
        return False
    alpha_count = len(re.findall(r'[a-zA-Z\u0900-\u097F\u0980-\u09FF]', line))
    if alpha_count < 2:
        return False
    readable = len(re.findall(
        r'[a-zA-Z0-9\s\(\)\.\,\-\+\=\/\:\;\!\?\u0900-\u097F\u0980-\u09FF]', line
    ))
    return readable / len(line) > 0.45


# ══════════════════════════════════════════════════════════════════════════════
#  TRANSLATION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class TranslationEngine:
    def __init__(self, glossary: dict | None = None):
        self._cache: dict = {}
        self._glossary = glossary or {}
        if TRANSLATOR_AVAILABLE:
            self._hi_bn = GoogleTranslator(source='hi', target='bn')
            self._en_bn = GoogleTranslator(source='en', target='bn')
            self._auto_bn = GoogleTranslator(source='auto', target='bn')
        else:
            self._hi_bn = None
            self._en_bn = None
            self._auto_bn = None

    def _do(self, translator, text: str) -> str:
        if translator is None:
            return text
        text = normalize_ocr_text(text)
        key = (id(translator), text[:400])
        if key in self._cache:
            return self._cache[key]
        for attempt in range(3):
            try:
                result = translator.translate(text[:4900]) or text
                result = postprocess_bengali_text(result)
                self._cache[key] = result
                return result
            except Exception as e:
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                else:
                    print(f"    ⚠️  Translation failed: {e}")
                    return text

    def _apply_glossary(self, text: str) -> str:
        for src, tgt in self._glossary.items():
            text = text.replace(src, tgt)
        return text

    def hindi_to_bengali(self, text: str) -> str:
        primary = self._do(self._hi_bn, text)
        # fallback improves quality when OCR language detection is noisy
        if primary and bengali_ratio(primary) >= 0.25:
            return self._apply_glossary(primary)
        fallback = self._do(self._auto_bn, text)
        chosen = fallback if bengali_ratio(fallback) > bengali_ratio(primary) else primary
        return self._apply_glossary(chosen)

    def english_to_bengali(self, text: str) -> str:
        primary = self._do(self._en_bn, text)
        if primary and bengali_ratio(primary) >= 0.25:
            return self._apply_glossary(primary)
        fallback = self._do(self._auto_bn, text)
        chosen = fallback if bengali_ratio(fallback) > bengali_ratio(primary) else primary
        return self._apply_glossary(chosen)


# ══════════════════════════════════════════════════════════════════════════════
#  OCR EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════

def ocr_pages(pdf_path: str, dpi: int = 220,
              first_page: int = None, last_page: int = None) -> list:
    """
    Convert PDF pages to images and run Tesseract OCR.
    Returns list of dicts: {page, lines}
    """
    kwargs = {"dpi": dpi}
    if first_page:
        kwargs["first_page"] = first_page
    if last_page:
        kwargs["last_page"] = last_page

    print(f"  Converting PDF to images (DPI={dpi})...")
    try:
        images = convert_from_path(pdf_path, **kwargs)
    except Exception as e:
        print(f"  ❌ PDF→image failed: {e}")
        print("  Make sure poppler is installed.")
        sys.exit(1)

    # Detect available Tesseract languages
    try:
        langs_out = pytesseract.get_languages()
        ocr_lang = '+'.join(l for l in ['hin', 'eng'] if l in langs_out)
        if not ocr_lang:
            ocr_lang = 'eng'
    except Exception:
        ocr_lang = 'eng'

    print(f"  OCR language(s): {ocr_lang}")
    if 'hin' not in ocr_lang:
        print("  ⚠️  Hindi tessdata not found. Hindi script will appear garbled.")
        print("  Install with: sudo apt install tesseract-ocr-hin")

    results = []
    offset = first_page or 1
    for i, img in enumerate(images):
        pg = i + offset
        print(f"  OCR page {pg}/{offset + len(images) - 1}...", end='\r')
        text = pytesseract.image_to_string(img, lang=ocr_lang, config='--psm 6 --oem 3')
        lines = [
            normalize_ocr_text(l)
            for l in text.split('\n')
            if is_useful(normalize_ocr_text(l))
        ]
        results.append({'page': pg, 'lines': lines})

    print()
    return results


# ══════════════════════════════════════════════════════════════════════════════
#  TRANSLATION PASS
# ══════════════════════════════════════════════════════════════════════════════

def translate_pages(pages: list, engine: TranslationEngine) -> list:
    """
    Translate each line. Returns enriched list with translation data.
    """
    enriched = []
    total_pages = len(pages)

    for page_data in pages:
        pg = page_data['page']
        lines = page_data['lines']
        print(f"  Translating page {pg}/{total_pages} ({len(lines)} lines)...")

        translated_lines = []
        for line in lines:
            lang = detect_lang(line)
            entry = {'original': line, 'lang': lang, 'translation': ''}

            if lang == 'hi':
                entry['translation'] = engine.hindi_to_bengali(line)
                time.sleep(0.25)
            elif lang == 'en':
                entry['translation'] = engine.english_to_bengali(line)
                time.sleep(0.25)

            translated_lines.append(entry)

        enriched.append({'page': pg, 'lines': translated_lines})

    return enriched


# ══════════════════════════════════════════════════════════════════════════════
#  PDF OUTPUT
# ══════════════════════════════════════════════════════════════════════════════

def build_pdf(enriched_pages: list, output_path: str,
              source_name: str = "document.pdf"):
    """Build colour-coded bilingual PDF."""
    font_regular, font_bold = register_fonts()

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        rightMargin=1.8*cm, leftMargin=1.8*cm,
        topMargin=1.8*cm, bottomMargin=1.8*cm
    )

    # ── Styles ──
    def ps(name, **kw):
        base = dict(fontName=font_regular, fontSize=10, leading=14,
                    spaceAfter=4, borderPadding=(3, 5, 3, 5))
        base.update(kw)
        return ParagraphStyle(name, **base)

    s_header  = ps('H',  fontName=font_bold, fontSize=12,
                   textColor=colors.white, backColor=colors.HexColor('#2C3E50'),
                   spaceAfter=8, spaceBefore=4, leading=18,
                   leftIndent=8, borderPadding=(5, 8, 5, 8))
    s_label   = ps('Lb', fontName=font_bold, fontSize=7,
                   textColor=colors.HexColor('#95A5A6'), spaceAfter=1, spaceBefore=5)
    s_orig_hi = ps('OH', textColor=colors.HexColor('#5D4037'),
                   backColor=colors.HexColor('#FFF8E1'), fontSize=9.5)
    s_orig_en = ps('OE', textColor=colors.HexColor('#1A3A5C'),
                   backColor=colors.HexColor('#E3F2FD'), fontSize=9.5)
    s_tr_hi_bn = ps('THB', textColor=colors.HexColor('#1B5E20'),
                   backColor=colors.HexColor('#E8F5E9'), fontSize=9.5)
    s_tr_en_bn = ps('TEB', textColor=colors.HexColor('#4A148C'),
                   backColor=colors.HexColor('#F3E5F5'), fontSize=9.5)
    s_intro   = ps('IN', textColor=colors.HexColor('#555'))

    def safe(t):
        return (t.replace('&', '&amp;')
                 .replace('<', '&lt;')
                 .replace('>', '&gt;'))

    def P(text, style):
        try:
            return Paragraph(safe(text), style)
        except Exception:
            cleaned = re.sub(r'[^\x00-\x7F\u0900-\u097F\u0980-\u09FF\s]', '?', text)
            return Paragraph(safe(cleaned), style)

    story = []

    # ── Cover page ──
    story.append(P(f"  PDF Translation Report", s_header))
    story.append(P(f"Source: {source_name}", s_intro))
    story.append(P("Hindi  →  Bengali  |  English  →  Bengali", s_intro))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#BDC3C7')))
    story.append(Spacer(1, 8))
    story.append(P("Colour guide:", ps('CG', fontName=font_bold, textColor=colors.HexColor('#2C3E50'))))

    legend = [
        ["Yellow bg", "Original Hindi text (OCR extracted)"],
        ["Light green bg", "Hindi → Bengali translation"],
        ["Blue bg", "Original English text"],
        ["Purple bg", "English → Bengali translation"],
    ]
    for bg_desc, meaning in legend:
        story.append(P(f"  {bg_desc}: {meaning}", s_intro))

    story.append(Spacer(1, 16))
    story.append(PageBreak())

    # ── Content pages ──
    for page_data in enriched_pages:
        pg  = page_data['page']
        lines = page_data['lines']

        story.append(P(f"  Page {pg}", s_header))
        story.append(Spacer(1, 4))

        if not lines:
            story.append(P("(No text extracted from this page)", s_intro))
        else:
            for entry in lines:
                orig = entry['original']
                lang = entry['lang']
                tr   = entry.get('translation', '')

                if lang == 'hi':
                    story.append(P("Original (Hindi — OCR):", s_label))
                    story.append(P(orig, s_orig_hi))
                    if tr and tr != orig:
                        story.append(P("→ Bengali:", s_label))
                        story.append(P(tr, s_tr_hi_bn))

                elif lang == 'en':
                    story.append(P("Original (English):", s_label))
                    story.append(P(orig, s_orig_en))
                    if tr and tr != orig:
                        story.append(P("→ Bengali:", s_label))
                        story.append(P(tr, s_tr_en_bn))

                story.append(Spacer(1, 2))

        story.append(HRFlowable(width='100%', thickness=0.5,
                                 color=colors.HexColor('#D5DBDB')))
        story.append(PageBreak())

    doc.build(story)
    size = os.path.getsize(output_path)
    print(f"\n✅ Output PDF saved: {output_path} ({size // 1024} KB)")
    return output_path


# ══════════════════════════════════════════════════════════════════════════════
#  SAVE / LOAD PROGRESS  (resume long jobs)
# ══════════════════════════════════════════════════════════════════════════════

def save_progress(data: list, path: str):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_progress(path: str) -> list:
    with open(path, encoding='utf-8') as f:
        return json.load(f)

def load_glossary(path: str | None) -> dict:
    if not path:
        return {}
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Glossary file must be a JSON object: {\"source\":\"target\"}")
    return {str(k): str(v) for k, v in data.items()}

def evaluate_accuracy(eval_file: str, engine: TranslationEngine) -> dict:
    """
    Evaluate translation quality with a labeled JSON file:
    [
      {"source":"...", "lang":"hi|en", "target":"..."},
      ...
    ]
    """
    from difflib import SequenceMatcher

    with open(eval_file, encoding='utf-8') as f:
        dataset = json.load(f)

    total = len(dataset)
    if total == 0:
        return {"samples": 0, "avg_similarity": 0.0, "avg_bn_ratio": 0.0}

    sim_scores, bn_scores = [], []
    for row in dataset:
        src = normalize_ocr_text(row.get("source", ""))
        lang = row.get("lang", "en")
        target = normalize_ocr_text(row.get("target", ""))
        if lang == "hi":
            pred = engine.hindi_to_bengali(src)
        else:
            pred = engine.english_to_bengali(src)
        sim_scores.append(SequenceMatcher(None, pred, target).ratio())
        bn_scores.append(bengali_ratio(pred))

    return {
        "samples": total,
        "avg_similarity": sum(sim_scores) / total,
        "avg_bn_ratio": sum(bn_scores) / total,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def parse_pages(page_str: str):
    """Parse '3-10' or '1,3,5' into (first, last) tuple."""
    if not page_str:
        return None, None
    if '-' in page_str:
        parts = page_str.split('-')
        return int(parts[0]), int(parts[1])
    pages = [int(x) for x in page_str.split(',')]
    return min(pages), max(pages)


def main():
    parser = argparse.ArgumentParser(
        description="PDF Translator: Hindi→Bengali, English→Bengali (image-based PDFs)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pdf_translator_main.py physics.pdf
  python pdf_translator_main.py physics.pdf -o physics_bn.pdf
  python pdf_translator_main.py physics.pdf --pages 3-16 --dpi 300
  python pdf_translator_main.py physics.pdf --ocr-only   # extract without translating
        """
    )
    parser.add_argument('input', nargs='?', help='Input PDF file (not required for --evaluate-only)')
    parser.add_argument('-o', '--output', help='Output PDF path (auto-named if omitted)')
    parser.add_argument('--pages', help='Page range, e.g. "3-10" or "1,3,5"')
    parser.add_argument('--dpi', type=int, default=220, help='OCR DPI (default 220, use 300 for better quality)')
    parser.add_argument('--ocr-only', action='store_true', help='Only extract text, no translation')
    parser.add_argument('--resume', help='Resume from a saved JSON progress file')
    parser.add_argument('--eval-file', help='Optional labeled JSON file to evaluate translation accuracy')
    parser.add_argument('--glossary-file', help='Optional JSON glossary for term-accurate Bengali output')
    parser.add_argument('--evaluate-only', action='store_true',
                        help='Run only --eval-file accuracy check, skip PDF OCR/output')
    args = parser.parse_args()

    glossary = load_glossary(args.glossary_file) if args.glossary_file else {}

    if args.evaluate_only:
        if not args.eval_file:
            print("❌ --evaluate-only requires --eval-file")
            sys.exit(1)
        ensure_runtime_dependencies(require_translator=True)
        engine = TranslationEngine(glossary=glossary)
        metrics = evaluate_accuracy(args.eval_file, engine)
        print("\n📊 Accuracy evaluation")
        print(f"  Samples: {metrics['samples']}")
        print(f"  Avg similarity vs reference: {metrics['avg_similarity']:.3f}")
        print(f"  Avg Bengali character ratio: {metrics['avg_bn_ratio']:.3f}")
        return

    if not args.input:
        print("❌ Input PDF is required unless using --evaluate-only")
        sys.exit(1)

    ensure_runtime_dependencies(require_ocr=True, require_translator=True, require_pdf=True)

    if not os.path.exists(args.input):
        print(f"❌ File not found: {args.input}")
        sys.exit(1)

    output = args.output or str(
        Path(args.input).parent / f"{Path(args.input).stem}_translated.pdf"
    )

    first_page, last_page = parse_pages(args.pages)

    print(f"\n📄 Input:  {args.input}")
    print(f"📝 Output: {output}")
    if args.pages:
        print(f"📑 Pages:  {args.pages}")
    print()

    # 1. OCR extraction
    if args.resume and os.path.exists(args.resume):
        print(f"📂 Resuming from: {args.resume}")
        ocr_data = load_progress(args.resume)
        # Convert to format expected by translate_pages
        pages = [{'page': d['page'], 'lines': [e['original'] for e in d['lines']]}
                 for d in ocr_data]
    else:
        print("🔍 Step 1: OCR text extraction")
        pages = ocr_pages(args.input, dpi=args.dpi,
                          first_page=first_page, last_page=last_page)
        total_lines = sum(len(p['lines']) for p in pages)
        print(f"  ✅ Extracted {total_lines} lines from {len(pages)} pages\n")

    if args.ocr_only:
        # Save OCR result as text file
        txt_path = str(Path(output).with_suffix('.txt'))
        with open(txt_path, 'w', encoding='utf-8') as f:
            for p in pages:
                f.write(f"\n{'='*50}\nPAGE {p['page']}\n{'='*50}\n")
                for line in p['lines']:
                    f.write(line + '\n')
        print(f"✅ OCR text saved to: {txt_path}")
        return

    # 2. Translation
    print("🌐 Step 2: Translation")
    if not TRANSLATOR_AVAILABLE:
        print("  ⚠️  Translator not available. Install deep-translator and retry.")
    engine = TranslationEngine(glossary=glossary)

    # Convert pages format for translate_pages
    pages_for_translation = pages
    if args.resume and os.path.exists(args.resume):
        enriched_pages = load_progress(args.resume)
    else:
        enriched_pages = translate_pages(pages_for_translation, engine)
        # Save progress
        progress_file = str(Path(output).with_suffix('.progress.json'))
        save_progress(enriched_pages, progress_file)
        print(f"  💾 Progress saved to: {progress_file}")

    # 3. Build PDF
    print("\n📑 Step 3: Building output PDF")
    build_pdf(enriched_pages, output, source_name=Path(args.input).name)

    if args.eval_file:
        print("\n📊 Step 4: Accuracy evaluation")
        metrics = evaluate_accuracy(args.eval_file, engine)
        print(f"  Samples: {metrics['samples']}")
        print(f"  Avg similarity vs reference: {metrics['avg_similarity']:.3f}")
        print(f"  Avg Bengali character ratio: {metrics['avg_bn_ratio']:.3f}")

    print(f"\n🎉 Done!")


if __name__ == '__main__':
    main()
