import os
import re
import io
import math
import unicodedata
import regex

SYLLABLE_FILE = os.path.join(os.path.dirname(__file__), 'data', 'vi_syllables.txt')

SECTION_PATTERN = re.compile(
    r'(NỘI\s+DUNG\s+VỤ\s+ÁN|NHẬN\s+ĐỊNH\s+CỦA\s+TÒA\s+ÁN|QUYẾT\s+ĐỊNH(?!\s+(?:ĐÌNH|CÔNG|TUYÊN|GIẢI|VỀ)))\s*:?'
)

# --- Classification signals (validated on this dataset) ---
# Legacy Vietnamese font (TCVN3/VNI) with no ToUnicode map: PyMuPDF reads the raw
# bytes as Latin-1, so chars are wrong at the source (ò->ß, â->©, đ->®, Đ->§, ...).
# Signature = Latin-1 chars that NEVER occur in valid Vietnamese (so safe to flag):
#   TCVN3: ß © ® ¸ Ö Ü ñ × ¨ ÷ ¬ µ        VNI: ø Ø ï Ï î ö ä Ä å Å Ñ Ð ð Æ æ Ç ç Û û ë Þ þ
LEGACY_SIG = regex.compile(r'[ß©®¸ÖÜñ×¨÷¬µ\xadøØïÏîöäÄåÅÑÐðÆæÇçÛûëÞþ]')
# A lowercase letter immediately followed by UPPERCASE = a swallowed space ('phốHồ').
GLUE = regex.compile(r'\p{Ll}\p{Lu}')
# A long all-caps run = glued header ('CHỦNGHĨA', 'PHỐHỒCHÍ'). High enough to clear
# legit all-caps words (NGUYÊN, THƯƠNG, ...).
ALLCAPS_GLUE = regex.compile(r'\p{Lu}{8,}')

MIN_PAGE_CHARS = 50      # a page below this is treated as image/scanned
SCANNED_FRACTION = 0.30  # >30% image pages -> OCR the whole doc
LEGACY_DENSITY = 0.005   # legacy-signature chars / total chars
GLUE_JOINTS = 5          # lower->UPPER joints needed to call text "glued"

MIN_SPLIT_LEN = 4        # only try to split letter-runs at least this long
OCR_DPI = 150            # render DPI for scanned pages

_LETTERS = regex.compile(r'\p{L}+')


# --- Glued-text fix: deterministic Vietnamese syllable splitter (no model) -------
# Frequency-ranked syllable list (hieuthi/common-vietnamese-syllables, ~7.2k).
# Word-break DP à la wordninja: among segmentations into known syllables, pick the
# one minimising summed Zipf cost. Only inserts spaces — never alters a character,
# so digits, names and article numbers are physically untouchable.

# The five Vietnamese tone marks as combining codepoints (NOT letter modifiers like
# breve/circumflex/horn). A syllable carries at most one.
_TONE_MARKS = frozenset('̣̀́̃̉')  # huyền sắc ngã hỏi nặng


def _toneless_key(s):
    """Tone-placement-invariant key: 'thỏa' (old) and 'thoả' (new) map to the same
    thing, so dictionary lookup is robust to either orthography. Letter modifiers
    (â ê ô ơ ư ă đ) are kept; only the tone mark is pulled out to a suffix."""
    base, tone = [], ''
    for ch in unicodedata.normalize('NFD', s):
        if ch in _TONE_MARKS:
            tone = ch
        else:
            base.append(ch)
    return unicodedata.normalize('NFC', ''.join(base)) + tone


def _load_syllables(path):
    with open(path, encoding='utf-8') as f:
        words = [w.strip().lower() for w in f if w.strip()]
    n = len(words)
    cost = {}
    for rank, w in enumerate(words):
        cost.setdefault(_toneless_key(w), math.log((rank + 1) * math.log(n + 1)))
    maxlen = max(len(w) for w in words)
    return cost, maxlen


_SYL_COST, _SYL_MAXLEN = _load_syllables(SYLLABLE_FILE)


