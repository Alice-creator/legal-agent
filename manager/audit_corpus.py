"""Đo THÀNH PHẦN corpus từ PDF gốc (không cần DB, không cần venv nặng).

Trả lời 2 câu hỏi làm nền cho audit retrieval (xem docs/retrieval_audit.md):
  1. Corpus đồng nhất tới mức nào? (phân bố loại tranh chấp qua dòng "V/v ...")
     -> quyết định thước đo exact-source có ý nghĩa hay không: corpus càng đồng nhất,
        bản án gốc càng lẫn vào hàng nghìn vụ na ná, metric càng đánh giá THẤP giá trị thật.
  2. Bao nhiêu phần index KHÔNG chứa tình tiết/lập luận? (doc chỉ có header QUYẾT ĐỊNH
     = quyết định thủ tục, theo đúng luật doc_type_of() trong chunk.py)
     -> quyết định có nên lọc theo section/doc_type lúc retrieve hay không.

⚠️ THIÊN LỆCH: chỉ đọc được PDF có text-layer (pdftotext). ~15% doc scan bị bỏ qua, mà
doc scan thường là bản án đầy đủ => tỉ lệ 'quyet_dinh' ở đây là ước lượng CAO. Có DB thì
đếm thẳng cho chuẩn:  SELECT doc_type, count(*) FROM documents GROUP BY 1;

Cần: poppler-utils (pdftotext). Không cần torch/psycopg.
Dùng:  python3 manager/audit_corpus.py [số-mẫu]      # mặc định 700, chạy ~20 giây
"""
import os
import re
import sys
import random
import subprocess
import collections
import statistics

PDF_DIR = os.environ.get("LEGAL_DATA", "data")
SEED = 42                      # cố định để chạy lại ra cùng số
MIN_TEXT = 400                 # dưới ngưỡng này coi như không có text-layer (doc scan)

# Header 4 phần của bản án VN. Luật gán nhãn GIỐNG chunk.doc_type_of():
# có NỘI DUNG VỤ ÁN hoặc NHẬN ĐỊNH -> bản án (có tình tiết), ngược lại -> quyết định thủ tục.
_SECTIONS = (("noi_dung", r"NỘI\s+DUNG\s+VỤ\s+ÁN"),
             ("nhan_dinh", r"NHẬN\s+ĐỊNH"),
             ("quyet_dinh", r"\bQUYẾT\s+ĐỊNH\b"))
# Dòng "V/v <loại tranh chấp>" nằm ngay khối đầu bản án, cạnh số bản án.
_VV = re.compile(r"V/v[:\s\"“']*([^\n\"”]{5,90}?)(?:\"|”|$|\s{2,}|NHÂN DANH)", re.I)


def pdf_text(path):
    try:
        out = subprocess.run(["pdftotext", "-q", path, "-"],
                             capture_output=True, timeout=25).stdout
    except Exception:
        return ""
    return out.decode("utf-8", "ignore")


def main(n_sample):
    files = sorted(f for f in os.listdir(PDF_DIR) if f.endswith(".pdf"))
    random.seed(SEED)
    sample = random.sample(files, min(n_sample, len(files)))

    vv = collections.Counter()
    dt = collections.Counter()
    chars = {"ban_an": [], "quyet_dinh": []}
    scanned = 0

    for fn in sample:
        text = pdf_text(os.path.join(PDF_DIR, fn))
        if len(text.strip()) < MIN_TEXT:
            scanned += 1
            continue
        flat = re.sub(r"\s+", " ", text)
        m = _VV.search(flat[:3000])
        vv[re.sub(r"\s+", " ", m.group(1).strip().lower()) if m else "(không thấy V/v)"] += 1
        found = {lbl for lbl, rx in _SECTIONS if re.search(rx, flat, re.I)}
        kind = "ban_an" if found & {"noi_dung", "nhan_dinh"} else "quyet_dinh"
        dt[kind] += 1
        chars[kind].append(len(text.strip()))

    ok = sum(dt.values())
    print(f"mẫu {len(sample)} · có text-layer {ok} · scan/rỗng {scanned} "
          f"({scanned*100/max(len(sample),1):.0f}%, KHÔNG tính vào thống kê dưới)\n")

    print("=== TOP 15 loại tranh chấp ===")
    named = ok - vv["(không thấy V/v)"]
    for k, c in vv.most_common(15):
        base = ok if k.startswith("(") else named
        print(f"{c:5} {c*100/max(base,1):5.1f}%  {k[:70]}")
    print(f"(% tính trên {named} doc CÓ ghi V/v; tổng {len(vv)-1} nhãn khác nhau)\n")

    print("=== doc_type (luật giống chunk.py) ===")
    for k, c in dt.most_common():
        print(f"{k:11} {c:5} doc · {c*100/max(ok,1):5.1f}%")
    total_chars = sum(sum(v) for v in chars.values())
    for k, v in chars.items():
        if v:
            print(f"  {k:11} TB {statistics.mean(v):7.0f} ký tự · p50 {statistics.median(v):7.0f} "
                  f"· chiếm {sum(v)*100/max(total_chars,1):4.1f}% tổng ký tự (≈ % chunk trong index)")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 700)
