# ── 1. Build the web app ─────────────────────────────────────────────
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── 2. Python runtime: API + built frontend on one port ─────────────
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DB_PATH=/data/memory.db \
    CHROMA_DB_DIR=/data/chroma \
    HF_HOME=/data/hf_cache \
    SENTENCE_TRANSFORMERS_HOME=/data/hf_cache
WORKDIR /app

# CPU-only torch keeps the image small; sentence-transformers pulls it in otherwise.
COPY requirements.txt ./
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt

COPY api ./api
COPY core ./core
COPY ingestion ./ingestion
COPY knowledge_graph ./knowledge_graph
COPY llm ./llm
COPY memory ./memory
COPY nlp ./nlp
COPY retrieval ./retrieval
COPY assets ./assets
COPY --from=web /web/dist ./frontend/dist

# Bake the embedding model into the image so first start is instant and offline.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', cache_folder='/opt/models')"
ENV SENTENCE_TRANSFORMERS_HOME=/opt/models

VOLUME ["/data"]
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/health')"
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
