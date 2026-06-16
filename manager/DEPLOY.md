# Deploy backend (home-lab + Cloudflare Tunnel)

Server home-lab sau NAT (vd `192.168.2.13`). Cloudflare Tunnel cho **public HTTPS**
mà không cần mở port router / IP tĩnh / domain-riêng-tự-cấp-cert.

```
App thẩm phán ──HTTPS──► Cloudflare edge ──tunnel──► cloudflared ──http──► backend:8000 ──► Postgres/pgvector
                         (cert tự động)              (trong compose)
```

## A. Tạo Cloudflare Tunnel (dashboard, 1 lần)
1. **Cloudflare Zero Trust** → Networks → **Tunnels** → *Create a tunnel* → **Cloudflared** → đặt tên (vd `legal-agent`).
2. Copy **token** (trong lệnh `cloudflared service install <TOKEN>` nó hiện) → dán vào `.env` (`CF_TUNNEL_TOKEN`).
3. Tab **Public Hostname** của tunnel → *Add a public hostname*:
   - Subdomain/Domain: vd `search.tenmien.com` (domain phải đang ở Cloudflare)
   - Service: **HTTP**, URL: `backend:8000`  ← tên service trong compose
4. Save. (Cert HTTPS cho hostname do Cloudflare lo, không cần Caddy.)

## B. Chạy backend trên server
```bash
# 1. login GHCR (1 lần) — PAT có scope read:packages
docker login ghcr.io -u <github-user>

# 2. lấy file deploy (clone repo, hoặc copy 2 file: docker-compose.prod.yml + .env)
git clone <repo> && cd legal-agent/manager     # hoặc scp docker-compose.prod.yml lên

# 3. tạo .env từ mẫu, điền POSTGRES_PASSWORD + CF_TUNNEL_TOKEN
cp .env.prod.example .env && nano .env

# 4. kéo image + chạy (db + backend + cloudflared)
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d

# 5. theo dõi: backend nạp model -> "model embed sẵn sàng"; cloudflared "Registered tunnel"
docker compose -f docker-compose.prod.yml logs -f backend cloudflared
```
Kiểm tra: mở `https://search.tenmien.com/health` → `{"status":"ok","db":"ok"}`.

## C. Nạp INDEX (357k chunk) từ Mac → server (1 lần + mỗi khi re-embed)
```bash
# trên Mac: dump documents + chunks (đã embed) từ Postgres dev (cổng 5433)
pg_dump "postgresql://legal:legal@localhost:5433/legal" -t documents -t chunks -Fc -f legal_index.dump
scp legal_index.dump server@192.168.2.13:~/

# trên server: restore vào Postgres trong compose
docker compose -f docker-compose.prod.yml exec -T db \
  pg_restore -U legal -d legal --no-owner < ~/legal_index.dump
```
(Schema do image/lần đầu tạo; nếu DB trống cần `psql ... -f schema.sql` trước.)

## D. Build app trỏ tới server
```bash
# local
cd manager/frontend && VITE_API_BASE=https://search.tenmien.com npm run tauri:build
# hoặc CI: đặt repo Variable VITE_API_BASE = https://search.tenmien.com (release-app.yml)
```

## E. Update sau này — TỰ ĐỘNG (watchtower)
- Code backend đổi → push `main` → CI build+push image → **watchtower trên server tự
  pull + recreate backend trong ~2 phút** (không cần SSH / lệnh tay). Backend restart
  ~30-40s (nạp lại model) → có downtime ngắn mỗi lần deploy.
- watchtower kéo image private bằng creds từ `docker login ghcr.io` (mount
  `~/.docker/config.json`). Chỉ auto-update container có label (backend); db/cloudflared giữ nguyên.
- Muốn deploy tay (không chờ poll): `docker compose -f docker-compose.prod.yml pull backend && up -d backend`.
- Re-embed (fine-tune) → làm lại bước C (watchtower KHÔNG đụng index/DB).

> Bảo mật: `.env` không commit; cân nhắc bỏ `ports: 8000:8000` của backend khi đã dùng tunnel (backend chỉ lộ qua Cloudflare). Privacy: query tới Gemini là free-tier (train data) — đổi tier no-train trước khi dùng vụ thật.
