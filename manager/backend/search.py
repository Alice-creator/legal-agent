"""E3 — Search router (hybrid retrieve) cho app THẨM PHÁN. Tách khỏi router admin.

Luồng: query (text + vector) → dense ANN (HNSW, cosine) + BM25 (tsv) song song →
RRF (k=60) → max-pool về bản án (parent) → trả top doc + snippet.

- Client (app v1) gửi {query, vector}: vector do máy user embed (cùng model AITeamVN).
- Nếu KHÔNG có vector (dev/test): server lazy-load model embed query. Production
  (image nhẹ, không torch) sẽ báo 501 → buộc client gửi vector.
"""
import os
import psycopg
from psycopg.rows import dict_row
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

DSN = os.environ.get("PG_DSN", "postgresql://legal:legal@localhost:5433/legal")
RRF_K = 60
router = APIRouter(prefix="/api/search", tags=["search"])

_model = None


def _embed(text):
    """Lazy-embed query (chỉ dùng dev/test; production thì client gửi vector)."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(os.environ.get("EMBED_MODEL", "AITeamVN/Vietnamese_Embedding"))
        except Exception:
            raise HTTPException(501, "server không có model embed — client phải gửi 'vector'")
    return _model.encode([text], normalize_embeddings=True)[0].tolist()


def _fmt(vec):
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


_SQL = """
WITH dense AS (
  SELECT id, doc_id, row_number() OVER (ORDER BY dist) AS rnk FROM (
    SELECT id, doc_id, embedding <=> %(vec)s::halfvec AS dist
    FROM chunks ORDER BY embedding <=> %(vec)s::halfvec LIMIT %(k)s) t
),
lex AS (
  SELECT id, doc_id, row_number() OVER (ORDER BY score DESC) AS rnk FROM (
    SELECT id, doc_id, ts_rank_cd(tsv, q) AS score
    FROM chunks, websearch_to_tsquery('simple', unaccent(%(q)s)) q
    WHERE tsv @@ q ORDER BY score DESC LIMIT %(k)s) t
),
fused AS (
  SELECT chunk_id, doc_id, sum(s) AS rrf FROM (
    SELECT id AS chunk_id, doc_id, 1.0/(%(rrf)s + rnk) AS s FROM dense
    UNION ALL
    SELECT id, doc_id, 1.0/(%(rrf)s + rnk) FROM lex
  ) u GROUP BY chunk_id, doc_id
),
perdoc AS (   -- max-pool: chunk khớp nhất của mỗi bản án
  SELECT DISTINCT ON (doc_id) doc_id, chunk_id, rrf
  FROM fused ORDER BY doc_id, rrf DESC
)
SELECT p.doc_id, d.filename, d.doc_type, round(p.rrf::numeric, 5) AS score,
       left(regexp_replace(c.chunk_text, E'\\n', ' ', 'g'), 300) AS snippet
FROM perdoc p
JOIN documents d ON d.id = p.doc_id
JOIN chunks    c ON c.id = p.chunk_id
WHERE (%(doc_type)s::text IS NULL OR d.doc_type = %(doc_type)s::text)
ORDER BY p.rrf DESC, p.doc_id     -- tiebreak ổn định khi RRF hòa điểm (eval reproducible)
LIMIT %(top)s;
"""


class SearchReq(BaseModel):
    query: str
    vector: list[float] | None = None   # client-embed; None -> server embed (dev)
    k: int = 60                          # số ứng viên mỗi nhánh (dense/lex)
    top: int = 20                        # số bản án trả về
    doc_type: str | None = None          # lọc: 'ban_an' / 'quyet_dinh' / None=cả hai


@router.post("")
def search(req: SearchReq):
    if not req.query.strip():
        raise HTTPException(400, "query rỗng")
    vec = req.vector if req.vector is not None else _embed(req.query)
    params = {"vec": _fmt(vec), "q": req.query, "k": req.k, "rrf": RRF_K,
              "doc_type": req.doc_type, "top": req.top}
    with psycopg.connect(DSN, row_factory=dict_row) as conn:
        conn.execute("SET LOCAL hnsw.ef_search = 100")
        rows = conn.execute(_SQL, params).fetchall()
    return {"query": req.query, "count": len(rows), "results": rows}
