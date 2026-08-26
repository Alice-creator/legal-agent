# Audit chất lượng retrieval (2026-08-26)

> Rà soát giải pháp tìm-vụ-tương-tự đang chạy production, đối chiếu với cách giới
> nghiên cứu làm bài toán này (COLIEE 2025/2026, VN-MTEB) và với chính corpus.
> Làm trên máy Ubuntu `loc-dev-G5-KE` (không có DB/index/venv nên **chỉ đọc code +
> đo corpus PDF**, chưa chạy lại eval). Việc đo lại số retrieval để dành cho máy có GPU.

## Kết luận

Thiết kế cốt lõi đúng, không phải làm lại. Nhưng hệ thống mới đi được **2 trong 4 tầng**
của một pipeline tra cứu án chuẩn, và E4 **đo ở cấu hình khác với production**.
Vấn đề không phải "chất lượng kém", mà là **chưa biết chất lượng tới đâu**: thước đo
hiện tại về bản chất không phân biệt được "retrieval yếu" với "corpus toàn vụ na ná".

Pipeline chuẩn của ngành: `lọc ứng viên → dense retrieval → cross-encoder rerank → cutoff thích ứng`.
Ta có tầng 2 (tốt), tầng 1 có sẵn nhưng đang tắt/lỗi, tầng 3 và 4 chưa có.

## 1. Hiệu chuẩn: 0,201 nDCG@10 nghĩa là gì

Số tuyệt đối của E4 nhìn thấp, nhưng đặt cạnh mặt bằng ngành thì **không phải hệ yếu**:

| Hệ thống | Bối cảnh | Kết quả |
|---|---|---|
| NOWJ @ COLIEE 2026 Task 1, tầng dense đơn thuần | Octen-Embedding-**8B** / E5-Mistral-**7B** | R@10 0,444 · R@100 0,766-0,786 |
| JNLP, **đứng nhất** COLIEE 2025 Task 1 | BM25 + rerank + phân loại, full pipeline | **F1 0,3353** |
| UQLegalAI, đứng nhì COLIEE 2025 | CaseLink (GNN) | F1 0,2962 |
| **Legal Agent (E4, n=308)** | AITeamVN 0,6B trên CPU, corpus 34k, 1 đáp án đúng | nDCG@10 0,201 · Hit@100 0,42 |

Đọc: cả ngành còn vật lộn quanh F1 0,3 cho bài toán này. Ta dùng model nhỏ hơn 12 lần,
chạy CPU, với thước đo khắt khe hơn (chỉ 1 doc được tính đúng). Baseline hợp lý.

Đọc ngược lại: **các đội mạnh đều coi dense là chỗ bắt đầu**, rồi mới chồng rerank.
Ta đang giao cho thẩm phán kết quả của tầng 2.

## 2. Đo lại corpus (bằng chứng mới)

Lấy mẫu ngẫu nhiên 700 PDF trong `data/` (hạt giống 42), 594 file có text-layer,
106 file scan nên bỏ qua. Tái lập: `python3 manager/audit_corpus.py`.

**Corpus cực kỳ đồng nhất.** Trong số doc ghi rõ loại tranh chấp: hợp đồng tín dụng
**35%**, mua bán hàng hoá **18%**. Hai loại gộp lại hơn nửa. Có 99 nhãn `V/v` khác nhau
nhưng đuôi phân bố rất mỏng.

→ **Câu bào chữa trong journal là ĐÚNG**: bản án gốc không đứng đầu không chứng minh
retrieval kém, vì top-10 tất yếu toàn vụ cùng loại.

→ Nhưng nó lộ ra vấn đề sản phẩm journal chưa nêu: nếu 35% corpus cùng một loại
tranh chấp thì việc "tìm đúng loại vụ" **không còn là phần khó**. Model làm được rồi.
Phần còn lại là phân biệt chi tiết: tài sản thế chấp là quyền sử dụng đất hộ gia đình
hay ô tô, có bên bảo lãnh không, tranh chấp lãi suất hay xử lý tài sản. Bi-encoder nén
450 token vào 1 vector 1024 chiều thì chính các chi tiết đó mờ trước tiên.
**Đây đúng là việc cross-encoder sinh ra để làm.**

**Thành phần index:**

| Chỉ số | Kết quả |
|---|---|
| Doc bị `chunk.py` gán `quyet_dinh` (thiếu cả header NỘI DUNG lẫn NHẬN ĐỊNH) | **53%** số doc |
| Nhưng chỉ chiếm | **16%** tổng ký tự ≈ 16% số chunk |
| Độ dài TB: bản án / quyết định | 20.616 / 3.775 ký tự |
| Phần mở đầu + phần quyết định trong 1 bản án (nhiều boilerplate) | ~25% ký tự (mẫu 10 doc `data_parsed/`) |

→ Khoảng **1/3 số chunk trong index không chứa tình tiết lẫn lập luận**, vẫn cạnh tranh
chỗ trong top-200 ứng viên.

