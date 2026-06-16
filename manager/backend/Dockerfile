# Backend tìm kiếm (FastAPI) — SERVER TỰ EMBED query (dense) nên cần torch (CPU) +
# sentence-transformers + model AITeamVN. Model được BAKE sẵn vào image -> server chỉ
# `docker pull` là chạy ngay (không tải HF lúc runtime). Layer xếp theo độ ổn định:
# deps -> model (ít đổi, pull 1 lần) -> code (đổi thường, chỉ layer này re-pull khi update).
# Build từ REPO ROOT:  docker build -t legal-backend -f manager/backend/Dockerfile .
FROM python:3.12-slim
WORKDIR /app
ENV HF_HOME=/app/.hf_cache \
    PYTHONUNBUFFERED=1

# 1) deps — torch CPU (nhẹ hơn nhiều bản CUDA) + sentence-transformers + api libs
COPY manager/backend/requirements.txt /app/manager/backend/requirements.txt
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r /app/manager/backend/requirements.txt

# 2) bake model vào image (layer riêng) — khởi động không cần mạng/HF, version khớp index
ARG EMBED_MODEL=AITeamVN/Vietnamese_Embedding
ENV EMBED_MODEL=${EMBED_MODEL}
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBED_MODEL}')"

# 3) code backend (cwd=/app, main.py chdir về /app)
COPY utils.py legacy_decode.py vni_decode.py /app/
COPY manager/ingest.py /app/manager/ingest.py
COPY manager/backend/ /app/manager/backend/
COPY data/vi_syllables.txt /app/data/vi_syllables.txt

ENV PG_DSN=postgresql://legal:legal@db:5432/legal
EXPOSE 8000
CMD ["uvicorn", "manager.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
