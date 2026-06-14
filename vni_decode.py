"""Decode rác font cũ VNI → Unicode. $0, KHÔNG cần GPU. (Anh em với legacy_decode.py
cho TCVN3 — xem nó để hiểu nguyên lý chung.)

VNI khác TCVN3: nguyên âm có dấu = base + glyph-dấu (digraph), vd "oä"→ộ, "aõ"→ã,
"öï"→ự, "ñ"→đ. Bảng map suy ra systematic + xác minh bằng align boilerplate
("Ñoäc laäp"≡"Độc lập") và từ điển âm tiết.

VNI tách-âm-tiết-theo-space ("quy e àn"="quyền") KHÔNG decode 1:1 được → gác cổng
validity tự loại (để dành re-OCR).

AN TOÀN (giống TCVN3): decode THEO DÒNG; (1) chỉ kích hoạt dòng có glyph RIÊNG-VNI
(ä å ø û ï ñ ö … — không trùng chữ Việt thật, không trùng TCVN3 đã xử); (2) chỉ giữ
nếu validity âm tiết ≥ 0.6 và tăng so với gốc. Digraph (a+dấu) vốn không xuất hiện
trong chữ Việt sạch nên an toàn.

Dùng:
    python vni_decode.py            # DRY-RUN
    python vni_decode.py --apply
"""
import os
import sys
import json
import unicodedata

import legacy_decode as L   # tái dùng SYL + _valid_frac

PROCESSED = L.PROCESSED
SYL = L.SYL

_TONE = {'s': '́', 'f': '̀', 'r': '̉', 'x': '̃', 'j': '̣'}


def _C(base, tone):
    return unicodedata.normalize('NFC', base + (_TONE[tone] if tone else ''))


# glyph-dấu trên nguyên âm THƯỜNG (a e i o u y, và móc ö=ư ô=ơ)
_PT = {'ù': 's', 'ø': 'f', 'û': 'r', 'õ': 'x', 'ï': 'j'}
# glyph-dấu trên nguyên âm MŨ (a/o/e → â/ô/ê) + dấu
_CT = {'á': 's', 'à': 'f', 'å': 'r', 'ã': 'x', 'ä': 'j'}


def _build_map():
    m = {}
    for v in 'aeiouy':
        for g, t in _PT.items():
            m[v + g] = _C(v, t)
    for base, real in (('ö', 'ư'), ('ô', 'ơ')):
        m[base] = real
        for g, t in _PT.items():
            m[base + g] = _C(real, t)
    for v, circ in (('a', 'â'), ('o', 'ô'), ('e', 'ê')):
        for g, t in _CT.items():
            m[v + g] = _C(circ, t)
        m[v + 'â'] = circ                  # circ KHÔNG dấu: aâ→â, oâ→ô, eâ→ê
    m['ñ'] = 'đ'
    for k, val in list(m.items()):
        m[k.upper()] = val.upper()
    return m


VNI = _build_map()
# glyph RIÊNG-VNI (không bao giờ là chữ Việt thật / không trùng TCVN3) -> tín hiệu rác
TRIGGER = set('äÄåÅøØûÛïÏñÑöÖ')
# single TRÙNG codepoint chữ Việt thật (ô "công", õ "võ"…) -> chỉ decode khi dòng rác đậm.
# Digraph (base+dấu) không bao giờ xuất hiện trong chữ Việt sạch nên LUÔN an toàn.
_AMBIG_SINGLE = set('ôÔ')
_GARBLE = TRIGGER | {c for k in VNI for c in k if not c.isascii()}


def _decode_line(ln, with_ambig):
    out, i = [], 0
    while i < len(ln):
        if i + 1 < len(ln) and ln[i:i + 2] in VNI:          # digraph: luôn decode
            out.append(VNI[ln[i:i + 2]]); i += 2
        elif ln[i] in VNI and not ln[i].isascii():
            if ln[i] in _AMBIG_SINGLE and not with_ambig:    # ô đơn lẻ: chỉ khi rác đậm
                out.append(ln[i])
            else:
                out.append(VNI[ln[i]])
            i += 1
        else:
            out.append(ln[i]); i += 1
    return unicodedata.normalize('NFC', ''.join(out))


def fix_text(ft):
    out, changed = [], 0
    for ln in ft.split('\n'):
        if any(c in TRIGGER for c in ln):
            letters = [c for c in ln if c.isalpha()]
            dens = sum(c in _GARBLE for c in letters) / max(len(letters), 1)
            dec = _decode_line(ln, with_ambig=dens >= 0.35)
            if dec != ln and L._valid_frac(dec) >= 0.6 and L._valid_frac(dec) > L._valid_frac(ln):
                out.append(dec); changed += 1; continue
        out.append(ln)
    return '\n'.join(out), changed


def main(apply=False):
    files = [f for f in os.listdir(PROCESSED) if f.endswith(".json")]
    docs = lines = 0
    samples = []
    for fn in files:
        p = os.path.join(PROCESSED, fn)
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        ft = d.get("full_text", "")
        if not any(c in TRIGGER for c in ft):
            continue
        fixed, n = fix_text(ft)
        if not n:
            continue
        docs += 1; lines += n
        if len(samples) < 8:
            for a, b in zip(ft.split('\n'), fixed.split('\n')):
                if a != b:
                    samples.append((a, b)); break
        if apply:
            d["full_text"] = fixed
            with open(p, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)

    head = "ĐÃ SỬA & GHI" if apply else "DRY-RUN (chưa ghi)"
    print(f"=== {head}: {docs} doc, {lines} dòng decode ===")
    for a, b in samples:
        print(f"  {a[:64]!r}\n-> {b[:64]!r}")
    if docs and not apply:
        print("\n→ Chạy lại với --apply để ghi.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
