"""Backend FastAPI cho phần mềm quản lý corpus.

Đọc/ghi bảng documents (Postgres). Tái dùng:
  - ingest.classify  -> phân loại lại bucket sau khi sửa/reprocess
  - legacy_decode + vni_decode -> "xử lý lại" doc ($0 charmap, không GPU)

Chạy (từ thư mục repo root):
  .venv-surya/bin/uvicorn manager.backend.main:app --reload --port 8000
"""
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
os.chdir(REPO)                                   # để legacy_decode/utils đọc data/ đúng
sys.path.insert(0, REPO)                          # utils, legacy_decode, vni_decode
sys.path.insert(0, os.path.join(REPO, "manager"))  # ingest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # search router

import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import ingest                       # classify()
import legacy_decode, vni_decode    # fix_text()

DSN = os.environ.get("PG_DSN", "postgresql://legal:legal@localhost:5433/legal")
PDF_DIR = os.path.join(REPO, "data", "legal-data")

app = FastAPI(title="Legal Corpus Manager")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

from search import router as search_router   # E3: hybrid search (app thẩm phán)
app.include_router(search_router)


def _q(sql, params=(), one=False, write=False):
    with psycopg.connect(DSN, row_factory=dict_row) as conn:
        cur = conn.execute(sql, params)
        if write:
            conn.commit()
            return None
        return cur.fetchone() if one else cur.fetchall()


def _reclassify_sql(text):
    """Trả (set-clause params) để cập nhật full_text + các trường dẫn xuất + tsv."""
    bucket, reason, legd, diac = ingest.classify(text)
    return (text, bucket, reason, round(legd, 5), round(diac, 5), len(text.strip()), text)


_UPDATE = """UPDATE documents SET full_text=%s, bucket=%s, reocr_reason=%s,
  legacy_density=%s, diacritic_density=%s, char_count=%s,
  tsv=to_tsvector('simple', unaccent(%s)), updated_at=now() WHERE id=%s"""


@app.get("/health")
def health():
    """Liveness + DB ping cho load-balancer / CI. 200 nếu DB ok, 503 nếu không."""
    try:
        _q("SELECT 1", one=True)
        return {"status": "ok", "db": "ok"}
    except Exception as ex:
        raise HTTPException(503, f"db down: {str(ex)[:150]}")


@app.get("/api/stats")
def stats():
    return {
        "total": _q("SELECT count(*) n FROM documents", one=True)["n"],
        "buckets": _q("SELECT bucket, count(*) n FROM documents GROUP BY bucket ORDER BY 2 DESC"),
        "routes": _q("SELECT route, count(*) n FROM documents GROUP BY route ORDER BY 2 DESC"),
        "reocr_reasons": _q("SELECT reocr_reason, count(*) n FROM documents "
                            "WHERE bucket='reocr' GROUP BY reocr_reason ORDER BY 2 DESC"),
    }


@app.get("/api/docs")
def list_docs(bucket: str | None = None, route: str | None = None,
              q: str | None = Query(None), page: int = 1, page_size: int = 50):
    where, params = [], []
    if bucket:
        where.append("bucket=%s"); params.append(bucket)
    if route:
        where.append("route=%s"); params.append(route)
    if q:
        where.append("(tsv @@ websearch_to_tsquery('simple', unaccent(%s)) OR filename ILIKE %s)")
        params += [q, f"%{q}%"]
    w = ("WHERE " + " AND ".join(where)) if where else ""
    total = _q(f"SELECT count(*) n FROM documents {w}", params, one=True)["n"]
    items = _q(f"""SELECT id, filename, route, bucket, reocr_reason, char_count,
                   diacritic_density FROM documents {w}
                   ORDER BY filename LIMIT %s OFFSET %s""",
               params + [page_size, (page - 1) * page_size])
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@app.get("/api/docs/{doc_id}")
def get_doc(doc_id: int):
    d = _q("SELECT id, filename, route, full_text, bucket, reocr_reason, legacy_density, "
           "diacritic_density, char_count, updated_at FROM documents WHERE id=%s", (doc_id,), one=True)
    if not d:
        raise HTTPException(404, "không tìm thấy doc")
    return d


@app.get("/api/docs/{doc_id}/pdf")
def get_pdf(doc_id: int):
    d = _q("SELECT filename FROM documents WHERE id=%s", (doc_id,), one=True)
    if not d:
        raise HTTPException(404, "không tìm thấy doc")
    path = os.path.abspath(os.path.join(PDF_DIR, d["filename"]))
    if not path.startswith(os.path.abspath(PDF_DIR)) or not os.path.exists(path):
        raise HTTPException(404, "không tìm thấy PDF gốc")
    return FileResponse(path, media_type="application/pdf")


@app.put("/api/docs/{doc_id}")
def edit_doc(doc_id: int, full_text: str = Body(..., embed=True)):
    """Sửa tay full_text → tự phân loại lại + cập nhật search index."""
    if not _q("SELECT 1 FROM documents WHERE id=%s", (doc_id,), one=True):
        raise HTTPException(404, "không tìm thấy doc")
    _q(_UPDATE, _reclassify_sql(full_text) + (doc_id,), write=True)
    return get_doc(doc_id)


@app.post("/api/docs/{doc_id}/reprocess")
def reprocess_doc(doc_id: int):
    """Chạy lại decode font cũ ($0, không GPU): TCVN3 rồi VNI, phân loại lại."""
    d = _q("SELECT full_text FROM documents WHERE id=%s", (doc_id,), one=True)
    if not d:
        raise HTTPException(404, "không tìm thấy doc")
    t, n1 = legacy_decode.fix_text(d["full_text"] or "")
    t, n2 = vni_decode.fix_text(t)
    _q(_UPDATE, _reclassify_sql(t) + (doc_id,), write=True)
    out = get_doc(doc_id)
    out["_decoded_lines"] = n1 + n2
    return out


@app.delete("/api/docs/{doc_id}")
def delete_doc(doc_id: int):
    if not _q("SELECT 1 FROM documents WHERE id=%s", (doc_id,), one=True):
        raise HTTPException(404, "không tìm thấy doc")
    _q("DELETE FROM documents WHERE id=%s", (doc_id,), write=True)
    return {"deleted": doc_id}