def _segment_run(run):
    """DP-segment a glued letter-run into known syllables (original case kept).

    Returns the space-separated form, or None if no full segmentation exists or it
    is a single syllable (nothing to split).
    """
    low = run.lower()
    n = len(low)
    best = [0.0] + [math.inf] * n     # best[i] = min cost to segment low[:i]
    back = [0] * (n + 1)
    for i in range(1, n + 1):
        for j in range(max(0, i - _SYL_MAXLEN), i):
            c = _SYL_COST.get(_toneless_key(low[j:i]))
            if c is not None and best[j] + c < best[i]:
                best[i] = best[j] + c
                back[i] = j
    if best[n] == math.inf:
        return None

    cuts, i = [], n
    while i > 0:
        cuts.append((back[i], i))
        i = back[i]
    if len(cuts) < 2:
        return None
    cuts.reverse()
    return ' '.join(run[a:b] for a, b in cuts)   # slice original to keep case/diacritics


def _case_fix(run):
    """Fix a stray UPPERCASE inside an otherwise-fine syllable ('tHành' -> 'thành').

    Only touches *internal* scramble — an uppercase letter with a lowercase letter
    somewhere after it. A trailing uppercase ('phốC', 'ThịU') is left alone: those
    are a syllable glued to a redacted name initial ('phố C', 'Thị U'), and
    lowercasing them would corrupt the name.
    """
    rest = run[1:] if run[0].isupper() else run    # a leading title-cap is normal
    seen_upper = False
    for ch in rest:
        if ch.isupper():
            seen_upper = True
        elif seen_upper and ch.islower():           # lowercase after uppercase = scramble
            low = run.lower()
            return low.capitalize() if run[0].isupper() else low
    return run


def _standardize(text):
    """Normalize any route's text into one consistent form before storing.

    NFC + de-glue/case-fix + unify dashes + drop stray page numbers + tidy
    whitespace. Case is PRESERVED on purpose: multilingual-e5 is case-sensitive and
    trained on natural-case text, so lowercasing tends to hurt, not help.
    """
    text = _split_glued(text)                      # NFC + re-space glued + fix sCramble
    text = regex.sub(r'[‐-―−﹘﹣－]', '-', text)  # dashes -> '-'
    text = regex.sub(r'[ \t]+', ' ', text)         # collapse runs of spaces/tabs
    text = regex.sub(r' *\n *', '\n', text)        # trim spaces around newlines
    text = regex.sub(r'\n{3,}', '\n\n', text)      # cap blank-line spam
    return text.strip()


def _strip_page_num(page_text):
    """Drop a stray page-number line at the top/bottom of ONE page.

    Position-bound on purpose: a bare digit line is only removed at a page boundary
    (where page numbers live), so a content number like '405' sitting mid-text is
    never touched.
    """
    lines = page_text.split('\n')
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines and regex.fullmatch(r'\d{1,3}', lines[0].strip()):
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and regex.fullmatch(r'\d{1,3}', lines[-1].strip()):
        lines.pop()
    return '\n'.join(lines)


def _split_glued(text):
    """Re-insert swallowed word spaces inside glued letter-runs. Free, no model."""
    text = unicodedata.normalize('NFC', text)

    def repl(m):
        run = m.group(0)
        if _toneless_key(run.lower()) in _SYL_COST:   # already a valid single syllable
            return _case_fix(run)
        if len(run) < MIN_SPLIT_LEN:          # too short to confidently split
            return run
        if all(ord(ch) < 128 for ch in run):  # pure ASCII -> foreign word, leave it
            return run
        return _segment_run(run) or run

    return _LETTERS.sub(repl, text)


# --- OCR for scanned docs: Surya, local on the Apple GPU (PyTorch MPS) -----------
# No model API, no cloud, $0. Predictors are loaded once (lazily) and reused.

_SURYA = None
# Surya can emit inline formatting tags (<b>, <i>, <math>, ...) — strip them.
_TAGS = regex.compile(r'</?(?:b|i|u|del|mark|small|sub|sup|math|br)\s*/?>')


def _surya():
    global _SURYA
    if _SURYA is None:
        os.environ.setdefault('PYTORCH_ENABLE_MPS_FALLBACK', '1')
        from surya.detection import DetectionPredictor
        from surya.recognition import RecognitionPredictor
        _SURYA = (DetectionPredictor(), RecognitionPredictor())
    return _SURYA


