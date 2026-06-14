# Phần mềm quản lý corpus

Quản lý 34k bản án đã trích xuất (`data/processed`): duyệt · tìm kiếm · bảng chất
lượng · sửa/xử-lý-lại. Stack: **PostgreSQL (Docker) + FastAPI + React/Vite**.

## Tiến độ
- [x] **P0** — Postgres (Docker) + schema + ingest 34k (kèm phân loại chất lượng)
- [ ] P1 — Backend API (stats/list/detail/search)
- [ ] P2 — Frontend (dashboard/list/detail + PDF đối chiếu)
- [ ] P3 — Ghi (sửa/reprocess/xoá)
- [ ] P4 — Đánh bóng

## Chạy P0

```bash
# 1. Postgres (image pgvector — sẵn cho Phiên 2). Host port 5433.
docker compose -f manager/docker-compose.yml up -d

# 2. Schema (idempotent)
docker exec -i legal_db psql -U legal -d legal < manager/schema.sql

# 3. Nạp 34k JSON → Postgres (upsert, chạy lại an toàn)
.venv-surya/bin/python manager/ingest.py
```

DB: `postgresql://legal:legal@localhost:5433/legal` (đổi qua `PG_DSN`).
Data nằm trong Docker named volume `legal_pgdata` (không trong repo).

Search: full-text `tsv` (`to_tsvector('simple', unaccent(full_text))`) + trigram
filename. Bỏ dấu vẫn tìm được. (Search ngữ nghĩa = Phiên 2, thêm cột `embedding` pgvector.)
