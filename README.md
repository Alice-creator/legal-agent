# Legal Agent

Công cụ tìm kiếm ngữ nghĩa trên bản án thương mại (KDTM) của toà án Việt Nam.
Mục tiêu: giúp **hội đồng xét xử** tra cứu các vụ án tương tự đã xử để tham khảo
khi tuyên án (hướng tới sự nhất quán giữa các phán quyết).

Nguồn: ~35.000 file PDF bản án. Toàn bộ pipeline chạy **LOCAL, $0** (không gọi cloud).

## Trạng thái

- **Phiên 1 — Trích xuất dữ liệu (XONG):** PDF → `full_text` tiếng Việt chuẩn hoá, sạch,
  sẵn sàng để embed. Output: `data/processed/<tên>.json` = `{filename, route, full_text}`.
- **Phiên 2 — Embedding & tìm kiếm (dự kiến):** chốt model embedding · index pgvector · API tìm kiếm.

📓 Nhật ký nghiên cứu + **runbook tái lập** (đủ để dựng lại Phiên 1 từ đầu):
mở `research_journal.html` trên trình duyệt — đọc mục "🔁 Tái lập nghiên cứu" trước tiên.

## Pipeline trích xuất

Mỗi doc được định tuyến theo cách rẻ-nhất-đáng-tin:

| Route | Tỉ lệ | Cách xử lý |
|-------|------:|-----------|
| `clean` | 72% | PyMuPDF text thuần |
| `glued` | 11% | PyMuPDF + bộ tách âm tiết tiếng Việt (DP trên 7184 âm tiết) |
| `scanned` | 17% | Surya OCR (GPU local) |
| `legacy`/`holes` | ~2% | bỏ + ghi log (`skipped_legacy.log`) |

Doc font cũ (TCVN3/VNI) được dọn thêm sau trích xuất — xem scripts.

**Trạng thái corpus:** 34.404 doc · **sạch 95,7%** (32.939) · 609 minor (rác chỉ ở
quốc hiệu/chữ ký, vẫn dùng được) · 856 doc residual để re-OCR sau.

## Scripts

| Script | Việc |
|--------|------|
| `main.py` | Pipeline chính: producer/consumer — text (CPU) + 1 worker Surya (GPU) song song |
| `utils.py` | Lõi: routing, trích xuất, tách âm tiết, OCR Surya, chuẩn hoá |
| `detect_errors.py` | Quét 100% corpus, phân loại lỗi theo vị trí, ghi hàng đợi `needs_reocr.txt` |
| `legacy_decode.py` | Decode font cũ TCVN3 → Unicode bằng charmap ($0, không GPU) |
| `reocr.py` | Re-OCR **theo trang** cho doc còn rác (VNI/rụng chữ); reuse Surya |
| `fix_legacy.py` | Sửa rác an toàn: ƣ→ư, dấu thanh mồ côi, PUA, control char |
| `fix_verified.py` | Sửa đích danh từng doc, đã xác minh tận trang PDF |
| `purge_legacy.py` | Gỡ doc rác-toàn-phần khỏi `data/processed` |
| `data_download.py` | Tải dữ liệu nguồn |

Môi trường: `.venv-surya` (Python 3.12) — pymupdf, regex, surya-ocr==0.14.7. Không cần ollama/cloud.
Thứ tự chạy đầy đủ: xem runbook trong `research_journal.html`.

```bash
.venv-surya/bin/python main.py            # chạy pipeline trích xuất
.venv-surya/bin/python detect_errors.py   # kiểm tra chất lượng corpus (FIXABLE phải = 0)
```

## Tech stack

| Layer | Công nghệ |
|-------|-----------|
| Trích xuất text | PyMuPDF |
| OCR | Surya (PyTorch/MPS, GPU Apple) |
| Embedding (Phiên 2) | chưa chốt (multilingual-e5 / bge-m3 / …) |
| Database (Phiên 2) | PostgreSQL + pgvector |

## Tài liệu

- [Quyết định sản phẩm](docs/product_decision.md)
- Nhật ký nghiên cứu & tái lập: `research_journal.html`