⚠️ **Thiên lệch của mẫu**: chỉ tính PDF có text-layer, bỏ qua ~15% doc scan, mà doc scan
thường là bản án đầy đủ. Con số 53% nhiều khả năng là ước lượng **cao**. Muốn số chuẩn:
đếm thẳng trong DB (`SELECT doc_type, count(*) FROM documents GROUP BY 1`).

## 3. Khiếm khuyết trong code (chưa sửa)

**① Production chạy ở điểm vận hành YẾU HƠN lúc đo.**
`manager/eval_run.py:66-68` đo với `cand=500, ef_search=500`.
`manager/backend/search.py:90-93` chạy `cand=200, ef_search=200`.
⇒ Con số 0,201 **không mô tả hành vi server đang phục vụ thẩm phán**.
Nâng `ef_search` lên 500 tốn thêm vài chục ms trên 357k vector, trong khi mỗi query đã
mất 1-3s chỉ để embed. Đây là recall bị bỏ lại trên bàn mà không đổi được gì.

**② Bộ lọc `doc_type` chạy SAU khi đã cắt ứng viên.**
`manager/backend/search.py:53-71`: CTE `dense` lấy 200 chunk gần nhất trước, mệnh đề
`WHERE d.doc_type = ...` mới lọc ở SELECT cuối. Thẩm phán chọn "chỉ Bản án" thì hệ
**không tìm sâu hơn**, chỉ vứt bớt kết quả đã có ⇒ có thể trả về ít hơn số yêu cầu và
chất lượng kém đi thay vì tốt lên. Tính năng này **chưa từng được eval đụng tới**.
Cách sửa: đưa `doc_type` xuống thẳng bảng `chunks` để lọc ngay trong lúc quét index,
kèm `hnsw.iterative_scan` (pgvector 0.8 sinh ra đúng cho ca này; ta đang chạy 0.8.2).

**③ Chưa có reranker.** Khoảng trống lớn nhất. Chính AITeamVN công bố
`Vietnamese_Reranker` (fine-tune từ bge-reranker-v2-m3), đo trên Legal Zalo 2021:

| | Acc@1 | MRR@10 |
|---|---:|---:|
| Vietnamese_Embedding_v2 (chỉ dense) | 0,7262 | 0,8149 |
| Vietnamese_Reranker | **0,7944** | **0,8672** |

Gần +7 điểm Acc@1 trên chính miền luật, từ chính nhóm làm ra model ta đang dùng.
⚠️ Model 0,6B chạy CPU, mỗi cặp query+chunk ~650 token. Rerank 20 chunk trên server
16GB không GPU có thể tốn vài giây, cộng dồn với 1-3s embed thì trải nghiệm xấu rõ.
Bản ONNX INT8 giảm còn ~570MB và nhanh hơn nhiều, nhưng số latency giữa các nguồn
**mâu thuẫn nặng**. → PHẢI tự đo trên đúng server đó rồi mới quyết, đừng tin số người khác.

**④ Điểm số hiển thị cho thẩm phán chưa hiệu chuẩn.**
UI in `(score*100).toFixed(1)%` kèm nhãn "độ tương đồng cosine". Với họ model bge-m3,
hai văn bản KHÔNG liên quan vẫn thường đạt cosine 0,3-0,5. Kết quả lạc đề vẫn hiện
"48,7%", người đọc hiểu là "gần đúng một nửa". Trong bối cảnh toà án, con số gợi ý sai
mức độ tin cậy nguy hiểm hơn là không có con số. → Bỏ, hoặc quy về phân vị so với nền.

**⑤ Không có `query_log`** (blueprint có kế hoạch, code chưa có). Pilot đang chạy với
thẩm phán thật mà **không thu được gì**: không biết họ hỏi thế nào, bấm kết quả thứ mấy,
hay bỏ đi tay trắng. Nguồn dữ liệu duy nhất không mua được bằng tiền, đang bị đổ đi mỗi ngày.

## 4. Đánh giá lại phương pháp E4

Kết luận "dense ≈ hybrid nên bỏ BM25" **đúng kết quả nhưng sai lập luận**:

- Chênh 0,205 với 0,201 là 0,004, quá nhỏ để có ý nghĩa dù kiểm định kiểu gì. Chốt dense hợp lý.
- Nhưng ngưỡng nhiễu ±0,027 tính theo kiểu **hai mẫu độc lập**, trong khi hai mode chạy
  trên CÙNG bộ query. So sánh có cặp phải tính phương sai trên **hiệu số từng query**,
  thường nhỏ hơn vài lần. Ngưỡng nhiễu thật hẹp hơn con số đang dùng.
- Quan trọng hơn: nhánh BM25 lúc đó **bị què**. `ts_rank_cd` không phải BM25, config
  `simple` tách theo âm tiết tiếng Việt, IDF phải chắp vá bằng cache DF thủ công.
  Thí nghiệm chứng minh "BM25 KIỂU NÀY vô dụng", CHƯA chứng minh "tín hiệu từ vựng vô dụng".
  Đội nhất COLIEE 2025 dùng BM25 làm tầng lọc đầu, đạt recall 76-85% ở top-100.
