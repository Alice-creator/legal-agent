# CLAUDE.md — Legal Agent

> File này Claude Code **tự nạp** vào mọi session trong repo. Mục tiêu: một Claude mới
> đọc xong là làm việc được ngay, không dẫm lại các bẫy đã tốn nhiều giờ.
> Viết ngắn, cao tín hiệu. Doc cho người đọc nằm ở mục **Tài liệu sâu hơn** cuối file.

## Hệ thống này là gì

Tra cứu **bản án tương tự** cho **thẩm phán** toà KDTM (kinh doanh-thương mại) VN.
Thẩm phán dán *tình tiết vụ đang xử* → nhận về các bản án/quyết định gần nhất về mặt
ngữ nghĩa + tóm tắt AI để **tham khảo** (không phải phán quyết). Civil-law nên đây là
"xem toà trước xử thế nào", không phải tiền lệ ràng buộc.

Nguồn: ~35.089 PDF (38GB). Corpus đã trích xuất: **34.404 doc · 357.104 chunk**.

## Hai phiên — repo chia làm 2 nửa

| Nửa | Thư mục | Việc | Trạng thái |
|---|---|---|---|
| **Phiên 1 — Trích xuất** | gốc repo (`main.py`, `utils.py`, `reocr.py`, `*_decode.py`, `fix_*.py`) | PDF → `data/processed/<tên>.json` `{filename, route, full_text}` tiếng Việt sạch | XONG (96,6% sạch) |
| **Phiên 2 — Tìm kiếm + App** | `manager/` | embed → pgvector → FastAPI search → Tauri desktop app | ĐANG CHẠY (đã deploy + pilot) |

Phiên 1 dùng venv **`.venv-surya`** (py3.12, surya-ocr, pymupdf). Backend Phiên 2
**cũng** chạy bằng venv này: `.venv-surya/bin/uvicorn manager.backend.main:app`.

## Kiến trúc đã CHỐT (và vì sao)

- **1 codebase → 2 bản Tauri build.** v1 = thẩm phán (search), v2 = admin (quản lý corpus).
  Cùng `manager/frontend`, khác build flag. ĐỪNG tách thành 2 repo.
- **Dense-primary retrieval**, KHÔNG hybrid. E4 đo: dense 0.201 ≈ hybrid 0.205 (trong
  nhiễu ±0.027), BM25 yếu + nhiễu âm-tiết-vỡ. → Bỏ BM25. Đừng "thêm lại hybrid cho chắc"
  mà không đo lại — xem bẫy `websearch_to_tsquery` bên dưới.
- **Server embed query bằng CPU** (`AITeamVN/Vietnamese_Embedding`, bge-m3 1024-dim,
  `halfvec(1024)`). ~1-3s/query, **không cần GPU**. App gửi *text*, server trả vector+kết quả.
- **Tóm tắt AI = Gemini BYOK phía client.** Mỗi thẩm phán dùng key Google riêng (lưu
  `localStorage`, KHÔNG auth cấp app). Server KHÔNG giữ key, KHÔNG tốn quota. Model fallback:
  `gemini-flash-latest` → `2.5-flash-lite` → `2.0-flash-lite` (né 503/quota).
- **Trả về chunk + tên doc**, không trả full doc. Click tên → trang chi tiết (full text + **PDF gốc** qua iframe).
- **CI build image, server CHỈ pull.** GHCR `ghcr.io/alice-creator/legal-agent-backend`.
  Watchtower (label-scoped, **pull-based** vì server sau NAT) tự deploy khi CI push.
- **Public HTTPS qua Cloudflare Tunnel** (server home-lab sau NAT, không port-forward).

## Hạ tầng thực tế

- **Server**: Ubuntu home-lab, **16GB RAM, KHÔNG GPU**, sau NAT (LAN `192.168.2.13`).
  Ra ngoài qua CF Tunnel. HNSW build chỉ tốn CPU nên server này dựng index được.
- **Stack prod**: `manager/docker-compose.prod.yml` — 4 service: `db` (pgvector 0.8.2,
  `shm_size: 3gb`) + `backend` (image GHCR, mount `./pdfs:/app/data/legal-data:ro`) +
  `cloudflared` (token tunnel) + `watchtower` (poll GHCR 120s).
- **38GB PDF gốc** nằm trên server (mount read-only) để hiện PDF.
- Secrets qua `manager/.env.prod` (gitignored; mẫu ở `.env.prod.example`):
  `POSTGRES_PASSWORD`, `CF_TUNNEL_TOKEN`.
- **Server chạy từ 1 bản `docker-compose.prod.yml` COPY tay lên (KHÔNG git clone)** + `.env` + `pdfs/`.
  → repo và server **dễ lệch**: sửa compose bên nào nhớ mirror bên kia. ĐỪNG bày `git pull` trên server.

## Thao tác thường dùng

