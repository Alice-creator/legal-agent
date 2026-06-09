import os
import json
import multiprocessing as mp

import pymupdf

import utils

legal_data_path = os.environ.get("LEGAL_DATA", os.path.join(os.getcwd(), "data", "legal-data"))
output_path = os.environ.get("OUTPUT_DIR", os.path.join(os.getcwd(), "data", "processed"))
skip_log_path = os.path.join(output_path, "skipped_legacy.log")

# 1 GPU -> 1 OCR worker. Thêm worker chỉ tranh nhau cùng 1 GPU chứ không nhanh hơn.
SURYA_WORKERS = int(os.environ.get("SURYA_WORKERS", "1"))


def _json_path(filename):
    return os.path.join(output_path, filename.replace(".pdf", ".json"))


def _save(filename, route, full_text):
    with open(_json_path(filename), "w", encoding="utf-8") as f:
        json.dump({"filename": filename, "route": route, "full_text": full_text},
                  f, ensure_ascii=False, indent=2)


def _surya_worker(q):
    """Tiến trình GPU: nhận doc scanned từ queue, OCR bằng Surya, ghi JSON.

    Chạy song song với luồng text (CPU) ở tiến trình chính. Text dùng CPU, OCR dùng
    GPU → không giành tài nguyên, nên luồng text không bao giờ bị block vì 1 doc scan.
    """
    while True:
        item = q.get()
        if item is None:          # hết việc
            break
        idx, filename = item
        try:
            doc = pymupdf.open(os.path.join(legal_data_path, filename))
            full_text, route = utils.extract_text(doc)   # route == scanned -> Surya
            _save(filename, route, full_text)             # scanned luôn ra text (không None)
            print(f"[scan {idx}] {filename} - {route}", flush=True)
        except Exception as e:
            print(f"[scan {idx}] {filename} - ERROR: {e}", flush=True)


if __name__ == "__main__":
    os.makedirs(output_path, exist_ok=True)
    files = os.listdir(legal_data_path)
    total = len(files)

    scanned_q = mp.Queue()
    workers = [mp.Process(target=_surya_worker, args=(scanned_q,), daemon=True)
               for _ in range(SURYA_WORKERS)]
    for w in workers:
        w.start()

    # Luồng chính (CPU): text xử lý NGAY; scanned đẩy vào queue cho worker GPU, không chờ.
    n_text = n_scan = n_skip = 0
    for i, filename in enumerate(files):
        if os.path.exists(_json_path(filename)):
            continue
        try:
            doc = pymupdf.open(os.path.join(legal_data_path, filename))
            route = utils.classify(doc)

            if route == "scanned":
                scanned_q.put((i + 1, filename))          # đẩy cho GPU rồi đi tiếp ngay
                n_scan += 1
                continue

            full_text, route = utils.extract_text(doc)    # clean/glued/legacy/holes — KHÔNG OCR
            if full_text is None:                          # legacy / holes -> bỏ + log
                with open(skip_log_path, "a", encoding="utf-8") as log:
                    log.write(f"{filename}\t{route}\n")
                n_skip += 1
                print(f"[{i+1}/{total}] {filename} - SKIPPED ({route})", flush=True)
            else:
                _save(filename, route, full_text)
                n_text += 1
                print(f"[{i+1}/{total}] {filename} - {route}", flush=True)
        except Exception as e:
            print(f"[{i+1}/{total}] {filename} - ERROR: {e}", flush=True)

    print(f"--- Text xong: {n_text} ghi · {n_skip} bỏ. Còn {n_scan} doc scanned, Surya (GPU) đang xử lý nốt... ---", flush=True)
    for _ in workers:
        scanned_q.put(None)        # sentinel: 1 cái cho mỗi worker
    for w in workers:
        w.join()
    print("DONE", flush=True)
