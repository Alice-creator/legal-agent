---
description: Khôi phục index pgvector (documents+chunks) đúng cách — né bẫy HNSW treo hàng giờ
argument-hint: [đường-dẫn-dump] (mặc định ~/legal_index.dump; chạy TRÊN SERVER)
---
Khôi phục index search lên Postgres trong compose prod.

⚠️ **BẪY CHÍNH:** `pg_restore` mặc định build HNSW với `maintenance_work_mem=64MB` →
TREO hàng giờ (tưởng restore hỏng/`documents=0`). Phải restore **data-only** rồi **tự
build index** với RAM lớn. HNSW chỉ cần CPU, không cần GPU.

Dump file = `$1` (mặc định `~/legal_index.dump`). Các lệnh dưới chạy trong thư mục chứa
`docker-compose.prod.yml` trên server.

**B1 — Tạo dump (nếu chưa có; máy có Postgres dev cổng 5433):**
```bash
pg_dump "postgresql://legal:legal@localhost:5433/legal" -t documents -t chunks -Fc -f legal_index.dump
# chuyển sang server: scp, hoặc quick-tunnel nếu server sau NAT (xem DEPLOY.md mục C)
```

**B2 — Trên server, tạo EXTENSION trước (halfvec cần `vector`):**
```bash
docker compose -f docker-compose.prod.yml exec -T db psql -U legal -d legal -c \
  "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS unaccent; CREATE EXTENSION IF NOT EXISTS pg_trgm;"
```

**B3 — Restore DATA-ONLY (KHÔNG để pg_restore tự build HNSW):**
```bash
docker compose -f docker-compose.prod.yml exec -T db \
  pg_restore -U legal -d legal --no-owner --section=pre-data --section=data < "${1:-$HOME/legal_index.dump}"
```

**B4 — Tự build HNSW với RAM lớn (~1-2 phút thay vì hàng giờ):**
```bash
docker compose -f docker-compose.prod.yml exec -T db psql -U legal -d legal -c \
  "SET maintenance_work_mem='2GB'; SET max_parallel_maintenance_workers=4; \
   CREATE INDEX IF NOT EXISTS idx_chunks_hnsw ON chunks USING hnsw (embedding halfvec_cosine_ops) WITH (m=16, ef_construction=64);"
```

**B5 — Verify:**
```bash
docker compose -f docker-compose.prod.yml exec -T db psql -U legal -d legal -c \
  "SELECT (SELECT count(*) FROM documents) docs, (SELECT count(*) FROM chunks) chunks, \
          (SELECT count(*) FROM chunks WHERE embedding IS NOT NULL) embedded;"
```
Kỳ vọng ~ docs 34404 · chunks 357104 · embedded = chunks. `\d chunks` thấy `idx_chunks_hnsw`.
Cuối cùng `/health` của backend → `{"status":"ok","db":"ok"}`.
