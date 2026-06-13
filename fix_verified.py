"""Sửa per-doc đã XÁC MINH tận trang PDF gốc (ground-truth bằng mắt).

Khác fix_legacy.py (sửa hàng loạt các pattern an toàn): file này chứa các sửa
ĐÍCH DANH từng doc, mỗi sửa đã render đúng trang PDF + đọc tận mắt rồi chép lại
chữ đúng. Dùng cho số ít doc 99.9% sạch chỉ dính 1 vùng hỏng — re-OCR cả doc sẽ
hại nhiều hơn (đổi text-layer chính xác lấy lỗi OCR mới), nên vá thẳng vùng đó.

Mỗi mục: (filename, chuỗi_rác, chuỗi_đúng, "vì sao tin được").
Idempotent: chỉ thay khi còn chuỗi rác. Dùng:
    python fix_verified.py            # DRY-RUN
    python fix_verified.py --apply
"""
import os
import sys
import json
import unicodedata

PROCESSED = os.path.join(os.getcwd(), "data", "processed")

# (file, rác, đúng, lý do)
CORRECTIONS = [
    (
        "KD-T2-L6-V3-424814.json",
        "Cùng đa ch:",
        "Cùng địa chỉ:",
        # PDF trang 2/2: 2 glyph 'ị','ỉ' không có ToUnicode -> \x00 (đã strip).
        # Dòng in rõ 'Cùng địa chỉ: Tổ 16, ấp 4...', ngay trên là 'Địa chỉ: 95A/6...'.
        "render trang 2: 'Cùng địa chỉ: Tổ 16, ấp 4, xã F1...'",
    ),
    (
        "KD-T1-L11-V3-166905.json",
        "Toµ ¸n nh©n d©n céng hoµ x· héi chñ nghÜa viÖt nam\n"
        "TØnh b¾c giang §éc lËp - Tù do- H¹nh phóc\n\nbiªn b¶n nghÞ ¸n\n",
        "Toà án nhân dân cộng hoà xã hội chủ nghĩa việt nam\n"
        "Tỉnh bắc giang Độc lập - Tự do - Hạnh phúc\n\nbiên bản nghị án\n",
        # PDF trang 8/12: header trang 'biên bản nghị án' in font TCVN3 (.VnTime)
        # không nhúng -> cả extract lẫn render đều fallback ra rác. Nội dung là
        # boilerplate hành chính chuẩn (không thể nhầm); giữ nguyên hoa/thường +
        # xuống dòng như bản gốc, chỉ decode đúng ký tự.
        "render trang 8: header 'biên bản nghị án' + quốc hiệu (TCVN3 không nhúng)",
    ),
]


def main(apply=False):
    head = "ĐÃ SỬA & GHI" if apply else "DRY-RUN (chưa ghi)"
    print(f"=== {head} ===")
    for fn, bad, good, why in CORRECTIONS:
        p = os.path.join(PROCESSED, fn)
        d = json.load(open(p, encoding="utf-8"))
        ft = d["full_text"]
        if bad not in ft:
            print(f"\n{fn}: (đã sạch / không thấy chuỗi rác — bỏ qua)")
            continue
        fixed = unicodedata.normalize("NFC", ft.replace(bad, good))
        print(f"\n{fn}  [{why}]")
        print("  rác :", repr(bad[:60]))
        print("  đúng:", repr(good[:60]))
        if apply:
            d["full_text"] = fixed
            with open(p, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
    if not apply:
        print("\n→ Chạy lại với --apply để ghi.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
