"""Re-OCR theo TRANG cho doc lẫn mã hoá còn sót (VNI / legacy nặng / rụng chữ / ảnh).

Dựng lại full_text TỪ PDF GỐC, theo từng trang:
  - trang dính rác font cũ (VNI/TCVN3 không cứu bằng charmap) hoặc trang ẢNH
    -> OCR LẠI trang đó bằng Surya (đọc pixel, không dính bẫy glyph dùng chung);
  - trang Unicode SẠCH -> giữ nguyên text PyMuPDF (rẻ, không đụng GPU).
Median ~1 trang/doc cần OCR, nên chỉ ~25% số trang phải qua GPU.

Tái dùng từ utils: _surya (predictor), render pixmap, _strip_page_num, _standardize,
OCR_DPI, LEGACY_SIG, MIN_PAGE_CHARS. Đọc hàng đợi từ data/processed/needs_reocr.txt;
ghi tiến độ vào reocr_done.log để CHẠY LẠI ĐƯỢC (bỏ qua doc đã xong).

Dùng:
    python reocr.py            # DRY-RUN: đếm trang cần OCR mỗi doc (CPU, KHÔNG OCR)
    python reocr.py --apply    # OCR + ghi đè JSON (GPU, lâu)
    python reocr.py --limit N  # chỉ N doc đầu (để test)
"""
import io
import os
import sys
import json

import pymupdf

import utils

PROCESSED = os.path.join(os.getcwd(), "data", "processed")
PDF_DIR = os.environ.get("LEGAL_DATA", os.path.join(os.getcwd(), "data", "legal-data"))
QUEUE = os.path.join(PROCESSED, "needs_reocr.txt")
DONE_LOG = os.path.join(PROCESSED, "reocr_done.log")

PAGE_LEGACY_DENSITY = 0.005   # trang có mật độ ký tự font cũ ≥ mức này -> OCR lại


def _page_needs_ocr(text, has_image):
    s = text.strip()
    if has_image and len(s) < utils.MIN_PAGE_CHARS:            # trang ảnh (chữ nằm trong ảnh)
        return True
    n = max(len(s), 1)
    return len(utils.LEGACY_SIG.findall(s)) / n >= PAGE_LEGACY_DENSITY  # trang rác font cũ


def plan(doc):
    """Trả về chỉ số các trang cần OCR (không OCR, chỉ CPU)."""
    return [i for i, p in enumerate(doc)
            if _page_needs_ocr(p.get_text(), len(p.get_images()) > 0)]


def reocr_doc(doc, ocr_idx):
    """Dựng lại full_text: OCR các trang trong ocr_idx, giữ PyMuPDF cho phần còn lại."""
    ocr_text = {}
    if ocr_idx:
        from PIL import Image
        det, rec = utils._surya()
        images = [Image.open(io.BytesIO(doc[i].get_pixmap(dpi=utils.OCR_DPI).tobytes('png'))).convert('RGB')
                  for i in ocr_idx]
        results = rec(images, det_predictor=det, math_mode=False)
        for i, r in zip(ocr_idx, results):
            ocr_text[i] = utils._TAGS.sub('', ' '.join(line.text for line in r.text_lines))
    pages = [ocr_text.get(i, p.get_text()) for i, p in enumerate(doc)]
    return utils._standardize('\n'.join(utils._strip_page_num(t) for t in pages))


def main(apply=False, limit=None):
    names = [l.strip() for l in open(QUEUE, encoding="utf-8") if l.strip()] if os.path.exists(QUEUE) else []
    done = set(l.strip() for l in open(DONE_LOG, encoding="utf-8")) if os.path.exists(DONE_LOG) else set()
    todo = [n for n in names if n not in done]
    if limit:
        todo = todo[:limit]

    n_doc = n_pages = n_ocr = 0
    for fn in todo:
        pdf = os.path.join(PDF_DIR, fn.replace(".json", ".pdf"))
        if not os.path.exists(pdf):
            print(f"  ?? thiếu PDF: {fn}", flush=True)
            continue
        try:
            doc = pymupdf.open(pdf)
        except Exception as e:
            print(f"  !! mở lỗi {fn}: {e}", flush=True)
            continue
        idx = plan(doc)
        n_doc += 1
        n_pages += doc.page_count
        n_ocr += len(idx)
        if apply:
            jp = os.path.join(PROCESSED, fn)
            try:
                d = json.load(open(jp, encoding="utf-8"))
            except Exception:
                d = {"filename": fn.replace(".json", ".pdf"), "route": "reocr"}
            d["full_text"] = reocr_doc(doc, idx)
            with open(jp, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
            with open(DONE_LOG, "a", encoding="utf-8") as log:
                log.write(fn + "\n")
            print(f"[{n_doc}/{len(todo)}] {fn} - OCR {len(idx)}/{doc.page_count} trang", flush=True)
        doc.close()

    head = "ĐÃ OCR & GHI" if apply else "DRY-RUN (không OCR)"
    print(f"\n=== {head}: {n_doc} doc · {n_pages} trang tổng · {n_ocr} trang cần OCR "
          f"({n_ocr*100//max(n_pages,1)}%) ===")
    if n_ocr and not apply:
        print(f"→ Ước lượng GPU (~9s/trang, 1 worker): ~{n_ocr*9//3600}h{n_ocr*9%3600//60}m")
        print("→ Chạy lại với --apply để OCR + ghi (an toàn để dừng/chạy lại nhờ reocr_done.log).")


if __name__ == "__main__":
    lim = next((int(a.split("=")[1]) for a in sys.argv if a.startswith("--limit=")), None)
    main(apply="--apply" in sys.argv, limit=lim)
