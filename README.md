# NotForgotten 🧠

> **AI-powered spaced repetition learning system** — combines semantic search with the Ebbinghaus forgetting curve to surface what you're about to forget, before you forget it.

---

## Architecture

```
PDF → chunk → embed → ChromaDB (semantic store)
                           ↓
               HybridRetriever (α·semantic + (1-α)·urgency)
                           ↓
               LangGraph Agent (retrieve → generate → assess → update)
                           ↓
               SQLite (SM-2 memory) + networkx (concept graph)
                           ↓
               FastAPI (/session/* + /dashboard)
```

## Quick Start

### 1. Install dependencies
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your LLM_PROVIDER and API key
```

### 3. Start the API
```bash
uvicorn api.main:app --reload --port 8080
```

### 4. Ingest your own PDF
```bash
# Upload via curl or use the Frontend UI
curl -X POST http://localhost:8080/ingest -F "file=@your_document.pdf"
```

### 5. Begin a session
```bash
# Ask a question
curl -X POST http://localhost:8080/session/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Summarize the key points", "session_id": "abc123"}'

# Rate your understanding (1-5) to update memory
curl -X POST http://localhost:8080/session/rate \
  -H "Content-Type: application/json" \
  -d '{"session_id": "abc123", "concept_id": "your_concept_id", "rating": 4}'
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/session/start` | Returns today's highest-urgency concepts |
| POST | `/session/query` | Runs full LangGraph pipeline, returns answer + sources |
| POST | `/session/rate` | Accepts self-rating, triggers SM-2 memory update |
| GET | `/dashboard` | Full memory state JSON for frontend |

## Key Concepts

- **SM-2 Algorithm** — Spaced repetition scheduler. Low ratings → shorter intervals. High ratings → longer intervals.
- **Ebbinghaus Retention** — `R = e^(−t/S)` where `t` = days since review, `S` = stability. Low retention = high urgency.
- **Hybrid Retrieval** — `score = α × semantic_similarity + (1−α) × urgency`. Chunks from forgotten concepts get boosted automatically.
- **Re-Teach Mode** — If you rate understanding ≤ 2, the agent loops back and retrieves additional context.

## Running Tests

```bash
pytest tests/ -v

# 30-day simulation harness
python tests/simulation_harness.py
```
