import utils
import os
import json
import pymupdf

legal_data_path = os.path.join(os.getcwd(), "data", "legal-data")
output_path = os.path.join(os.getcwd(), "data", "processed")
os.makedirs(output_path, exist_ok=True)

files = os.listdir(legal_data_path)
total = len(files)

for i, filename in enumerate(files):
    json_name = filename.replace(".pdf", ".json")
    json_path = os.path.join(output_path, json_name)

    # Skip if already processed
    if os.path.exists(json_path):
        continue

    filepath = os.path.join(legal_data_path, filename)
    try:
        doc = pymupdf.open(filepath)
        full_text = utils.extract_text(doc)
        sections = utils.split_sections(full_text)

        result = {
            "filename": filename,
            "full_text": full_text,
            "opening": sections["opening"],
            "noi_dung_vu_an": sections["noi_dung_vu_an"],
            "nhan_dinh_cua_toa_an": sections["nhan_dinh_cua_toa_an"],
            "quyet_dinh": sections["quyet_dinh"],
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"[{i+1}/{total}] {filename} - done")
    except Exception as e:
        print(f"[{i+1}/{total}] {filename} - ERROR: {e}")
