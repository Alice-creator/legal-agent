"""E4 (pass 1) — Sinh synthetic query để eval retrieval. Offline trên Mac.

Mỗi query bắt nguồn từ 1 bản án → bản án đó = đáp án đúng (ground truth). Cho LLM
phần tình tiết + nhận định, yêu cầu viết mô tả tranh chấp NGẮN, ẨN DANH (bỏ tên
đương sự/tòa, số bản án, ngày, số tiền) để không "lộ đáp án" cho BM25 — buộc
retrieval phải khớp NGỮ NGHĨA + TÌNH TIẾT, không phải copy chuỗi.

- Nguồn: bucket clean, doc_type ban_an, có section noi_dung. Sample tất định (hash id).
- LLM: ollama cloud (gemma4:31b-cloud). Trả 'SKIP' nếu văn bản chỉ thủ tục.
- Resumable: bỏ qua doc_id đã có trong file out. Song song nhẹ (thread).

Dùng:
    .venv-surya/bin/python manager/eval_gen.py --n 300
"""
import os
import re
import sys
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import psycopg
from ollama import Client

DSN = os.environ.get("PG_DSN", "postgresql://legal:legal@localhost:5433/legal")
MODEL = os.environ.get("EVAL_LLM", "gemma4:31b-cloud")
OUT = os.environ.get("EVAL_QUERIES", "data/processed/eval_queries.jsonl")
MAX_FACTS = 2500   # ký tự facts đưa cho LLM

PROMPT = """Bạn tóm tắt hồ sơ vụ án để thẩm phán đi tìm các bản án TƯƠNG TỰ.
Cho phần TÌNH TIẾT + NHẬN ĐỊNH của một bản án dưới đây, hãy viết một bản tóm tắt
tình tiết (5-8 câu, tiếng Việt) như cách thẩm phán mô tả vụ án trong tay để tra cứu.

GIỮ các CHI TIẾT ĐẶC TRƯNG giúp phân biệt vụ này với các vụ khác cùng loại:
- loại hàng hóa / dịch vụ / tài sản cụ thể (vd: kết cấu thép, bê tông, phụ gia, căn hộ...);
- diễn biến giao dịch + nguyên nhân tranh chấp cụ thể;
- loại tài sản bảo đảm / thế chấp nếu có; các tình tiết bất thường nếu có.

CHỈ LƯỢC BỎ thông tin định danh: tên người / doanh nghiệp / ngân hàng / tòa án,
số bản án, số tiền chính xác, ngày tháng chính xác (có thể nói "một khoản tiền lớn",
"sau vài tháng"...). Diễn đạt LẠI bằng lời của bạn, KHÔNG sao chép nguyên câu.

Nếu văn bản chỉ là thủ tục / không có tranh chấp rõ → trả về đúng một chữ: SKIP
Chỉ in ra bản tóm tắt (hoặc SKIP), không thêm lời dẫn.

--- VĂN BẢN ---
{facts}
--- HẾT ---"""

_local = threading.local()


def _client():
    if not hasattr(_local, "c"):
        key = os.environ.get("OLLAMA_API_KEY")
        _local.c = Client(host="https://ollama.com",
                          headers={"Authorization": f"Bearer {key}"})
    return _local.c


def _load_env():
    """Đọc .env ở repo root nếu OLLAMA_API_KEY chưa có trong môi trường."""
    if os.environ.get("OLLAMA_API_KEY"):
        return
    p = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(p):
        for line in open(p):
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def sample_docs(conn, n, done_ids):
    """n bản án clean có noi_dung, sample tất định (hash) — bỏ doc đã làm."""
    rows = conn.execute("""
        SELECT d.id, d.filename,
               string_agg(ch.chunk_text, ' ' ORDER BY ch.chunk_index) facts
        FROM documents d JOIN chunks ch ON ch.doc_id = d.id
        WHERE d.bucket = 'clean' AND d.doc_type = 'ban_an'
          AND ch.section IN ('noi_dung','nhan_dinh')
        GROUP BY d.id, d.filename
        HAVING length(string_agg(ch.chunk_text,' ')) > 600
        ORDER BY md5(d.id::text || 'e4seed')
        LIMIT %s
    """, (n + len(done_ids) + 200,)).fetchall()
    out = [(i, fn, facts) for (i, fn, facts) in rows if i not in done_ids]
    return out[:n]


def gen_one(doc_id, filename, facts):
    facts = re.sub(r"\s+", " ", facts).strip()[:MAX_FACTS]
    try:
        r = _client().chat(model=MODEL, options={"temperature": 0.7},
                          messages=[{"role": "user", "content": PROMPT.format(facts=facts)}])
        q = r["message"]["content"].strip()
    except Exception as e:
        return {"doc_id": doc_id, "filename": filename, "error": str(e)[:150]}
    if q.upper().startswith("SKIP") or not (30 <= len(q) <= 800):
        return {"doc_id": doc_id, "filename": filename, "skip": True, "raw": q[:120]}
    return {"doc_id": doc_id, "filename": filename, "query": q}


def main(n, workers):
    _load_env()
    if not os.environ.get("OLLAMA_API_KEY"):
        sys.exit("thiếu OLLAMA_API_KEY (.env)")
    done = set()
    if os.path.exists(OUT):
        for line in open(OUT):
            try:
                done.add(json.loads(line)["doc_id"])
            except Exception:
                pass
    conn = psycopg.connect(DSN)
    docs = sample_docs(conn, n, done)
    print(f"sinh {len(docs)} query (đã có {len(done)}), model={MODEL}, workers={workers}", flush=True)

    kept = skipped = errored = 0
    lock = threading.Lock()
    with open(OUT, "a") as f, ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(gen_one, i, fn, facts) for (i, fn, facts) in docs]
        for k, fut in enumerate(as_completed(futs), 1):
            rec = fut.result()
            with lock:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
            if rec.get("query"):
                kept += 1
            elif rec.get("skip"):
                skipped += 1
            else:
                errored += 1
            if k % 20 == 0 or k == len(futs):
                print(f"  {k}/{len(futs)} · giữ {kept} · skip {skipped} · lỗi {errored}", flush=True)
    print(f"XONG → {OUT} · giữ {kept} query dùng được.", flush=True)


if __name__ == "__main__":
    n = 300
    workers = 6
    for a in sys.argv:
        if a.startswith("--n="):
            n = int(a.split("=")[1])
        elif a.startswith("--workers="):
            workers = int(a.split("=")[1])
    if "--n" in sys.argv:
        n = int(sys.argv[sys.argv.index("--n") + 1])
    main(n, workers)
