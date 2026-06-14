# Phần mềm quản lý corpus

Quản lý 34k bản án đã trích xuất (`data/processed`): duyệt · tìm kiếm · bảng chất
lượng · sửa/xử-lý-lại. Stack: **PostgreSQL (Docker) + FastAPI + React/Vite**.

## Tiến độ
- [x] **P0** — Postgres (Docker) + schema + ingest 34k (kèm phân loại chất lượng)
- [x] **P1** — Backend FastAPI (stats/list/detail/search/pdf + sửa/reprocess/xoá)
- [x] **P2** — Frontend React/Vite (dashboard/list/detail + PDF đối chiếu)
- [x] **P3** — Ghi (sửa tay · decode lại $0 · xoá) — gộp vào P1/P2
- [ ] P4 — Đánh bóng (highlight rác, export, re-OCR qua UI…)

## Chạy app (3 bước, 2 terminal)

```bash
# 0. Postgres (nếu chưa chạy) — chỉ cần 1 lần
docker compose -f manager/docker-compose.yml up -d
#    (lần đầu setup DB: docker exec -i legal_db psql -U legal -d legal < manager/schema.sql
#                       && .venv-surya/bin/python manager/ingest.py)

# 1. Backend (terminal 1, từ repo root)
.venv-surya/bin/uvicorn manager.backend.main:app --reload --port 8000

# 2. Frontend (terminal 2)
npm --prefix manager/frontend install      # chỉ lần đầu
npm --prefix manager/frontend run dev
```

Mở **http://localhost:5173** → Bảng chất lượng / Tài liệu (lọc + tìm + xem PDF đối chiếu + sửa/decode/xoá).

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
