"""Gỡ các doc font cũ (TCVN3/VNI) đã LỌT vào data/processed (full_text là rác).

Một số doc VNI lọt qua vì bộ nhận diện ban đầu chỉ tune cho TCVN3. Sau khi đã vá
utils.LEGACY_SIG (thêm chữ ký VNI), script này quét lại các JSON đã ghi: đo mật độ
ký tự font-cũ trên full_text bằng ĐÚNG tiêu chí của utils (LEGACY_SIG + LEGACY_DENSITY);
doc nào vượt ngưỡng -> xoá JSON + ghi vào skipped_legacy.log (giống như nếu classify
bắt được ngay từ đầu). Không cần đọc lại PDF.

Doc font-LẪN (chỉ header/footer font cũ, thân Unicode) có mật độ thấp -> GIỮ.
Chỉ doc rác nặng (VNI/TCVN3-full) mới vượt ngưỡng -> xoá.

Dùng:
    python purge_legacy.py            # DRY-RUN: chỉ báo cáo
    python purge_legacy.py --apply    # xoá thật + ghi log
"""
import os
import sys
import json

import utils

PROCESSED = os.path.join(os.getcwd(), "data", "processed")
SKIP_LOG = os.path.join(PROCESSED, "skipped_legacy.log")

# Chỉ gỡ doc RÁC TOÀN PHẦN (VNI/TCVN3-full, ~mật độ 4-5%). Đặt cao hơn ngưỡng
# routing (utils.LEGACY_DENSITY=0.005) một cách CÓ CHỦ Ý: doc LẪN (thân Unicode sạch
# + 1 mẩu footer/đoạn font cũ) có mật độ 0.5-2% -> GIỮ lại vì thân vẫn dùng được.
PURGE_DENSITY = 0.02


def legacy_density(text):
    s = text.strip()
    if not s:
        return 0.0
    return len(utils.LEGACY_SIG.findall(s)) / len(s)


def main(apply=False):
    files = [f for f in os.listdir(PROCESSED) if f.endswith(".json")]
    hits = []
    for fn in files:
        try:
            d = json.load(open(os.path.join(PROCESSED, fn), encoding="utf-8"))
        except Exception:
            continue
        dens = legacy_density(d.get("full_text", ""))
        if dens > PURGE_DENSITY:
            hits.append((fn, d.get("route"), round(dens, 4)))

    head = "ĐÃ XOÁ" if apply else "DRY-RUN (chưa xoá)"
    print(f"=== {head}: {len(hits)}/{len(files)} doc rác-toàn-phần (density > {PURGE_DENSITY}) ===")
    for fn, route, dens in sorted(hits, key=lambda x: -x[2])[:12]:
        print(f"  {fn}  route={route}  density={dens}")
    if apply:
        for fn, _, _ in hits:
            os.remove(os.path.join(PROCESSED, fn))
            with open(SKIP_LOG, "a", encoding="utf-8") as log:
                log.write(f"{fn.replace('.json', '.pdf')}\tlegacy-vni\n")
        print(f"\nĐã xoá {len(hits)} JSON, ghi vào {SKIP_LOG}")
    elif hits:
        print("\n→ Chạy lại với --apply để xoá.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
