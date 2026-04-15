import re
import json
import ollama


def extract_text(doc):
    """Extract text from PDF document, page by page. Skip image-only pages."""
    pages = []
    for page in doc:
        raw = " ".join(w[4] for w in page.get_text("words"))
        if len(raw.strip()) > 50:
            fixed = _fix_spacing_llm(raw)
            pages.append(fixed)
    return "\n".join(pages)


def _fix_spacing_llm(page_text):
    """Use Qwen to fix broken Vietnamese text spacing for a single page."""
    response = ollama.chat(model='qwen2.5:14b', messages=[{
        'role': 'user',
        'content': (
            'Fix the spacing in this Vietnamese legal text. '
            'Only fix spacing — do not change, translate, or summarize any words. '
            'Return only the fixed text, nothing else.\n\n'
            f'{page_text}'
        )
    }])
    return response['message']['content']


def split_sections(text):
    """Split court judgment text into 4 sections using LLM to find boundaries."""
    if not text.strip():
        return {"opening": "", "NỘI DUNG VỤ ÁN": "", "NHẬN ĐỊNH CỦA TÒA ÁN": "", "QUYẾT ĐỊNH": ""}

    response = ollama.chat(model='qwen2.5:14b', messages=[{
        'role': 'user',
        'content': (
            'Find the section headers in this Vietnamese court judgment.\n'
            'For each section header found, return a quote of ~30 characters '
            'from the document that starts with the header text.\n\n'
            'Look for these 3 headers:\n'
            '1. NỘI DUNG VỤ ÁN\n'
            '2. NHẬN ĐỊNH CỦA TÒA ÁN\n'
            '3. QUYẾT ĐỊNH (the section header before the verdict, '
            'NOT the document title like "QUYẾT ĐỊNH ĐÌNH CHỈ...")\n\n'
            'Return JSON with format:\n'
            '{"noi_dung_vu_an": "~30 char quote starting with header, or null",\n'
            ' "nhan_dinh_cua_toa_an": "~30 char quote starting with header, or null",\n'
            ' "quyet_dinh": "~30 char quote starting with header, or null"}\n\n'
            f'{text}'
        )
    }], format='json')

    boundaries = json.loads(response['message']['content'])

    header_map = {
        'noi_dung_vu_an': 'NỘI DUNG VỤ ÁN',
        'nhan_dinh_cua_toa_an': 'NHẬN ĐỊNH CỦA TÒA ÁN',
        'quyet_dinh': 'QUYẾT ĐỊNH',
    }

    # Find each boundary position in the text
    split_points = []
    for key, header_name in header_map.items():
        quote = boundaries.get(key)
        if not quote:
            continue

        idx = text.find(quote)
        if idx == -1:
            # Try progressively shorter prefixes of the quote
            for length in range(len(quote) - 1, 9, -1):
                idx = text.find(quote[:length])
                if idx != -1:
                    break
        if idx == -1:
            # Last resort: search for the header name directly
            match = re.search(re.escape(header_name), text)
            if match:
                idx = match.start()

        if idx != -1:
            split_points.append((idx, header_name))

    split_points.sort()

    # Split text at the boundaries
    sections = {"opening": "", "NỘI DUNG VỤ ÁN": "", "NHẬN ĐỊNH CỦA TÒA ÁN": "", "QUYẾT ĐỊNH": ""}

    if not split_points:
        sections["opening"] = text.strip()
    else:
        sections["opening"] = text[:split_points[0][0]].strip()
        for i, (pos, header) in enumerate(split_points):
            end = split_points[i + 1][0] if i + 1 < len(split_points) else len(text)
            content_start = pos + len(header)
            content = text[content_start:end].strip().lstrip(':').strip()
            sections[header] = content

    return sections
