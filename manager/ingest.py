"""Nạp 34k JSON (data/processed) vào PostgreSQL, kèm phân loại chất lượng.

Tái dùng phân loại bucket/reason GIỐNG detect_errors.py (theo VỊ TRÍ garble), tính
luôn legacy_density / diacritic_density / char_count. tsv tính bằng SQL
(to_tsvector('simple', unaccent(full_text))). Upsert theo filename → chạy lại an toàn.

Cần: psycopg (cài trong .venv-surya). DB mặc định postgresql://legal:legal@localhost:5433/legal
(đổi qua biến môi trường PG_DSN).

Dùng:
    .venv-surya/bin/python manager/ingest.py
"""
import os
import sys
import json
import regex
import psycopg

# import utils ở repo root để dùng LEGACY_SIG
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import utils

PROCESSED = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
DSN = os.environ.get("PG_DSN", "postgresql://legal:legal@localhost:5433/legal")

_UNI = regex.compile(
    r'[ăâêôơưđàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ]', regex.I)
LOW_DENSITY = 0.15
LEGACY_HEAVY = 0.005


def classify(full_text):
    """(bucket, reocr_reason, legacy_density, diacritic_density) — khớp detect_errors."""
    s = full_text.strip()
    n = max(len(s), 1)
    legd = len(utils.LEGACY_SIG.findall(s)) / n
    diac = len(_UNI.findall(s)) / n
    if len(s) < 150:
        return "reocr", "empty", legd, diac
    if legd >= LEGACY_HEAVY:
        return "reocr", "legacy_char", legd, diac
    if diac < LOW_DENSITY:
        return "reocr", "low_density", legd, diac
    if 0 < legd < LEGACY_HEAVY:
        in_body = any(0.12 <= m.start() / n <= 0.92 for m in utils.LEGACY_SIG.finditer(s))
        if in_body:
            return "reocr", "legacy_body", legd, diac
        return "minor", None, legd, diac
    return "clean", None, legd, diac


_SQL = """
INSERT INTO documents
  (filename, route, full_text, bucket, reocr_reason, legacy_density, diacritic_density, char_count, tsv)
VALUES
  (%s, %s, %s, %s, %s, %s, %s, %s, to_tsvector('simple', unaccent(%s)))
ON CONFLICT (filename) DO UPDATE SET
  route=EXCLUDED.route, full_text=EXCLUDED.full_text, bucket=EXCLUDED.bucket,
  reocr_reason=EXCLUDED.reocr_reason, legacy_density=EXCLUDED.legacy_density,
  diacritic_density=EXCLUDED.diacritic_density, char_count=EXCLUDED.char_count,
  tsv=EXCLUDED.tsv, updated_at=now()
"""


def main():
    files = [f for f in os.listdir(PROCESSED) if f.endswith(".json")]
    print(f"Nạp {len(files)} doc vào {DSN} ...")
    rows = []
    for fn in files:
        try:
            d = json.load(open(os.path.join(PROCESSED, fn), encoding="utf-8"))
        except Exception:
            continue
        ft = d.get("full_text", "") or ""
        bucket, reason, legd, diac = classify(ft)
        rows.append((d.get("filename", fn), d.get("route"), ft, bucket, reason,
                     round(legd, 5), round(diac, 5), len(ft.strip()), ft))

    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            B = 1000
            for i in range(0, len(rows), B):
                cur.executemany(_SQL, rows[i:i + B])
                conn.commit()
                print(f"  {min(i + B, len(rows))}/{len(rows)}", end="\r", flush=True)
            cur.execute("SELECT bucket, count(*) FROM documents GROUP BY bucket ORDER BY 2 DESC")
            print("\n=== bucket trong DB ===")
            for b, c in cur.fetchall():
                print(f"  {b:7} {c}")
            cur.execute("SELECT count(*) FROM documents")
            print(f"  TỔNG   {cur.fetchone()[0]}")


if __name__ == "__main__":
    main()
