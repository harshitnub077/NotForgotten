"""End-to-end API test: ingest → review → analytics, fully offline."""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

DIM = 64


class FakeEmbedder:
    """Deterministic hashed bag-of-words embeddings (no model download)."""

    dimension = DIM

    def embed_many(self, texts):
        out = np.zeros((len(texts), DIM), dtype=np.float32)
        for i, t in enumerate(texts):
            for w in t.lower().split():
                h = int(hashlib.md5(w.strip(".,;:").encode()).hexdigest(), 16)
                out[i, h % DIM] += 1.0
            n = np.linalg.norm(out[i])
            out[i] = out[i] / n if n else out[i]
        return out

    def embed(self, text):
        return self.embed_many([text])[0].tolist()


def make_client(monkeypatch, email="student@example.com"):
    import ingestion.embedder as emb

    fake = FakeEmbedder()
    monkeypatch.setattr(emb, "get_embedder", lambda: fake)
    monkeypatch.setattr(emb, "embed_texts", lambda texts: fake.embed_many(list(texts)))

    from fastapi.testclient import TestClient

    from api.main import app

    c = TestClient(app)
    res = c.post("/api/auth/signup", json={"email": email, "password": "correct horse", "name": "Asha"})
    assert res.status_code == 200, res.text
    return c


@pytest.fixture()
def client(monkeypatch):
    with make_client(monkeypatch) as c:
        yield c


def _wait(client, job_id, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] != "running":
            return job
        time.sleep(0.2)
    raise AssertionError("job timed out")


def _ingest(client):
    text = (Path(__file__).resolve().parent.parent / "assets" / "demo" / "cell-energy.md").read_text()
    res = client.post("/api/documents/text", json={"title": "Cell energy", "text": text})
    assert res.status_code == 200
    job = _wait(client, res.json()["job_id"])
    assert job["status"] == "done", job
    return res.json()["document_id"]


def test_full_learning_loop(client):
    assert client.get("/api/health").json()["status"] == "ok"
    doc_id = _ingest(client)

    docs = client.get("/api/documents").json()
    assert docs[0]["status"] == "ready" and docs[0]["card_count"] > 0

    concepts = client.get("/api/concepts").json()
    assert len(concepts) >= 2
    graph = client.get("/api/graph").json()
    assert len(graph["nodes"]) == len(concepts)

    # Review queue: all cards are new
    q = client.get("/api/review/queue").json()
    assert q["cards"] and all(c["is_new"] for c in q["cards"])
    card = q["cards"][0]
    assert set(card["preview"]) == {"1", "2", "3", "4"}

    graded = client.post("/api/review/grade", json={"card_id": card["id"], "response": card["answer"]}).json()
    assert graded["rating"] >= 3

    ans = client.post(
        "/api/review/answer",
        json={
            "card_id": card["id"],
            "rating": graded["rating"],
            "response": card["answer"],
            "score": graded["score"],
            "confidence": 0.8,
            "duration_ms": 12000,
            "session_id": q["session_id"],
        },
    ).json()
    assert ans["stability_after"] > 0 and ans["interval_days"] >= 1
    assert ans["concept_retention"] is not None

    summary = client.get(f"/api/review/session/{q['session_id']}").json()
    assert summary["reviews"] == 1

    today = client.get("/api/today").json()
    assert today["cards_learned"] == 1 and today["streak"]["current"] == 1

    ins = client.get("/api/insights").json()
    assert ins["reviews_total"] == 1 and len(ins["heatmap"]) == 365
    assert ins["calibration"]["n"] == 1

    detail = client.get(f"/api/concepts/{card['concept_id']}").json()
    assert detail["cards_detail"] and detail["curve"][0]["r"] is not None

    fey = client.post(
        f"/api/concepts/{card['concept_id']}/feynman",
        json={"explanation": "ATP is the energy currency of the cell; breaking a phosphate bond releases energy."},
    ).json()
    assert 0 <= fey["score"] <= 1

    more = client.post(f"/api/concepts/{card['concept_id']}/generate", json={"n": 2}).json()
    assert more["created"] >= 0

    # Cram & smart modes
    assert client.get("/api/review/queue?mode=cram").json()["cards"]
    smart = client.get("/api/review/queue?mode=smart&minutes=1").json()
    assert len(smart["cards"]) <= 3

    # Exam planner
    exam_date = (datetime.now(timezone.utc) + timedelta(days=14)).date().isoformat()
    plan = client.post("/api/exams", json={"name": "Bio midterm", "exam_date": exam_date, "document_ids": [doc_id]}).json()
    assert plan["days_left"] >= 13 and len(plan["daily"]) == plan["days_left"]
    assert client.get(f"/api/review/queue?mode=exam&exam_id={plan['id']}").json()["cards"]

    # Search and tutor (offline stream)
    hits = client.get("/api/search", params={"q": "ATP synthase chemiosmosis"}).json()
    assert hits
    with client.stream("POST", "/api/tutor/chat", json={"message": "How is ATP made?"}) as resp:
        body = "".join(resp.iter_text())
    assert '"type": "meta"' in body and '"type": "done"' in body

    # Settings
    s = client.patch("/api/settings", json={"desired_retention": 0.85}).json()
    assert s["desired_retention"] == 0.85

    opt = client.post("/api/insights/optimize").json()
    assert opt["improved"] is False  # not enough history yet

    assert client.delete(f"/api/documents/{doc_id}").status_code == 200
    assert client.get("/api/concepts").json() == []


def test_rejects_bad_input(client):
    assert client.post("/api/documents/text", json={"title": "x", "text": "short"}).status_code == 422
    assert client.post("/api/documents/url", json={"url": "ftp://example.com/x"}).status_code == 400
    assert client.post("/api/review/answer", json={"card_id": "nope", "rating": 3}).status_code == 404
    assert client.post("/api/review/answer", json={"card_id": "nope", "rating": 9}).status_code == 422
    past = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()
    assert client.post("/api/exams", json={"name": "old", "exam_date": past}).status_code == 400


def test_url_ssrf_guard():
    from ingestion.extract import _assert_public_host

    with pytest.raises(ValueError):
        _assert_public_host("http://127.0.0.1:8080/admin")
    with pytest.raises(ValueError):
        _assert_public_host("file:///etc/passwd")
