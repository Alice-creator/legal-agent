"""E2 — Embed chunks bằng AITeamVN (MPS, fp16) + build HNSW. Offline trên máy Mac.

Resumable: chỉ embed chunk có embedding IS NULL. Dừng/chạy lại an toàn (bỏ qua cái
đã xong). Lấy chunk theo ĐỘ DÀI tăng dần để giảm padding (nhanh hơn). Khi không còn
chunk NULL -> tự build index HNSW (halfvec_cosine_ops). Chạy lại sau khi xong = chỉ
build index.

Dùng (nền, qua đêm):
    nohup .venv-surya/bin/python manager/embed.py > data/processed/embed.out 2>&1 &
Test nhanh:
    .venv-surya/bin/python manager/embed.py --limit 20
"""
import os
import sys
import time
import psycopg
from sentence_transformers import SentenceTransformer

DSN = os.environ.get("PG_DSN", "postgresql://legal:legal@localhost:5433/legal")
MODEL = os.environ.get("EMBED_MODEL", "AITeamVN/Vietnamese_Embedding")
BATCH = int(os.environ.get("EMBED_BATCH", "128"))
FETCH = 4000   # số chunk lấy mỗi vòng (đã sort theo độ dài)


def _fmt(vec):
    return "[" + ",".join(f"{x:.5f}" for x in vec) + "]"


def build_hnsw(conn):
    print("embed xong → build HNSW (halfvec_cosine_ops)...", flush=True)
    t = time.time()
    with conn.cursor() as cur:
        cur.execute("SET maintenance_work_mem='2GB'")
        cur.execute("SET max_parallel_maintenance_workers=4")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_hnsw ON chunks "
                    "USING hnsw (embedding halfvec_cosine_ops) WITH (m=16, ef_construction=64)")
    conn.commit()
    print(f"HNSW xong sau {(time.time()-t)/60:.1f} phút.", flush=True)


def main(limit=None):
    fp16 = bool(os.environ.get("EMBED_FP16"))
    print(f"load {MODEL} (MPS, {'fp16' if fp16 else 'fp32'})...", flush=True)
    m = SentenceTransformer(MODEL, device="mps")
    if fp16:
        m.half()   # ~2x nhanh, gần như không mất chất lượng — nhưng MẶC ĐỊNH fp32
    conn = psycopg.connect(DSN)
    total = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
    done0 = conn.execute("SELECT count(*) FROM chunks WHERE embedding IS NOT NULL").fetchone()[0]
    print(f"{done0}/{total} đã embed · còn {total-done0}", flush=True)

    t0 = time.time()
    done = done0
    processed = 0
    while True:
        n = FETCH if limit is None else min(FETCH, limit - processed)
        if n <= 0:
            break
        rows = conn.execute(
            "SELECT id, chunk_text FROM chunks WHERE embedding IS NULL "
            "ORDER BY length(chunk_text) LIMIT %s", (n,)).fetchall()
        if not rows:
            break
        ids = [r[0] for r in rows]
        emb = m.encode([r[1] for r in rows], batch_size=BATCH,
                       normalize_embeddings=True, show_progress_bar=False)
        with conn.cursor() as cur:
            cur.executemany("UPDATE chunks SET embedding=%s::halfvec WHERE id=%s",
                            [(_fmt(e), i) for e, i in zip(emb, ids)])
        conn.commit()
        done += len(rows)
        processed += len(rows)
        rate = processed / max(time.time() - t0, 1e-6)
        eta = (total - done) / rate / 60 if rate > 0 else 0
        print(f"{done}/{total} · {rate:.1f} chunk/s · ETA {eta:.0f} phút", flush=True)

    remain = conn.execute("SELECT count(*) FROM chunks WHERE embedding IS NULL").fetchone()[0]
    if remain == 0 and limit is None:
        build_hnsw(conn)
    else:
        print(f"còn {remain} chunk NULL (chưa build HNSW).", flush=True)


if __name__ == "__main__":
    lim = next((int(a.split("=")[1]) for a in sys.argv if a.startswith("--limit=")), None)
    if lim is None and "--limit" in sys.argv:
        i = sys.argv.index("--limit")
        if i + 1 < len(sys.argv):
            lim = int(sys.argv[i + 1])
    main(limit=lim)
