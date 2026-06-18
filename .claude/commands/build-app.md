---
description: Build app cài đặt 3 OS (mac/win/linux) — tag + push kích release-app.yml
argument-hint: <version, vd v0.1.1>
---
Phát hành bản app desktop mới qua CI (`.github/workflows/release-app.yml`). **Chạy trên máy DEV, từ GỐC REPO**
(có git remote `origin` trỏ GitHub).

Version = `$1`. Nếu user không đưa: `git tag --sort=-v:refname | head -1` xem tag mới nhất, đề xuất +1 patch,
**hỏi user xác nhận** trước khi tag.

### Trước khi tag — kiểm:
1. **Working tree sạch** (`git status` không còn thay đổi chưa commit) và đang ở **commit muốn phát hành**
   (thường là `main` đã push) — vì release build từ đúng commit mà tag trỏ tới.
2. ⚠️ **Repo Variable `VITE_API_BASE` PHẢI đã set** = URL server (vd `https://search.tenmien.com`).
   Quên → app build ra trỏ URL **rỗng** = HỎNG toàn bộ. Token `gh` ở máy này không đọc được Variables (403)
   → **nhờ user xác nhận** trên web: Settings → Secrets and variables → Actions → tab **Variables**.

### Chạy:
1. `git tag $1 && git push origin $1`
2. Theo dõi (chạy NỀN):
   ```bash
   gh run watch $(gh run list --workflow=release-app.yml -L1 --json databaseId --jq '.[0].databaseId') --exit-status
   ```
3. Xong (3 job mac/win/linux ✓): installer nằm ở **release draft `$1`** trên GitHub (token local thường
   KHÔNG thấy draft → nhờ user mở trang Releases). Tải về → đổi tên `LegalSearch-macos.dmg` /
   `-windows.exe` / `-linux.AppImage` → bỏ vào `download/` → deploy Cloudflare Pages.

Build lại version đã có: `git tag -d $1 && git push origin :$1` rồi tag lại.
Lần build đầu (chưa cache Rust) ~15-20 phút; lần sau nhanh hơn.
