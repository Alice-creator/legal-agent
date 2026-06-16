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
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

ANSWER_MODEL = os.environ.get("ANSWER_MODEL", "qwen2.5:14b")

DSN = os.environ.get("PG_DSN", "postgresql://legal:legal@localhost:5433/legal")
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


# --- Sinh câu trả lời tự nhiên (RAG generation) ---
# DEV PROTOTYPE: endpoint này gọi LOCAL ollama để demo UX. PRODUCTION: app Tauri tự
# gọi ollama TẠI MÁY USER (server 16GB no-GPU KHÔNG chạy LLM) — prompt + luồng y hệt.
# Luật nhạy cảm → prompt ràng buộc CHỈ-dựa-trích-dẫn, bắt buộc dẫn nguồn, cấm bịa.
_SYSTEM = """Bạn là trợ lý tra cứu án lệ cho thẩm phán Việt Nam. Người dùng đưa TÌNH TIẾT vụ đang xử và một số ĐOẠN TRÍCH từ các bản án/quyết định tương tự đã tìm được (đánh số [1], [2]...).

Nhiệm vụ: tóm tắt NGẮN GỌN (tiếng Việt) các vụ tìm được liên quan thế nào tới vụ đang xử — điểm CHUNG và KHÁC BIỆT về quan hệ pháp luật tranh chấp và hướng giải quyết — để thẩm phán THAM KHẢO.

QUY TẮC BẮT BUỘC (luật là lĩnh vực nhạy cảm):
1. CHỈ dùng thông tin có trong các đoạn trích. TUYỆT ĐỐI KHÔNG bịa tình tiết, số liệu, tên, điều luật, hay kết quả xử không xuất hiện trong trích dẫn.
2. Mỗi nhận định phải DẪN NGUỒN [số] tương ứng.
3. Nếu các đoạn trích KHÔNG đủ để kết luận → nói rõ "cần đọc bản án đầy đủ", đừng đoán.
4. KHÔNG đưa ra phán quyết hay lời khuyên pháp lý. Đây chỉ là tóm tắt tham khảo; thẩm phán phải tự đọc bản án gốc."""


class AnswerReq(BaseModel):
    query: str
    contexts: list[dict] = []   # [{n, name, chunk}] — các nguồn từ /api/search


@router.post("/answer")
def answer(req: AnswerReq):
    try:
        import ollama
        client = ollama.Client()   # localhost:11434
    except Exception:
        raise HTTPException(501, "không có ollama local (dev-only). Production: client tự sinh.")
    ctx = "\n\n".join(f"[{c.get('n')}] {c.get('name')}:\n{c.get('chunk', '')}"
                      for c in req.contexts)
    msgs = [{"role": "system", "content": _SYSTEM},
            {"role": "user", "content":
             f"TÌNH TIẾT VỤ ĐANG XỬ:\n{req.query}\n\nCÁC BẢN ÁN/QUYẾT ĐỊNH TƯƠNG TỰ:\n{ctx}"}]

    def gen():
        for part in client.chat(model=ANSWER_MODEL, messages=msgs, stream=True):
            yield part["message"]["content"]

    return StreamingResponse(gen(), media_type="text/plain; charset=utf-8")