def _ocr_surya(doc):
    """OCR every page with Surya (local GPU). Strips formatting tags and stray
    page numbers, mirroring the text route."""
    from PIL import Image
    images = [
        Image.open(io.BytesIO(page.get_pixmap(dpi=OCR_DPI).tobytes('png'))).convert('RGB')
        for page in doc
    ]
    if not images:
        return ""
    det, rec = _surya()
    results = rec(images, det_predictor=det, math_mode=False)
    pages = [_TAGS.sub('', ' '.join(line.text for line in r.text_lines)) for r in results]
    return '\n'.join(_strip_page_num(p) for p in pages)


# --- Routing ---------------------------------------------------------------------

def _classify(pages):
    """Route a document. `pages` is a list of (text, has_image) per page.

    'scanned' -> mostly image pages                 -> vision OCR (reads every page)
    'legacy'  -> TCVN3/VNI font, bytes corrupted     -> DROP (logged)
    'holes'   -> text doc punctured by image page(s) -> DROP (logged): salvaging
                 leaves gaps that break sections / embeddings
    'glued'   -> Unicode but words run together      -> syllable splitter
    'clean'   -> Unicode, properly spaced            -> PyMuPDF as-is

    An image page is one with no text but an embedded image; a blank page (no text,
    no image) carries no content, so it never counts as a 'hole'.
    """
    text = '\n'.join(t for t, _ in pages)
    stripped = text.strip()
    if not stripped:
        return 'scanned'

    image_pages = sum(1 for t, img in pages if img and len(t.strip()) < MIN_PAGE_CHARS)
    if image_pages / max(len(pages), 1) > SCANNED_FRACTION:
        return 'scanned'

    n = len(stripped)
    if len(LEGACY_SIG.findall(stripped)) / n > LEGACY_DENSITY:
        return 'legacy'
    if image_pages > 0:
        return 'holes'
    if len(GLUE.findall(stripped)) >= GLUE_JOINTS or ALLCAPS_GLUE.search(stripped):
        return 'glued'
    return 'clean'


def classify(doc):
    """Public helper: the extraction route a document would take (no processing)."""
    return _classify([(page.get_text(), len(page.get_images()) > 0) for page in doc])


def extract_text(doc):
    """Extract text via the cheapest reliable route. Returns (text, route).

    clean/glued  -> PyMuPDF text + deterministic syllable splitter (free, no model)
    scanned      -> Surya OCR, local on the GPU
    legacy/holes -> text is None: the doc can't be trusted whole (byte-corrupted
                    chars, or a missing image page that breaks the doc), so it is
                    dropped — the caller logs the route and skips it.
    """
    pages = [(page.get_text(), len(page.get_images()) > 0) for page in doc]
    kind = _classify(pages)

    if kind in ('legacy', 'holes'):
        return None, kind
    if kind == 'scanned':
        text = _ocr_surya(doc)
    else:
        text = '\n'.join(_strip_page_num(t) for t, _ in pages)   # per-page: drop page numbers
    return _standardize(text), kind   # one consistent form for every route


def split_sections(text):
    """Split court judgment text into 4 sections by regex on standard headers."""
    if not text.strip():
        return {"opening": "", "noi_dung_vu_an": "", "nhan_dinh_cua_toa_an": "", "quyet_dinh": ""}

    parts = SECTION_PATTERN.split(text)

    sections = {"opening": parts[0].strip()}
    for header, content in zip(parts[1::2], parts[2::2]):
        normalized = re.sub(r'\s+', ' ', header.strip()).upper()
        if 'NỘI DUNG' in normalized:
            sections['NỘI DUNG VỤ ÁN'] = content.strip()
        elif 'NHẬN ĐỊNH' in normalized:
            sections['NHẬN ĐỊNH CỦA TÒA ÁN'] = content.strip()
        elif 'QUYẾT ĐỊNH' in normalized:
            sections['QUYẾT ĐỊNH'] = content.strip()

    return {
        "opening": sections.get("opening", ""),
        "noi_dung_vu_an": sections.get("NỘI DUNG VỤ ÁN", ""),
        "nhan_dinh_cua_toa_an": sections.get("NHẬN ĐỊNH CỦA TÒA ÁN", ""),
        "quyet_dinh": sections.get("QUYẾT ĐỊNH", ""),
    }
