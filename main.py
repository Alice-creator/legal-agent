import utils
import os
import json
import pymupdf

legal_data_path = os.path.join(os.getcwd(), "data", "legal-data")
output_path = os.path.join(os.getcwd(), "data", "processed")
os.makedirs(output_path, exist_ok=True)

skip_log_path = os.path.join(output_path, "skipped_legacy.log")

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
        full_text, route = utils.extract_text(doc)

        # None -> dropped on purpose (legacy font, or text doc punctured by an
        # image page). Log the route and skip.
        if full_text is None:
            with open(skip_log_path, "a", encoding="utf-8") as log:
                log.write(f"{filename}\t{route}\n")
            print(f"[{i+1}/{total}] {filename} - SKIPPED ({route})")
            continue

        result = {
            "filename": filename,
            "route": route,
            "full_text": full_text,
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"[{i+1}/{total}] {filename} - {route}")
    except Exception as e:
        print(f"[{i+1}/{total}] {filename} - ERROR: {e}")
