# NotForgotten

**Remember it on exam day.** NotForgotten turns your PDFs, notes and articles into recall questions, schedules each one just before you'd forget it, and plans backwards from your exam date.

It is not another flashcard app. The unit of memory is the **concept**: concepts are discovered automatically, linked in a prerequisite graph where forgetting propagates, reviewed by *typing* answers that are graded on meaning, and scheduled with **FSRS-6**, the state-of-the-art spaced-repetition model, fitted to how *you* forget.

---

## What it does

| | |
|---|---|
| **Add anything** | Drag in PDFs, Markdown/TXT, paste notes, or import a web page. Concepts are discovered, named, summarised and linked. |
| **Recall questions, written for you** | Question/answer, fill-the-gap and "explain why" cards following the minimum-information principle (LLM, with an offline fallback). |
| **Typed recall, graded** | You write the answer from memory. It's graded on meaning (LLM rubric, or sentence-embedding similarity + key-term recall offline) and mapped to an FSRS rating. |
| **Confidence calibration** | Say how sure you are before checking. Insights report Brier score, calibration error and over/under-confidence: the "illusion of competence", measured. |
| **Smart queues** | *Due*, *time-boxed* ("I have 10 minutes": the reviews that protect the most memory per second), *weakest first*, and *exam* modes, interleaved across concepts. |
| **Knowledge map** | Force-directed concept graph with a **time machine**: drag the clock forward to see what fades if you stop studying. |
| **Shaky foundations** | If a concept builds on prerequisites you're forgetting, its *effective* recall is discounted and the weak foundations are named. |
| **Exam planner** | Set a date and target recall; it simulates every day until then, adds just-in-time final reviews, and reports minutes/day and projected exam-day recall. |
| **Memory-aware tutor** | Streaming chat (explain / Socratic / quiz) that cites your sources, slips in recall checks on fading concepts, and turns answers into cards. |
| **Feynman mode** | Explain a concept in plain words; get coverage, clarity, missed ideas and a probing follow-up question. |
| **Insights** | Year heatmap, true retention, keep-vs-stop forecast, workload forecast, memory-strength distribution, interactive forgetting-curve playground. |
| **Personal forgetting curve** | One click fits FSRS parameters to your own review history (regularised maximum likelihood). |

Each student has a **private account**: sign up, log in from any device, and their library, review history and exam plans sync through a hosted Postgres database. Data export and account deletion are built in.

Everything works **without an API key**. An LLM (Groq, OpenAI or Anthropic) makes questions, grading and tutoring richer.

---

## The maths

### FSRS-6 memory model (`memory/fsrs.py`)
Each card has difficulty *D*, stability *S* (days until recall drops to 90%) and retrievability *R*:

```
R(t, S) = (1 + F·t/S)^(−w20),     F = 0.9^(−1/w20) − 1
```

A power law, not Ebbinghaus' exponential: a population of memories with different decay rates averages to a power law, and it fits real review logs better. Stability grows after successful recall by

```
S' = S · (1 + e^w8 · (11 − D) · S^(−w9) · (e^(w10·(1−R)) − 1) · hard/easy modifiers)
```

so recalling at *lower* R yields a *bigger* gain (the spacing effect), and lapses use the post-forgetting stability formula. All 21 FSRS-6 default weights are included.

### Value of a review (`memory/planner.py`)
The area under the forgetting curve has a closed form ("retention-days"):

```
∫ R dt = S / (F·(1−d)) · [(1 + F·t/S)^(1−d)] evaluated over the horizon
```

The expected gain of reviewing now over a 30-day horizon is

```
gain = R·A(S_recall) + (1−R)·A(S_lapse) − A(no review)
```

and dividing by the expected seconds per review gives *retention-days per second*. Time-boxed sessions are a greedy knapsack over that ratio.

### Forgetting propagation (`knowledge_graph/propagation.py`)
For prerequisite edges u → v with similarity weight w, evaluated in topological order:

