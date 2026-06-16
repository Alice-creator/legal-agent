"""Search router (dense-primary) cho app THẨM PHÁN. Tách khỏi router admin.

Luồng: query (vector) → dense ANN (HNSW, cosine) → max-pool về bản án (chunk gần
nhất mỗi doc) → top-N bản án + snippet.

Vì sao DENSE-ONLY (không hybrid BM25): E4 eval (n=308 synthetic query) cho thấy
hybrid ≈ dense (chênh ≤0.026, trong nhiễu ±0.027), BM25 một mình gần vô dụng
(nDCG 0.026). Với query diễn-giải tình tiết, embedding mang gần hết tín hiệu;
ts_rank của Postgres (không IDF, tách âm tiết tiếng Việt) chỉ thêm nhiễu. Bỏ lexical
cho gọn. Nếu sau này cần exact-match query NGẮN (Điều X, tên riêng) thì thêm lại
BM25 TỬ TẾ (word-level + IDF), không phải hack đếm âm tiết. Xem journal Phiên 2.

- Client (app v1) gửi {query, vector}: vector do máy user embed (cùng model AITeamVN).
- Thiếu vector (dev/test): server lazy-load model. Production (image nhẹ, không torch)
  sẽ báo 501 → buộc client gửi vector.
"""
import os
import psycopg
from psycopg.rows import dict_row
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

DSN = os.environ.get("PG_DSN", "postgresql://legal:legal@localhost:5433/legal")
router = APIRouter(prefix="/api/search", tags=["search"])

_model = None


def load_model():
    """Nạp + warm model embed. Gọi lúc STARTUP (lifespan) để request đầu không phải
    chờ ~30-40s. Raise nếu sentence-transformers không có (image nhẹ không torch)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        m = SentenceTransformer(os.environ.get("EMBED_MODEL", "AITeamVN/Vietnamese_Embedding"))
        m.encode(["khởi động"], normalize_embeddings=True)   # warm graph
        _model = m
    return _model


def _embed(text):
    try:
        m = load_model()
    except Exception:
        raise HTTPException(501, "server không có model embed — client phải gửi 'vector'")
    return m.encode([text], normalize_embeddings=True)[0].tolist()


def _fmt(vec):
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


_SQL = """
WITH dense AS (
  SELECT id, doc_id, embedding <=> %(vec)s::halfvec AS dist
  FROM chunks ORDER BY embedding <=> %(vec)s::halfvec LIMIT %(cand)s
),
perdoc AS (   -- max-pool: chunk gần nhất của mỗi bản án
  SELECT DISTINCT ON (doc_id) doc_id, id AS chunk_id, dist
  FROM dense ORDER BY doc_id, dist ASC
)
SELECT p.doc_id, d.filename, d.doc_type,
       round((1 - p.dist)::numeric, 4) AS score,   -- cosine similarity
       regexp_replace(c.chunk_text, E'\\n', ' ', 'g') AS chunk   -- chunk khớp (full, cho LLM + preview)
FROM perdoc p
JOIN documents d ON d.id = p.doc_id
JOIN chunks    c ON c.id = p.chunk_id
WHERE (%(doc_type)s::text IS NULL OR d.doc_type = %(doc_type)s::text)
ORDER BY p.dist ASC
LIMIT %(top)s;
"""


class SearchReq(BaseModel):
    query: str
    vector: list[float] | None = None   # client-embed; None -> server embed (dev)
    top: int = 20                        # số bản án trả về
    doc_type: str | None = None          # lọc: 'ban_an' / 'quyet_dinh' / None=cả hai


@router.post("")
def search(req: SearchReq):
    if not req.query.strip():
        raise HTTPException(400, "query rỗng")
    vec = req.vector if req.vector is not None else _embed(req.query)
    cand = max(200, req.top * 12)        # đủ chunk để max-pool ra >= top doc riêng
    params = {"vec": _fmt(vec), "cand": cand, "doc_type": req.doc_type, "top": req.top}
    with psycopg.connect(DSN, row_factory=dict_row) as conn:
        conn.execute(f"SET LOCAL hnsw.ef_search = {max(100, cand)}")
        rows = conn.execute(_SQL, params).fetchall()
    return {"query": req.query, "count": len(rows), "results": rows}

# Sinh câu trả lời (RAG generation) KHÔNG ở server: app tự gọi Gemini bằng key của
# user (lưu máy user). Server chỉ dense-retrieve, không đụng LLM/key. Xem frontend.
