---
description: Khởi động môi trường dev local (Postgres + FastAPI backend + Vite frontend)
argument-hint: (không cần tham số)
---
Khởi động full stack dev local, đúng thứ tự, chạy từ gốc repo.

1. **Postgres** (pgvector, host port 5433) — nếu container `legal_db` chưa chạy:
   `docker compose -f manager/docker-compose.yml up -d`
   Chờ `legal_db` `healthy` trước khi qua bước 2.

2. **Backend** FastAPI (port 8000), chạy NỀN, venv `.venv-surya`:
   `.venv-surya/bin/uvicorn manager.backend.main:app --reload --port 8000`
   Model embed eager-load lúc khởi động → chờ `curl -s localhost:8000/health` trả `{"status":"ok"}`
   (~30-40s) rồi mới báo sẵn sàng. Trước đó gọi search sẽ lỗi/treo.

3. **Frontend** Vite, chạy NỀN:
   `npm --prefix manager/frontend run dev`   (lần đầu: `npm --prefix manager/frontend install` trước)

Xong, báo user: backend `http://localhost:8000`, app `http://localhost:5173`.
Nếu API trong dev bị 404: frontend gọi `/api/...` → cần proxy Vite hoặc đặt
`VITE_API_BASE=http://localhost:8000` (xem `manager/frontend/src/api.js`).
