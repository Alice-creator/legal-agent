"""Sửa rác font cũ ở mức AN TOÀN trên full_text đã trích (retro-fix các JSON).

CHỈ sửa những thứ KHÔNG nhập nhằng với chữ tiếng Việt hợp lệ:
  1. ƣ/Ƣ -> ư/Ư   — ƣ không phải chữ tiếng Việt, luôn là lỗi font (vd "đƣơng"->"đương").
  2. dấu thanh mồ côi bị tách rời bởi khoảng trắng: "Bô ̣ luâ ̣t" -> "Bộ luật"
     (gắn combining mark về nguyên âm liền trước rồi NFC).

KHÔNG làm charmap TCVN3/VNI đầy đủ ở đây: các byte font cũ ánh xạ ra é/ó/ù/à...
— vốn CŨNG là chữ tiếng Việt hợp lệ. Ở mức văn bản thuần không thể phân biệt 'é'
rác (cần -> ộ) với 'é' thật ('khoé', 'bé') -> blanket-map sẽ corrupt chữ đúng.
Sửa trọn vẹn cần đọc lại PDF + nhận diện font theo từng span (xem nhật ký nghiên cứu).

Dùng:
    python fix_legacy.py            # DRY-RUN: chỉ báo cáo, không ghi
    python fix_legacy.py --apply    # ghi đè các JSON đã sửa
"""
import os
import sys
import json
import unicodedata
import regex

PROCESSED = os.path.join(os.getcwd(), "data", "processed")

# 5 dấu thanh tiếng Việt dạng combining (huyền sắc ngã hỏi nặng)
_COMBINING = "̣̀́̃̉"
_orphan = regex.compile(r"(\S) +([" + _COMBINING + r"])")   # ký tự + space(s) + dấu mồ côi


# (3) Lỗi cmap font tiêu đề: glyph "ò" map nhầm sang codepoint "õ" (chỉ ở tiêu đề
# in hoa). CHỈ thay đúng chuỗi không-bao-giờ-hợp-lệ; KHÔNG blanket õ->ò vì 'õ' là chữ
# tiếng Việt thật ('ngõ', 'võ', 'rõ').
_TITLE_TONE = {"TÕA": "TÒA", "HÕA": "HÒA", "Tõa": "Tòa", "Hõa": "Hòa"}


def fix(text):
    t = text.replace("ƣ", "ư").replace("Ƣ", "Ư")   # (1) ƣ luôn là ư
    t = _orphan.sub(r"\1\2", t)                      # (2) kéo dấu mồ côi về sát nguyên âm
    for bad, good in _TITLE_TONE.items():            # (3) TÕA->TÒA, HÕA->HÒA (title)
        t = t.replace(bad, good)
    t = "".join(c for c in t if not (0xe000 <= ord(c) <= 0xf8ff))  # (4) bỏ ký tự PUA (glyph chữ-ký/symbol)
    t = regex.sub(r"\n{3,}", "\n\n", t)              # dọn dòng trống do bỏ block chữ-ký
    return unicodedata.normalize("NFC", t)           # rồi gộp precomposed


def main(apply=False):
    files = [f for f in os.listdir(PROCESSED) if f.endswith(".json")]
    changed = 0
    samples = []
    for fn in files:
        p = os.path.join(PROCESSED, fn)
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        ft = d.get("full_text", "")
        fixed = fix(ft)
        if fixed == ft:
            continue
        changed += 1
        if len(samples) < 6:
            i = next((k for k in range(min(len(ft), len(fixed))) if ft[k] != fixed[k]), 0)
            samples.append((fn, ft[max(0, i - 18):i + 18], fixed[max(0, i - 18):i + 18]))
        if apply:
            d["full_text"] = fixed
            with open(p, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)

    head = "ĐÃ SỬA & GHI" if apply else "DRY-RUN (chưa ghi)"
    print(f"=== {head}: {changed}/{len(files)} JSON thay đổi ===")
    for fn, before, after in samples:
        print(f"\n{fn}")
        print("  trước:", repr(before))
        print("  sau  :", repr(after))
    if changed and not apply:
        print("\n→ Chạy lại với --apply để ghi đè.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
