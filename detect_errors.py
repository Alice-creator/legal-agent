"""Quét TOÀN BỘ data/processed, phát hiện & phân loại lỗi chất lượng full_text.

Chạy trên cả corpus (không sample) → báo cáo có thẩm quyền + ghi danh sách doc cần
re-OCR. Phân 3 nhóm:

  FIXABLE   — đáng lẽ ~0 sau các fix đã làm (nếu >0 là còn sót, cần xử lý):
              empty · pua · tone_swap(TÕA/HÕA) · guoc(ƣ) · glyph_bad(U+FFFD/control)
  RE-OCR    — cần đọc lại bằng Surya (font cũ / rụng chữ), defer:
              empty · legacy_char (mật độ font cũ cao) · low_density ·
              legacy_body (font cũ lẫn trong THÂN án — nội dung có giá trị bị hỏng)
  MINOR     — giữ lại: legacy chỉ ở letterhead/chữ ký (boilerplate; thân Unicode sạch)

Dùng:
    python detect_errors.py            # báo cáo
    python detect_errors.py --list     # + ghi data/processed/needs_reocr.txt
"""
import os
import sys
import json
import regex

import utils

PROCESSED = os.path.join(os.getcwd(), "data", "processed")
LOW_DENSITY = 0.15        # mật độ dấu dưới mức này = nghi rụng chữ / OCR kém
LEGACY_HEAVY = 0.005      # mật độ ký tự font cũ ≥ mức này = cần re-OCR (= ngưỡng routing)

_UNI = regex.compile(
    r'[ăâêôơưđàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ]', regex.I)
_CTRL = regex.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')


def detect(ft):
    """Trả về (set lỗi FIXABLE, set lỗi RE-OCR, có_legacy_trace)."""
    s = ft.strip()
    n = max(len(s), 1)
    fix, reocr = set(), set()

    if len(s) < 150:
        reocr.add("empty")     # trích xuất hỏng (mảnh vụn) — nội dung trong ảnh, cần re-OCR
    if any(0xe000 <= ord(c) <= 0xf8ff for c in ft):
        fix.add("pua")
    if "TÕA" in ft or "HÕA" in ft:
        fix.add("tone_swap")
    if "ƣ" in ft or "Ƣ" in ft:
        fix.add("guoc")
    if "�" in ft or _CTRL.search(ft):
        fix.add("glyph_bad")

    legacy_density = len(utils.LEGACY_SIG.findall(s)) / n
    diacritic_density = len(_UNI.findall(s)) / n
    if legacy_density >= LEGACY_HEAVY:
        reocr.add("legacy_char")
    if diacritic_density < LOW_DENSITY:
        reocr.add("low_density")

    # Mật độ legacy thấp KHÔNG có nghĩa vô hại: doc lẫn mã hoá (thân Unicode sạch
    # + 1 vùng font cũ). Phân theo VỊ TRÍ garble, không theo mật độ:
    #   - chỉ ở letterhead (12% đầu) / chữ ký (8% cuối) = boilerplate → giữ (trace)
    #   - lẫn trong thân (12-92%) = nội dung có giá trị bị hỏng → cần re-OCR
    legacy_trace = False
    if 0 < legacy_density < LEGACY_HEAVY:
        in_body = any(0.12 <= m.start() / n <= 0.92
                      for m in utils.LEGACY_SIG.finditer(s))
        if in_body:
            reocr.add("legacy_body")
        else:
            legacy_trace = True
    return fix, reocr, legacy_trace


def main(write_list=False):
    files = [f for f in os.listdir(PROCESSED) if f.endswith(".json")]
    from collections import Counter
    fix_c, reocr_c = Counter(), Counter()
    trace = clean = 0
    reocr_files = []
    for fn in files:
        try:
            ft = json.load(open(os.path.join(PROCESSED, fn), encoding="utf-8")).get("full_text", "")
        except Exception:
            continue
        fix, reocr, tr = detect(ft)
        for e in fix:
            fix_c[e] += 1
        for e in reocr:
            reocr_c[e] += 1
        if reocr:
            reocr_files.append(fn)
        elif fix:
            pass
        elif tr:
            trace += 1
        else:
            clean += 1

    n = len(files)
    print(f"=== DETECT ERRORS: {n} doc ===\n")
    print("FIXABLE (đáng lẽ ~0):")
    for e in ("pua", "tone_swap", "guoc", "glyph_bad"):
        print(f"  {e:12} {fix_c[e]}")
    print("\nRE-OCR (defer — cần Surya đọc lại):")
    for e in ("empty", "legacy_char", "low_density", "legacy_body"):
        print(f"  {e:12} {reocr_c[e]}")
    print(f"  → tổng doc cần re-OCR: {len(reocr_files)} ({len(reocr_files)*100//n}%)")
    print(f"\nMINOR (legacy chỉ ở letterhead/chữ ký, giữ): {trace}")
    print(f"SẠCH hoàn toàn: {clean} ({clean*100//n}%)")

    if write_list:
        p = os.path.join(PROCESSED, "needs_reocr.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(sorted(reocr_files)))
        print(f"\n→ Ghi {len(reocr_files)} tên file vào {p}")


if __name__ == "__main__":
    main(write_list="--list" in sys.argv)
