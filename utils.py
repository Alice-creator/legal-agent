import os
import re
import time
import base64
from dotenv import load_dotenv
from ollama import Client

load_dotenv()

# Switch between local and cloud by changing this. Cloud tags end with '-cloud'.
# Local: 'qwen2.5vl:7b'
# Cloud: 'gemma4:31b-cloud', 'qwen3-vl:235b-cloud', 'ministral-3:8b-cloud'
MODEL = 'gemma4:31b-cloud'

SECTION_PATTERN = re.compile(
    r'(NỘI\s+DUNG\s+VỤ\s+ÁN|NHẬN\s+ĐỊNH\s+CỦA\s+TÒA\s+ÁN|QUYẾT\s+ĐỊNH(?!\s+(?:ĐÌNH|CÔNG|TUYÊN|GIẢI|VỀ)))\s*:?'
)


def _build_client():
    if MODEL.endswith('-cloud'):
        return Client(
            host='https://ollama.com',
            headers={'Authorization': f'Bearer {os.environ["OLLAMA_API_KEY"]}'},
        )
    return Client()


_client = _build_client()

PAGES_PER_BATCH = 4
MAX_RETRIES = 5


def _extract_batch(images):
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            response = _client.chat(model=MODEL, messages=[{
                'role': 'user',
                'images': images,
                'content': (
                    'Extract ALL text from these Vietnamese court judgment pages.\n'
                    'Keep the original structure and section headers.\n'
                    'Return only the extracted text, nothing else.'
                )
            }])
            return response['message']['content']
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
    raise last_err


def extract_text(doc):
    """Extract text from PDF pages as images using vision model in batches.

    Falls back to per-page on batch failure (cloud timeouts, Metal crashes).
    """
    all_images = []
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        all_images.append(base64.b64encode(pix.tobytes('png')).decode('utf-8'))

    if not all_images:
        return ""

    parts = []
    for start in range(0, len(all_images), PAGES_PER_BATCH):
        batch = all_images[start:start + PAGES_PER_BATCH]
        try:
            parts.append(_extract_batch(batch))
        except Exception:
            for img in batch:
                parts.append(_extract_batch([img]))

    return '\n'.join(parts)


def split_sections(text):
    """Split court judgment text into 4 sections by regex on standard headers."""
    if not text.strip():
        return {"opening": "", "noi_dung_vu_an": "", "nhan_dinh_cua_toa_an": "", "quyet_dinh": ""}

    parts = SECTION_PATTERN.split(text)

    sections = {"opening": parts[0].strip()}
    for header, content in zip(parts[1::2], parts[2::2]):
        normalized = re.sub(r'\s+', ' ', header.strip()).upper()
        if 'NỘI DUNG' in normalized:
            sections['NỘI DUNG VỤ ÁN'] = content.strip()
        elif 'NHẬN ĐỊNH' in normalized:
            sections['NHẬN ĐỊNH CỦA TÒA ÁN'] = content.strip()
        elif 'QUYẾT ĐỊNH' in normalized:
            sections['QUYẾT ĐỊNH'] = content.strip()

    return {
        "opening": sections.get("opening", ""),
        "noi_dung_vu_an": sections.get("NỘI DUNG VỤ ÁN", ""),
        "nhan_dinh_cua_toa_an": sections.get("NHẬN ĐỊNH CỦA TÒA ÁN", ""),
        "quyet_dinh": sections.get("QUYẾT ĐỊNH", ""),
    }