```
R_eff(v) = R(v) · Π (1 − λ·w·max(0, τ − R_eff(u)) / τ),   τ = 0.9
```

### Calibration (`memory/calibration.py`)
Brier score, expected calibration error, resolution and overconfidence = mean(confidence) − accuracy.

### Personal parameters (`memory/optimizer.py`)
MAP estimate over key FSRS weights: binary cross-entropy of predicted R against actual recall on spaced reviews, plus a Gaussian prior centred on the population defaults (strength fades with evidence), optimised with bounded L-BFGS-B. A fit is accepted only if log-loss improves and calibration doesn't degrade.

### Concept discovery (`nlp/concepts.py`)
Author structure first (headed sections become concepts; oversized ones are sub-clustered); otherwise position-aware Ward clustering of sentence embeddings with silhouette model selection inside a granularity prior. Concepts are named with class-based TF-IDF (or an LLM) and linked by centroid similarity.

---

## Architecture

```
frontend/   React 18 + Vite + TypeScript — "terminal wayfinding" design system, hand-built SVG charts, d3-force graph
api/        FastAPI routes (/api/*), SSE streaming tutor; serves frontend/dist in production
core/       settings, card memory, analytics read models, demo library
memory/     FSRS-6, planner, calibration, optimizer, SQLite schema (+ legacy SM-2)
nlp/        text utils, concept discovery, card generation, grading
ingestion/  PDF / text / URL extraction, chunking, embeddings, background pipeline
retrieval/  ChromaDB vector store + forgetting-aware reranking
knowledge_graph/  prerequisite propagation
llm/        provider-agnostic client (Groq / OpenAI / Anthropic) with offline degradation
```

Storage: SQLite (`data/memory.db`) locally, or hosted **Postgres** when `DATABASE_URL` is set. Passages, their embeddings, cards, reviews and accounts all live in that one database; semantic search is exact per-user cosine similarity over the stored embeddings (`all-MiniLM-L6-v2`), so there is no separate vector database to run. See [docs/DEPLOY_HF.md](docs/DEPLOY_HF.md) to host a free beta (Hugging Face Space + Neon), or [docs/DEPLOY.md](docs/DEPLOY.md) for other hosts.

---

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optionally add GROQ_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY
```

Run the API:

```bash
.venv/bin/uvicorn api.main:app --port 8080
```

Run the web app (in another terminal):

```bash
npm --prefix frontend install && npm --prefix frontend run dev
```

Open http://localhost:5173 and choose **Try the demo library** to explore with sample texts and a simulated two-month study history, or add your own material.

For a single-server production build:

```bash
npm --prefix frontend run build && .venv/bin/uvicorn api.main:app --port 8080
```

### Docker (one container, data in a volume)

```bash
docker compose up --build
```

Then open http://localhost:8080. The image bakes in the embedding model and serves the API and the web app on one port; your library lives in the `notforgotten-data` volume. Put an LLM key in `.env` to enable AI features.

> For a public deployment set `DATABASE_URL`, `COOKIE_SECURE=1` and `CORS_ORIGINS`, and optionally `BETA_INVITE_CODES`. See [docs/DEPLOY.md](docs/DEPLOY.md).

## Tests

```bash
.venv/bin/python -m pytest
```

108 tests (run on both SQLite and Postgres in CI) cover accounts and cross-user isolation, the FSRS model (curve inversion, closed-form integrals vs numeric), planning, calibration, the optimizer recovering a synthetic learner, clustering, card generation, grading, propagation, retrieval, extraction, and a full offline API learning loop.

## Roadmap

- Password reset by email; Google sign-in
- Mobile app (PWA first) with study reminders
- Image occlusion for diagrams; OCR for scanned PDFs
- Spaced *interleaved problem practice* for maths and physics
- Shared class decks for teachers, with cohort analytics
