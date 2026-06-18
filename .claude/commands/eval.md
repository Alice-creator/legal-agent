---
description: Chạy eval retrieval (E4) — đo nDCG/Recall/MRR trên index hiện có
argument-hint: [--n N để sinh thêm query trước] (mặc định chỉ chạy eval trên query có sẵn)
---
Đánh giá chất lượng retrieval (E4). **Chạy trên máy DEV (Mac), từ GỐC REPO** — các script dùng
path tương đối (`data/processed/...`) nên sai thư mục là sai hết.

### Trước khi chạy — kiểm (preflight). Báo user nếu thiếu, ĐỪNG chạy mù:
1. **Đang ở gốc repo** (`pwd` = …/legal-agent, KHÔNG phải `manager/`).
2. **Postgres dev (5433) chạy**: `docker compose -f manager/docker-compose.yml up -d` → chờ `legal_db` healthy.
3. **HNSW index PHẢI tồn tại & ĐÚNG LOẠI** — thiếu/sai thì retrieve = seq scan, chậm + số liệu vô nghĩa. Kiểm:
   `docker exec legal_db psql -U legal -d legal -tAc "SELECT 1 FROM pg_indexes WHERE indexname='idx_chunks_hnsw' AND indexdef LIKE '%halfvec_cosine_ops%'"` → phải trả về `1`.
   Thiếu → build index trước (xem `manager/embed.py` / `/restore-index`).
4. **venv `.venv-surya`** có sẵn (sentence-transformers, psycopg; thêm `ollama` nếu chạy Pass 1).

### Pass 1 (TUỲ CHỌN) — sinh synthetic query
Chỉ chạy nếu user đưa `--n`, HOẶC `data/processed/eval_queries.jsonl` chưa tồn tại.
Cần `OLLAMA_API_KEY` (key ollama **cloud**, không phải ollama local) trong `.env` ở gốc repo (hoặc export sẵn).
```bash
.venv-surya/bin/python manager/eval_gen.py --n 300
```
→ append `data/processed/eval_queries.jsonl` (resumable, bỏ qua doc_id đã có). Query ẩn danh tên/ngày/số tiền.

### Pass 2 — chạy eval (offline, KHÔNG cần mạng/ollama)
```bash
.venv-surya/bin/python manager/eval_run.py
# gold set khác: --queries data/processed/<file>.jsonl
```
- Đọc query từ `data/processed/eval_queries.jsonl` (output của Pass 1). File trống/thiếu → script
  `sys.exit("không có query…")` ngay; thiếu thì chạy Pass 1 trước. **An toàn**: chỉ ĐỌC DB, chạy lại tuỳ ý.
- Đo 3 mode: **hybrid / dense / bm25**. Mode bm25 cần `data/processed/term_df.json` (cache IDF);
  thiếu file đó thì **BM25 ra số rác** — nhưng **dense** (cái ta quan tâm) vẫn đúng, cứ đọc dense.
- Mặc định encode bằng **MPS** (Apple Silicon — máy dev). Máy Intel/Linux: chạy với env `EVAL_DEVICE=cpu`
  (vd `EVAL_DEVICE=cpu .venv-surya/bin/python manager/eval_run.py`).

### Kết quả & diễn giải
`eval_run.py` in tiến độ `k/n`, rồi bảng — cột `nDCG@10 MRR R@1 R@5 R@10 R@20 R@50 Hit@100`, mỗi
mode 1 dòng (hybrid/dense/bm25) — và ghi `data/processed/eval_results.json`.

**Mốc sanity (theo E4, n≈308):** dense `nDCG@10 ≈ 0.20`, `Hit@100 ≈ 0.42`. Nếu dense ≈ 0 →
index/embedding hỏng (sai model, vector NULL, index sai loại) → **DỪNG, báo user, đừng kết luận**.

**Báo lại** bảng metrics + so dense vs hybrid. Lưu ý phương pháp: chỉ tính bản án GỐC là relevant →
số tuyệt đối là **cận DƯỚI**, chỉ để **so mode/model**. E4 đã chốt **dense ≈ hybrid** (nhiễu ±0.027)
→ dùng **dense-primary**; ĐỪNG đổi sang hybrid trừ khi eval cải thiện **vượt nhiễu** rõ ràng.
