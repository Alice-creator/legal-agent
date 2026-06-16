"""E4 (pass 1) — Chạy eval retrieval trên index hiện có. Offline (Mac/MPS).

Mỗi query có 1 đáp án đúng = bản án gốc (doc_id). Đo bản án gốc xếp hạng bao nhiêu
khi retrieve sâu (top-100 doc) ở 3 mode: hybrid (RRF dense+BM25) / dense-only /
bm25-only. Metrics tự tính (1 relevant/query, binary):
  nDCG@10 = 1/log2(r+1) nếu r<=10; Recall@k = 1 nếu r<=k; MRR = 1/r; Hit@100.

Lưu ý phương pháp: chỉ tính bản án GỐC là relevant (under-estimate — các án tương
tự khác không được tính công), nên con số tuyệt đối là cận DƯỚI; dùng để SO mode/
model là chính. Synthetic query hơi lạc quan → bổ sung gold set người-duyệt khi chốt.

Dùng:
    .venv-surya/bin/python manager/eval_run.py            # dùng eval_queries.jsonl
    .venv-surya/bin/python manager/eval_run.py --queries data/processed/eval_pilot.jsonl
"""
import os
import re
import sys
import json
import math

import psycopg
from sentence_transformers import SentenceTransformer


import unicodedata

_DF = None


def _load_df():
    global _DF
    if _DF is None:
        p = "data/processed/term_df.json"
        _DF = json.load(open(p)) if os.path.exists(p) else {}
    return _DF


def _unaccent(s):
    """Khớp unaccent của Postgres cho tiếng Việt (đ→d + bỏ dấu)."""
    s = s.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def or_tsquery(text, k=10, df_max=40000):
    """Query dài → OR top-K token HIẾM nhất (IDF cao). AND (websearch/plainto) khớp
    rỗng (không doc nào chứa đủ ~80 từ); OR-tất-cả khớp gần cả corpus → ts_rank_cd
    cực chậm + nhiễu. Chỉ giữ từ hiếm = phân biệt vụ + nhanh. Token unaccent khớp tsv."""
    df = _load_df()
    seen, cand = set(), []
    for raw in re.findall(r"\w+", text.lower(), re.UNICODE):
        lex = _unaccent(raw)
        if len(lex) < 2 or lex in seen:
            continue
        seen.add(lex)
        d = df.get(lex)
        if d is not None:               # bỏ token ngoài corpus
            cand.append((lex, d))
    sel = [t for t in cand if t[1] <= df_max] or cand
    sel.sort(key=lambda x: x[1])        # hiếm nhất trước
    return " | ".join(lex for lex, _ in sel[:k]) or "x"

DSN = os.environ.get("PG_DSN", "postgresql://legal:legal@localhost:5433/legal")
MODEL = os.environ.get("EMBED_MODEL", "AITeamVN/Vietnamese_Embedding")
CAND = int(os.environ.get("EVAL_CAND", "500"))      # ứng viên chunk mỗi nhánh
TOPDOCS = int(os.environ.get("EVAL_TOPDOCS", "100"))  # độ sâu xếp hạng doc
EF = int(os.environ.get("EVAL_EFSEARCH", "500"))     # HNSW ef_search (recall sâu cho eval)
RRF_K = 60

_DENSE = """
WITH dense AS (
  SELECT doc_id, embedding <=> %(vec)s::halfvec AS dist
  FROM chunks ORDER BY embedding <=> %(vec)s::halfvec LIMIT %(cand)s)
SELECT doc_id FROM (SELECT doc_id, min(dist) d FROM dense GROUP BY doc_id) p
ORDER BY d ASC LIMIT %(top)s
"""

_BM25 = """
WITH lex AS (
  SELECT doc_id, ts_rank_cd(tsv, q) AS s
  FROM chunks, to_tsquery('simple', unaccent(%(tsq)s)) q
  WHERE tsv @@ q ORDER BY s DESC LIMIT %(cand)s)
SELECT doc_id FROM (SELECT doc_id, max(s) s FROM lex GROUP BY doc_id) p
ORDER BY s DESC LIMIT %(top)s
"""

