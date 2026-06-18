---
description: Chạy eval retrieval (E4) — đo nDCG/Recall/MRR trên index hiện có
argument-hint: [--n N để sinh thêm query trước] (mặc định chỉ chạy eval trên query có sẵn)
---
Đánh giá chất lượng retrieval. venv `.venv-surya`, cần Postgres dev (5433) đang chạy + index đã build.

**Pass 1 (tuỳ chọn) — sinh synthetic query** (cần `OLLAMA_API_KEY` trong env/.env):
```bash
.venv-surya/bin/python manager/eval_gen.py --n 300
```
→ ghi `data/processed/eval_queries.jsonl` (resumable — bỏ qua doc_id đã có). Mỗi query
ẩn danh (bỏ tên/ngày/số tiền) nên buộc khớp ngữ nghĩa, không copy chuỗi. Chỉ chạy pass này
nếu user đưa `--n` hoặc file query chưa tồn tại.

**Pass 2 — chạy eval** (đo bản án gốc xếp hạng bao nhiêu; 3 mode hybrid / dense / bm25):
```bash
.venv-surya/bin/python manager/eval_run.py
# gold set khác: --queries data/processed/<file>.jsonl
```

Báo lại bảng metrics theo mode (nDCG@10, Recall@k, MRR, Hit@100).

**Diễn giải đúng:** chỉ tính bản án GỐC là relevant → số tuyệt đối là **cận DƯỚI**, dùng để
SO mode/model là chính. E4 đã chốt **dense ≈ hybrid** (trong nhiễu ±0.027) → hệ thống dùng
**dense-primary**. ĐỪNG đổi sang hybrid trừ khi eval cho thấy cải thiện **vượt nhiễu** rõ ràng.
