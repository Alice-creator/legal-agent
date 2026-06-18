#!/usr/bin/env python3
"""Lan can an toàn cho `rm` — chặn 2 mẫu nguy hiểm trước khi Bash chạy.

Được gọi bởi hook PreToolUse (matcher Bash) trong .claude/settings.json.
Đọc JSON {tool_name, tool_input.command} từ stdin.
  - Vô hại  -> exit 0 (cho chạy).
  - Nguy hiểm -> ghi lý do ra stderr + exit 2 (Claude Code chặn, đưa lý do lại cho Claude).

Bài học gốc: một lần `tar -x` sai thư mục nhưng `rm /tmp/pdfs.tar` chung block vẫn
chạy -> mất 38GB. Hook này chặn đúng tình huống đó, KHÔNG cản các rm thường ngày.
"""
import json
import re
import sys

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)  # không parse được -> không chặn

if data.get("tool_name") != "Bash":
    sys.exit(0)

cmd = (data.get("tool_input") or {}).get("command", "") or ""

# chỉ quan tâm lệnh có `rm`
if not re.search(r"(^|[\s;&|(])rm(\s|$)", cmd):
    sys.exit(0)

reasons = []

# (1) rm đi CHUNG dòng với tải/giải nén -> đúng vụ mất 38GB
if re.search(r"\b(tar|curl|wget|unzip|gunzip|scp|rsync)\b", cmd) and \
   re.search(r"(&&|;|\|).*\brm\b", cmd):
    reasons.append(
        "`rm` đi chung dòng với tải/giải nén (tar/curl/wget/unzip…). "
        "TÁCH `rm` ra lệnh RIÊNG, chạy SAU khi đã giải nén + verify "
        "(đã mất 38GB vì lỗi này một lần)."
    )

# (2) rm -r/-f nhắm đường nhạy cảm
has_force = re.search(r"\brm\b[^|;&]*\s-{1,2}[a-z]*(r|f|recursive|force)", cmd) is not None
if has_force:
    protected = [
        (r"\bdata/(legal-data|processed)?", "data/ (corpus đã trích xuất)"),
        (r"\bpdfs?\b", "pdfs/ (38GB PDF gốc)"),
        (r"(^|\s)/(\s|$|\*)", "/ (gốc hệ thống)"),
        (r"(^|\s)~(/|\s|$)", "~ (home)"),
        (r"\$HOME\b", "$HOME"),
        (r"(^|\s)\*(\s|$)", "* (glob trần — dễ quét nhầm)"),
    ]
    for pat, label in protected:
        if re.search(pat, cmd):
            reasons.append(f"`rm -rf` nhắm đường nhạy cảm: {label}. Soi kỹ path tuyệt đối trước khi xoá.")

if reasons:
    sys.stderr.write(
        "⛔ LAN CAN rm (.claude/hooks/guard-rm.py) chặn lệnh:\n  $ " + cmd.strip() + "\n\n- "
        + "\n- ".join(reasons)
        + "\n\nNếu chắc chắn cần xoá: tách `rm` thành lệnh riêng, ghi path tuyệt đối rõ ràng, "
        "hoặc xin user xác nhận rồi chạy lại.\n"
    )
    sys.exit(2)

sys.exit(0)
