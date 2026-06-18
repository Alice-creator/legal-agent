---
description: Khôi phục index pgvector (documents+chunks) đúng cách — né bẫy HNSW treo hàng giờ
argument-hint: [đường-dẫn-dump-TRÊN-SERVER] (mặc định ~/legal_index.dump)
---
Nạp index search vào Postgres của stack prod.

**MÔI TRƯỜNG:** đây là runbook bạn (Claude) thực thi **khi đã ở TRÊN SERVER** (ssh vào server,
hoặc đang chạy trong shell server) — KHÔNG chạy từ máy Mac. Các lệnh `docker compose` giả định
**cwd = thư mục `manager/` trên server** (nơi chứa `docker-compose.prod.yml`). Nếu chưa, `cd` vào đó trước.

⚠️ **BẪY CHÍNH:** `pg_restore` mặc định tự build HNSW với `maintenance_work_mem=64MB` → TREO hàng
giờ (nhìn như đứng máy / `documents=0`, tưởng hỏng). Vì vậy phải tách 2 bước: **restore data-only**
(B3) rồi **tự build index** với 2GB RAM (B4). ĐỪNG gộp, ĐỪNG bỏ B4. HNSW chỉ cần CPU, không cần GPU.

**Đường dẫn dump:** mặc định `~/legal_index.dump` (đã viết sẵn trong các lệnh dưới). Nếu user đưa path
khác qua đối số (`$1`), **bạn tự thay MỌI chỗ `~/legal_index.dump` bằng path đó** trước khi chạy — KHÔNG
dựa vào bash `$1`/`${1:-…}`: slash command thay `$1` vào *text* lệnh này, không truyền positional arg cho shell.

---
**B1 — LÀM TRÊN MÁC** (bỏ qua nếu dump đã có sẵn trên server): tạo dump + chuyển sang server.
```bash
# trên Mac, từ máy có Postgres dev cổng 5433:
pg_dump "postgresql://legal:legal@localhost:5433/legal" -t documents -t chunks -Fc -f legal_index.dump
# chuyển sang server: scp legal_index.dump user@server:~/   (server sau NAT → quick-tunnel, xem DEPLOY.md §C)
```

**B2–B5 — LÀM TRÊN SERVER.** Trước hết `cd` vào thư mục chứa compose (vd `cd ~/legal-agent/manager`),
vì các lệnh dùng `-f docker-compose.prod.yml` (đường dẫn tương đối):

**B2 — Tạo EXTENSION trước (halfvec cần `vector`):**
```bash
docker compose -f docker-compose.prod.yml exec -T db psql -U legal -d legal -c \
  "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS unaccent; CREATE EXTENSION IF NOT EXISTS pg_trgm;"
```

**B3 — Restore DATA-ONLY (không để pg_restore build HNSW):**
```bash
docker compose -f docker-compose.prod.yml exec -T db \
  pg_restore -U legal -d legal --no-owner --section=pre-data --section=data < ~/legal_index.dump
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
Kỳ vọng ~ docs **34404** · chunks **357104** · embedded = chunks. `\d chunks` thấy `idx_chunks_hnsw`.
Cuối: kiểm backend — `curl https://<domain-tunnel>/health` (hoặc `curl localhost:8000/health` nếu còn map port)
→ `{"status":"ok","db":"ok"}`.

**Nếu B3 lỗi giữa chừng** (dump hỏng / hết đĩa / OOM): dọn rồi làm lại từ B2 —
`... psql ... -c "DROP TABLE IF EXISTS chunks CASCADE; DROP TABLE IF EXISTS documents CASCADE;"`