```bash
# Dev local (2 terminal)
docker compose -f manager/docker-compose.yml up -d                 # Postgres :5433
.venv-surya/bin/uvicorn manager.backend.main:app --reload --port 8000
npm --prefix manager/frontend run dev                               # http://localhost:5173

# Deploy: KHÔNG build trên server. Push code → CI build+push GHCR → Watchtower tự pull.
# Build app cài (3 OS): git tag vX.Y.Z && git push origin vX.Y.Z  → release-app.yml
```
Chi tiết deploy/khôi-phục-index/transfer: đọc **`manager/DEPLOY.md`** (runbook đầy đủ).

## Bẫy đã tốn nhiều giờ — ĐỌC TRƯỚC KHI ĐỘNG VÀO

- **Khôi phục index pgvector**: pg_restore mặc định (`maintenance_work_mem`=64MB) **treo
  hàng giờ** ở bước build HNSW → tưởng restore hỏng. Cách đúng: restore **data-only**
  (`--section=pre-data --section=data`, nhớ `CREATE EXTENSION vector` trước cho `halfvec`),
  RỒI `SET maintenance_work_mem='2GB'; CREATE INDEX ... USING hnsw (... halfvec_cosine_ops)`
  → 1-2 phút thay vì hàng giờ.
- **`websearch_to_tsquery` ráp AND** mọi token → query dài ⇒ BM25 = 0 (bug prod cũ). Đây
  là lý do gốc bỏ hybrid. Nếu cần full-text lại: dùng IDF top-K từ hiếm, ĐỪNG OR-tất-cả
  (match 357k chunk, 34s/query).
- **Model phải eager-load lúc khởi động** (FastAPI `lifespan`), không lazy. CI health-test
  đặt `LAZY_EMBED=1` để bỏ qua. Sau khi backend restart, chờ ~30-40s model nạp xong
  (`/health`) rồi mới verify — không thì HTTP 000.
- **Tauri webview KHÔNG mở `target=_blank`.** Link ngoài phải qua `tauri-plugin-opener`
  (`openUrl`), bọc try/catch để fallback `window.open` ở môi trường web. Xem `openExternal` trong `Search.jsx`.
- **`VITE_API_BASE` bake lúc build** (repo Variable). Quên set → app trỏ URL rỗng = hỏng
  toàn bộ. Đổi server URL = phải build lại app.
- **`docker login ghcr.io`** cần **PAT** scope `read:packages` (KHÔNG dùng password), username
  `Alice-creator` (KHÔNG dùng email).
- **ĐỪNG nối `rm` sau lệnh tải/giải nén** trong cùng một chuỗi `&&`/`;`. Một lần `tar -x` sai
  thư mục nhưng `rm /tmp/pdfs.tar` vẫn chạy → mất 38GB. Luôn giải nén + verify TRƯỚC, `rm` riêng.
- **Mac công ty không cài được Tailscale** (Darktrace quản lý) → transfer file qua CF
  quick-tunnel relay. `trycloudflare` thỉnh thoảng timeout — tạm thời, thử lại.
- **`gh` CLI token ở máy này quyền hẹp** (403 khi đọc Variables/packages, không thấy
  release draft). Việc cần quyền đó → nhờ user thao tác trên web UI.
- **Watchtower `containrrr/watchtower` đã bị bỏ rơi** → client Docker API cũ (1.25) bị daemon host
  (≥1.40) từ chối → crash-loop, auto-deploy **chết âm thầm** (từng thấy `restarts=8772`). Fix: ghim
  `DOCKER_API_VERSION: "1.44"` trong env service watchtower (đã có trong compose). Hỏng nữa → đổi fork
  còn maintain, hoặc deploy tay (`docker compose ... pull backend && up -d backend`).

## Quy ước

- Doc/comment/commit message viết **tiếng Việt**, thuật ngữ kỹ thuật để nguyên tiếng Anh.
- **Comment = giải thích *business why*, không kể lại *what*.** Đoạn phức tạp — nhất là **SQL dài** — chú thích từng CTE/mệnh đề theo *mục đích nghiệp vụ* nó phục vụ (vd: "max-pool chunk về 1 dòng/bản án để vụ có nhiều đoạn khớp không bị đếm trùng"). Xem các comment sẵn có trong `manager/backend/search.py` làm mẫu.
- `data/`, `pdfs/`, `.env*`, venv, `target/`, `node_modules/` đều gitignored — không commit.
- Số liệu trong file này là **lúc viết** — đếm lại trước khi báo cáo (corpus có thể đổi).

## Tài liệu sâu hơn (mở bằng trình duyệt / editor)

| File | Nội dung |
|---|---|
| `manager/DEPLOY.md` | Runbook deploy: CF Tunnel, GHCR pull, khôi phục index (extension+HNSW 2GB), mount PDF, Watchtower |
| `system_design.html` | Kiến trúc Phiên 2 (đã cập nhật theo "1 codebase → 2 build") |
| `research_journal.html` | Nhật ký + runbook tái lập Phiên 1 (trích xuất) — đọc mục "🔁 Tái lập" trước |
| `rag_research.html` | Quá trình chốt thiết kế RAG (embedding, hybrid vs dense, E0–E4) |
| `docs/product_decision.md` | Định nghĩa sản phẩm, cấu trúc 4 phần của bản án VN |
| `README.md` / `manager/README.md` | Tổng quan Phiên 1 / Phiên 2 |
