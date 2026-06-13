"""Decode rác font cũ TCVN3 (.VnTime…) -> Unicode. $0, KHÔNG cần GPU/OCR.

Vì sao decode được mà không cần OCR: rác này là *byte còn nguyên, chỉ sai font* —
PyMuPDF đọc byte TCVN3 nhưng không có ToUnicode nên hiện ra ký tự CP1252 (µ ¸ © …).
TCVN3 là bảng 1:1 nên ánh xạ ngược lại được chính xác. (VNI thì tách âm tiết theo
khoảng trắng — "Đi e à u"=="Điều" — KHÔNG decode 1:1 được, để dành re-OCR.)

Bảng map KHÔNG gõ từ trí nhớ: suy ra bằng cách CĂN CHỈNH theo codepoint giữa dòng
rác và boilerplate đã biết ("Toµ ¸n nh©n d©n"=="Toà án nhân dân", 1:1), rồi xác minh
phần còn lại bằng từ điển 7184 âm tiết. Ký hiệu hợp lệ (m² ½ ÷ ©®) KHÔNG nằm trong map.

AN TOÀN — decode THEO DÒNG, có gác cổng:
  1. chỉ thử dòng chứa ký tự rác KHÔNG nhập nhằng (µ ¸ © ® § …) — dòng Unicode sạch
     không bao giờ có chúng nên không bị đụng;
  2. chỉ GIỮ bản decode nếu nó LÀM TĂNG tỉ lệ âm tiết hợp lệ của dòng. Nhờ vậy 'é','ó'
     (vừa là chữ Việt thật vừa là glyph TCVN3) chỉ đổi khi đang ở dòng rác thật sự.

Dùng:
    python legacy_decode.py            # DRY-RUN: báo cáo, không ghi
    python legacy_decode.py --apply
"""
import os
import sys
import json
import unicodedata
import regex

PROCESSED = os.path.join(os.getcwd(), "data", "processed")
SYL = set(l.strip().lower() for l in
          open(os.path.join("data", "vi_syllables.txt"), encoding="utf-8") if l.strip())

# TCVN3 (hiện dưới dạng CP1252) -> tiếng Việt. Suy ra bằng căn-chỉnh-boilerplate.
TCVN3 = {
    '\xad': 'ư',  # soft-hyphen, KHÔNG phải '-' thường
    '§': 'Đ', '©': 'â', 'ª': 'ê', '«': 'ô', '¬': 'ơ', '®': 'đ', 'µ': 'à',
    '¶': 'ả', '·': 'ã', '¸': 'á', '¹': 'ạ', '¨': 'ă', '¾': 'ắ', '»': 'ằ',
    'Ç': 'ầ', 'Ë': 'ậ', 'Ð': 'é', 'Õ': 'ế', 'Ö': 'ệ', 'Ï': 'ẽ', 'Ü': 'ĩ',
    'Þ': 'ị', 'ß': 'ò', 'å': 'ồ', 'è': 'ố', 'é': 'ộ', 'æ': 'ổ', 'î': 'ợ',
    'ñ': 'ủ', 'ó': 'ú', 'ø': 'ứ', 'ö': 'ử', 'ù': 'ự', 'ä': 'ọ', '×': 'ì',
    'Ø': 'ỉ', 'ë': 'ở', 'Æ': 'ặ', '¢': 'Â', '¤': 'Ô',
}
# Tín hiệu "dòng này là rác TCVN3": CHỈ các glyph RIÊNG của TCVN3 (không dùng chung
# với VNI, không trùng codepoint chữ Việt thật). Dòng VNI không chứa chúng -> không
# kích hoạt -> để dành re-OCR. Các glyph dùng chung (ö ñ ø æ ä å Ç Ø) vẫn ở trong
# TCVN3 map để decode tiếp KHI dòng đã được 1 glyph TCVN3-riêng kích hoạt.
TRIGGER = set('µ¸©¬®§ËÞÖÜª«¶·¹¨¾»¢¤îëÆÏÕ')

_WORD = regex.compile(r'[^\W\d_]+', regex.UNICODE)


def _valid_frac(text):
    toks = [w for w in _WORD.findall(text.lower()) if len(w) > 1]
    return sum(w in SYL for w in toks) / len(toks) if toks else 0.0


def _decode_line(ln):
    return unicodedata.normalize('NFC', ''.join(TCVN3.get(c, c) for c in ln))


def fix_text(ft):
    out, changed = [], 0
    for ln in ft.split('\n'):
        if any(c in TRIGGER for c in ln):
            dec = _decode_line(ln)
            # gác cổng: phải vừa khá hơn dòng gốc, VỪA đạt ngưỡng hợp lệ tuyệt đối.
            # Dòng VNI bị map TCVN3 (sai bảng) vẫn rác (~0.25) -> tự loại, khỏi cần
            # phân loại họ font; dòng có ký hiệu hợp lệ (m² ½ ©) không tăng điểm -> giữ.
            if dec != ln and _valid_frac(dec) >= 0.6 and _valid_frac(dec) > _valid_frac(ln):
                out.append(dec)
                changed += 1
                continue
        out.append(ln)
    return '\n'.join(out), changed


def main(apply=False):
    files = [f for f in os.listdir(PROCESSED) if f.endswith(".json")]
    docs = lines = 0
    samples = []
    for fn in files:
        p = os.path.join(PROCESSED, fn)
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        ft = d.get("full_text", "")
        if not any(c in TRIGGER for c in ft):
            continue
        fixed, n = fix_text(ft)
        if not n:
            continue
        docs += 1
        lines += n
        if len(samples) < 8:
            for a, b in zip(ft.split('\n'), fixed.split('\n')):
                if a != b:
                    samples.append((fn, a, b))
                    break
        if apply:
            d["full_text"] = fixed
            with open(p, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)

    head = "ĐÃ SỬA & GHI" if apply else "DRY-RUN (chưa ghi)"
    print(f"=== {head}: {docs} doc, {lines} dòng decode ===")
    for fn, a, b in samples:
        print(f"\n{fn}")
        print("  rác :", repr(a[:70]))
        print("  ->  :", repr(b[:70]))
    if docs and not apply:
        print("\n→ Chạy lại với --apply để ghi.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
