"""E1 — Tách section + chunk ĐỀU (~450 token) các doc sạch vào bảng chunks.

Chiến thuật (xem rag_research.html):
  - Tầng SECTION: regex header (NỘI DUNG VỤ ÁN / NHẬN ĐỊNH / QUYẾT ĐỊNH) chỉ để
    (a) tag doc_type (ban_an nếu có tình tiết/nhận-định, else quyet_dinh),
    (b) gắn nhãn section cho mỗi chunk, (c) không cho chunk vắt ngang 2 section.
  - Tầng CHUNK: gói các ĐOẠN (\n) tới ~TARGET token, overlap ~OVERLAP token →
    chunk ĐỀU (không phụ thuộc độ dài section). Đoạn khổng lồ thì hard-split theo token.
  - embedding để NULL (điền ở E2). tsv = to_tsvector('simple', unaccent(chunk_text)).

Chỉ xử doc bucket clean/minor (bỏ reocr — rác OCR). Idempotent: TRUNCATE chunks rồi dựng lại.
Dùng:  .venv-surya/bin/python manager/chunk.py            # DRY-RUN (thống kê, không ghi)
       .venv-surya/bin/python manager/chunk.py --apply
"""
import os
import sys
import statistics
import regex
import psycopg
from transformers import AutoTokenizer

DSN = os.environ.get("PG_DSN", "postgresql://legal:legal@localhost:5433/legal")
MODEL = os.environ.get("EMBED_MODEL", "AITeamVN/Vietnamese_Embedding")
TARGET, OVERLAP, MIN_CHUNK = 450, 67, 40

_H = [("noi_dung", regex.compile(r"NỘI\s+DUNG\s+VỤ\s+ÁN", regex.I)),
      ("nhan_dinh", regex.compile(r"NHẬN\s+ĐỊNH", regex.I)),
      ("quyet_dinh", regex.compile(r"\bQUYẾT\s+ĐỊNH\b", regex.I))]


def split_sections(text):
    """[(label, segment_text)] theo header; nếu không có header -> [('full', text)]."""
    marks = sorted((m.start(), lbl) for lbl, rx in _H for m in [rx.search(text)] if m)
    if not marks:
        return [("full", text)]
    segs = []
    if marks[0][0] > 0:
        segs.append(("opening", text[:marks[0][0]]))
    for i, (pos, lbl) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        segs.append((lbl, text[pos:end]))
    return segs


def doc_type_of(text):
    return "ban_an" if (_H[0][1].search(text) or _H[1][1].search(text)) else "quyet_dinh"


def _hardsplit(paras_ids, paras, tok):
    """Đoạn > TARGET: cắt cứng theo cửa sổ token (hiếm)."""
    out = []
    ids = paras_ids
    i = 0
    while i < len(ids):
        j = min(i + TARGET, len(ids))
        out.append(tok.decode(ids[i:j]).strip())
        if j >= len(ids):
            break
        i = j - OVERLAP
    return out


def chunk_section(seg, tok):
    paras = [p for p in regex.split(r"\n+", seg) if p.strip()]
    if not paras:
        return []
    counts = [len(x) for x in tok(paras, add_special_tokens=False)["input_ids"]]
    chunks, cur, cur_t = [], [], 0
    for p, c in zip(paras, counts):
        if c > TARGET:                                   # đoạn khổng lồ
            if cur:
                chunks.append("\n".join(cur)); cur, cur_t = [], 0
            ids = tok(p, add_special_tokens=False)["input_ids"]
            chunks += _hardsplit(ids, p, tok)
            continue
        if cur_t + c > TARGET and cur:                   # đóng chunk + overlap
            chunks.append("\n".join(cur))
            # overlap: giữ các đoạn cuối tổng <= OVERLAP token
            keep, kt = [], 0
            for q in reversed(cur):
                qc = len(tok(q, add_special_tokens=False)["input_ids"])
                if kt + qc > OVERLAP:
                    break
                keep.insert(0, q); kt += qc
            cur, cur_t = keep[:], kt
        cur.append(p); cur_t += c
    if cur:
        chunks.append("\n".join(cur))
    return [c.strip() for c in chunks if c.strip()]


_SQL = ("INSERT INTO chunks (doc_id, section, chunk_index, chunk_text, tsv) "
        "VALUES (%s,%s,%s,%s, to_tsvector('simple', unaccent(%s)))")


def main(apply=False):
    tok = AutoTokenizer.from_pretrained(MODEL, use_fast=True)
    conn = psycopg.connect(DSN)
    docs = conn.execute("SELECT id, full_text FROM documents "
                        "WHERE bucket IN ('clean','minor') ORDER BY id").fetchall()
    print(f"Doc clean/minor: {len(docs)} · model {MODEL} · target {TARGET}/overlap {OVERLAP}")
    if apply:
        conn.execute("TRUNCATE chunks RESTART IDENTITY")
        conn.commit()

    from collections import Counter
    dt = Counter(); chunk_lens = []; n_chunks = 0; rows = []
    for did, ft in docs:
        ft = (ft or "").strip()
        if not ft:
            continue
        dtype = doc_type_of(ft)
        dt[dtype] += 1
        # gom chunk mọi section, kèm token-len
        raw = []
        for label, seg in split_sections(ft):
            for ch in chunk_section(seg, tok):
                raw.append((label, ch, len(tok(ch, add_special_tokens=False)["input_ids"])))
        # gộp chunk nhỏ (<MIN_CHUNK) vào chunk trước (tránh chunk tí hon do header lẻ)
        merged = []
        for label, ch, tl in raw:
            if merged and tl < MIN_CHUNK:
                pl, pt, ptl = merged[-1]
                merged[-1] = (pl, pt + "\n" + ch, ptl + tl)
            else:
                merged.append((label, ch, tl))
        for idx, (label, ch, tl) in enumerate(merged):
            n_chunks += 1
            chunk_lens.append(tl)
            rows.append((did, label, idx, ch, ch))
        if apply:
            conn.execute("UPDATE documents SET doc_type=%s WHERE id=%s", (dtype, did))
            if len(rows) >= 2000:
                conn.cursor().executemany(_SQL, rows); conn.commit(); rows = []
    if apply and rows:
        conn.cursor().executemany(_SQL, rows); conn.commit()

    L = chunk_lens
    print(f"\ndoc_type: {dict(dt)}")
    print(f"chunks: {n_chunks} · {n_chunks/max(sum(dt.values()),1):.1f} chunk/doc")
    print(f"token/chunk — mean {statistics.mean(L):.0f} · p50 {statistics.median(L):.0f} · "
          f"p90 {sorted(L)[int(len(L)*0.9)]} · min {min(L)} · max {max(L)}")
    print(("ĐÃ GHI vào chunks." if apply else "DRY-RUN — chạy --apply để ghi."))


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