- Ground truth chỉ tính đúng bản án gốc, trên corpus vừa đo được là cực kỳ đồng nhất.
  Thước đo này **không thể phân biệt** "retrieval yếu" với "corpus toàn vụ na ná".

**Hướng ra (LLM-judge) là đúng và giờ có bằng chứng hậu thuẫn**: UMBRELA cho thấy điểm
relevance do LLM chấm tương quan với người ở Kendall τ > 0,87 **khi dùng để xếp hạng các
hệ thống với nhau**, nhưng yếu hơn nhiều khi xét từng query. Đúng nhu cầu của ta: cần biết
"bật reranker có tốt hơn không", không cần con số tuyệt đối. Vẫn có phản biện học thuật
rằng LLM chưa thay được người ⇒ đừng dùng làm điểm nghiệm thu với toà.

## 5. Lựa chọn model: ĐÚNG, không cần đụng

- VN-MTEB (EACL 2026, 41 bộ dữ liệu VN): dẫn đầu retrieval tiếng Việt là model 7-8B có
  instruction tuning (gte-Qwen2-7B-instruct 46,05 · e5-Mistral-7B 41,73). Không chạy nổi
  trên server 16GB không GPU.
- Trong tầm với, `AITeamVN/Vietnamese_Embedding` hơn bge-m3 gốc rất xa trên miền luật
  (MRR@10 0,818 vs 0,682).
- Bản **v2 mới hơn lại TỤT điểm ở miền luật** theo chính model card ⇒ ở lại v1 là quyết
  định đúng, không phải quán tính.
- Cách max-pool chunk về bản án trùng với cách NOWJ tính điểm doc-level (MaxSim kiểu
  ColBERT) ⇒ thiết kế này đã được ngành xác nhận.

## 6. Backlog xếp theo ROI

| # | Việc | Công | Lợi |
|---|---|---|---|
| 1 | Ghi `query_log` (query, kết quả, click) | 1 giờ | Mở khoá mọi thứ về sau. Mỗi ngày trễ là mất dữ liệu pilot |
| 2 | Nâng `ef_search`/`cand` của production bằng lúc eval | 5 phút | Lấy lại recall đã đo, gần như không tốn latency |
| 3 | Đưa `doc_type` xuống `chunks`, lọc trong lúc quét index | 1 giờ | Sửa một tính năng đang phản tác dụng |
| 4 | Bộ eval LLM-judge 50-100 query, dùng để SO cấu hình | 1 ngày | Có thước đo thật; mọi cải tiến sau đều dựa vào nó |
| 5 | Thử reranker, đo latency trên ĐÚNG server trước khi bật | 1-2 ngày | Cải thiện lớn nhất, nhưng rủi ro latency |
| 6 | Bỏ/hiệu chuẩn con số phần trăm trên UI | 30 phút | Rủi ro niềm tin trong bối cảnh toà án |

**Số 4 phải làm trước số 5**, nếu không sẽ bật reranker mà không chứng minh được nó giúp gì.

## 7. Thí nghiệm đề xuất cho máy mạnh

Ba câu hỏi cần số đo thật, chạy được trên máy có GPU + index đầy đủ:

1. **Điểm vận hành**: chạy `eval_run.py` với `EVAL_CAND/EVAL_EFSEARCH` = (200,200) so với
   (500,500) so với (1000,1000). Trả lời: nâng lên có thật sự tăng recall không, tốn thêm bao nhiêu ms.
2. **Lọc section**: thêm điều kiện `section IN ('noi_dung','nhan_dinh')` vào CTE dense rồi
   đo lại. Trả lời: cắt 1/3 chunk boilerplate giúp hay hại.
3. **Reranker**: lấy top-50 chunk từ dense → rerank bằng `AITeamVN/Vietnamese_Reranker` →
   đo lại nDCG/Recall, ĐỒNG THỜI đo latency trên CPU giống server prod (không phải trên GPU).

Cả ba nên đo trên gold set LLM-judge (việc số 4), không phải trên exact-source, vì lý do ở mục 4.

## Nguồn

- NOWJ@COLIEE 2026: https://arxiv.org/pdf/2607.16603
- Overview COLIEE 2025: https://dl.acm.org/doi/10.1145/3769126.3785016
- AITeamVN/Vietnamese_Embedding · Vietnamese_Reranker: https://huggingface.co/AITeamVN/Vietnamese_Embedding · https://huggingface.co/AITeamVN/Vietnamese_Reranker
- VN-MTEB (EACL 2026): https://arxiv.org/abs/2507.21500
- UMBRELA: https://arxiv.org/html/2406.06519v1 · phản biện: https://arxiv.org/abs/2412.17156
- LeCaRDv2: https://arxiv.org/pdf/2310.17609
