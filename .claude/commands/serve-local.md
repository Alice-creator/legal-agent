---
description: Khởi động môi trường dev local (Postgres + FastAPI backend + Vite frontend)
argument-hint: (không cần tham số)
---
Khởi động full stack dev local. **Chạy trên máy DEV, từ GỐC REPO** (`pwd` = …/legal-agent).

### Trước khi chạy — kiểm:
- Đang ở gốc repo (không phải `manager/`).
- venv `.venv-surya` có sẵn; `manager/frontend/node_modules` đã cài (nếu chưa: `npm --prefix manager/frontend install`).

### 1. Postgres (pgvector, host port 5433)
Nếu container `legal_db` chưa chạy:
```bash
docker compose -f manager/docker-compose.yml up -d
```
Chờ `legal_db` `healthy` (`docker ps`). **Lần đầu lập DB** (DB trống): nạp schema + data trước —
`docker exec -i legal_db psql -U legal -d legal < manager/schema.sql && .venv-surya/bin/python manager/ingest.py`.

### 2. Backend FastAPI (port 8000) — chạy NỀN
```bash
.venv-surya/bin/uvicorn manager.backend.main:app --reload --port 8000
```
Model embed **eager-load** lúc khởi động → chờ `curl -s localhost:8000/health` trả `{"status":"ok"}`
(~30-40s) rồi mới báo sẵn sàng. Gọi search trước đó sẽ lỗi/treo.

### 3. Frontend Vite — chạy NỀN
```bash
npm --prefix manager/frontend run dev
```

Xong báo user: backend `http://localhost:8000`, app `http://localhost:5173`.
Nếu API trong dev 404: frontend gọi `/api/...` → cần proxy Vite hoặc đặt `VITE_API_BASE=http://localhost:8000`
(xem `manager/frontend/src/api.js` — `API_BASE = import.meta.env.VITE_API_BASE || ''`).
