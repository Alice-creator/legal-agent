# Backend tìm kiếm (FastAPI). Nhẹ — KHÔNG torch/surya (embedding/build ở máy Mac).
# Build từ REPO ROOT:  docker build -t legal-backend -f manager/backend/Dockerfile .
FROM python:3.12-slim
WORKDIR /app

COPY manager/backend/requirements.txt /app/manager/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/manager/backend/requirements.txt

# code backend import (cwd=/app, main.py chdir về /app)
COPY utils.py legacy_decode.py vni_decode.py /app/
COPY manager/ingest.py /app/manager/ingest.py
COPY manager/backend/ /app/manager/backend/
COPY data/vi_syllables.txt /app/data/vi_syllables.txt

ENV PG_DSN=postgresql://legal:legal@db:5432/legal
EXPOSE 8000
CMD ["uvicorn", "manager.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