# hybrid = đúng logic search.py: RRF theo chunk → max-pool về doc
_HYBRID = """
WITH dense AS (
  SELECT id, doc_id, row_number() OVER (ORDER BY dist) AS rnk FROM (
    SELECT id, doc_id, embedding <=> %(vec)s::halfvec AS dist
    FROM chunks ORDER BY embedding <=> %(vec)s::halfvec LIMIT %(cand)s) t),
lex AS (
  SELECT id, doc_id, row_number() OVER (ORDER BY s DESC) AS rnk FROM (
    SELECT id, doc_id, ts_rank_cd(tsv, q) AS s
    FROM chunks, to_tsquery('simple', unaccent(%(tsq)s)) q
    WHERE tsv @@ q ORDER BY s DESC LIMIT %(cand)s) t),
fused AS (
  SELECT chunk_id, doc_id, sum(sc) AS rrf FROM (
    SELECT id AS chunk_id, doc_id, 1.0/(%(rrf)s + rnk) AS sc FROM dense
    UNION ALL SELECT id, doc_id, 1.0/(%(rrf)s + rnk) FROM lex) u
  GROUP BY chunk_id, doc_id),
perdoc AS (SELECT DISTINCT ON (doc_id) doc_id, rrf FROM fused ORDER BY doc_id, rrf DESC)
SELECT doc_id FROM perdoc ORDER BY rrf DESC, doc_id LIMIT %(top)s
"""

MODES = {"hybrid": _HYBRID, "dense": _DENSE, "bm25": _BM25}


def rank_of(conn, sql, params, source_id):
    rows = conn.execute(sql, params).fetchall()
    for i, (doc_id,) in enumerate(rows, 1):
        if doc_id == source_id:
            return i
    return None


def metrics(ranks):
    """ranks: list[int|None]. Trả dict metric trung bình."""
    n = len(ranks)
    ndcg = sum((1.0 / math.log2(r + 1)) for r in ranks if r and r <= 10) / n
    mrr = sum((1.0 / r) for r in ranks if r) / n
    out = {"nDCG@10": ndcg, "MRR": mrr}
    for k in (1, 5, 10, 20, 50):
        out[f"R@{k}"] = sum(1 for r in ranks if r and r <= k) / n
    out["Hit@100"] = sum(1 for r in ranks if r) / n
    return out


def main(qfile):
    queries = []
    for line in open(qfile):
        r = json.loads(line)
        if r.get("query"):
            queries.append((r["doc_id"], r["query"]))
    if not queries:
        sys.exit(f"không có query trong {qfile}")
    print(f"{len(queries)} query · embed bằng {MODEL} (MPS)...", flush=True)

    m = SentenceTransformer(MODEL, device="mps")
    vecs = m.encode([q for _, q in queries], batch_size=64,
                    normalize_embeddings=True, show_progress_bar=False)

    conn = psycopg.connect(DSN)
    conn.execute(f"SET hnsw.ef_search = {EF}")
    ranks = {mode: [] for mode in MODES}
    for k, ((src, qtext), vec) in enumerate(zip(queries, vecs), 1):
        vs = "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
        params = {"vec": vs, "tsq": or_tsquery(qtext), "cand": CAND, "top": TOPDOCS, "rrf": RRF_K}
        for mode, sql in MODES.items():
            ranks[mode].append(rank_of(conn, sql, params, src))
        if k % 25 == 0 or k == len(queries):
            print(f"  {k}/{len(queries)}", flush=True)

    cols = ["nDCG@10", "MRR", "R@1", "R@5", "R@10", "R@20", "R@50", "Hit@100"]
    print(f"\n=== KẾT QUẢ (n={len(queries)}, cand={CAND}, topdocs={TOPDOCS}, ef={EF}) ===")
    print(f"{'mode':<8}" + "".join(f"{c:>9}" for c in cols))
    results = {}
    for mode in MODES:
        mt = metrics(ranks[mode])
        results[mode] = mt
        print(f"{mode:<8}" + "".join(f"{mt[c]:>9.3f}" for c in cols))

    outp = "data/processed/eval_results.json"
    json.dump({"n": len(queries), "cand": CAND, "ef": EF, "results": results},
              open(outp, "w"), ensure_ascii=False, indent=2)
    print(f"\n→ {outp}")


if __name__ == "__main__":
    qf = os.environ.get("EVAL_QUERIES", "data/processed/eval_queries.jsonl")
    if "--queries" in sys.argv:
        qf = sys.argv[sys.argv.index("--queries") + 1]
    main(qf)
