"""Accounts, sessions and per-user isolation."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.test_api import _wait, make_client

TEXT = (Path(__file__).resolve().parent.parent / "assets" / "demo" / "cell-energy.md").read_text()


def _anon(monkeypatch) -> TestClient:
    import ingestion.embedder as emb

    from api.main import app
    from tests.test_api import FakeEmbedder

    fake = FakeEmbedder()
    monkeypatch.setattr(emb, "get_embedder", lambda: fake)
    monkeypatch.setattr(emb, "embed_texts", lambda texts: fake.embed_many(list(texts)))
    return TestClient(app)


class TestAccounts:
    def test_data_routes_require_login(self, monkeypatch):
        with _anon(monkeypatch) as c:
            assert c.get("/api/health").status_code == 200
            for path in ("/api/today", "/api/documents", "/api/concepts", "/api/review/queue", "/api/insights"):
                assert c.get(path).status_code == 401, path
            assert c.get("/api/auth/me").status_code == 401

    def test_signup_login_logout(self, monkeypatch):
        with make_client(monkeypatch) as c:
            me = c.get("/api/auth/me").json()["user"]
            assert me["email"] == "student@example.com" and me["name"] == "Asha"
            assert "password_hash" not in me
            assert c.post("/api/auth/logout").status_code == 200
            assert c.get("/api/today").status_code == 401
            bad = c.post("/api/auth/login", json={"email": "student@example.com", "password": "nope-nope"})
            assert bad.status_code == 401
            ok = c.post("/api/auth/login", json={"email": "STUDENT@example.com", "password": "correct horse"})
            assert ok.status_code == 200
            assert c.get("/api/today").status_code == 200

    def test_validation_and_duplicates(self, monkeypatch):
        with make_client(monkeypatch) as c:
            dup = c.post("/api/auth/signup", json={"email": "student@example.com", "password": "another one"})
            assert dup.status_code == 409
            assert c.post("/api/auth/signup", json={"email": "not-an-email", "password": "longenough"}).status_code == 400
            assert c.post("/api/auth/signup", json={"email": "a@b.co", "password": "short"}).status_code == 400

    def test_invite_codes(self, monkeypatch):
        monkeypatch.setenv("BETA_INVITE_CODES", "ALPHA,BETA")
        with _anon(monkeypatch) as c:
            assert c.get("/api/auth/config").json()["invite_required"] is True
            body = {"email": "x@y.io", "password": "longenough"}
            assert c.post("/api/auth/signup", json=body).status_code == 403
            assert c.post("/api/auth/signup", json={**body, "invite_code": "BETA"}).status_code == 200

    def test_login_rate_limited(self, monkeypatch):
        with make_client(monkeypatch) as c:
            c.post("/api/auth/logout")
            codes = [
                c.post("/api/auth/login", json={"email": "student@example.com", "password": f"wrong-{i}"}).status_code
                for i in range(10)
            ]
            assert codes[-1] == 429

    def test_password_change_revokes_other_sessions(self, monkeypatch):
        with make_client(monkeypatch) as a:
            with _anon(monkeypatch) as b:
                b.post("/api/auth/login", json={"email": "student@example.com", "password": "correct horse"})
                assert b.get("/api/today").status_code == 200
                res = a.post("/api/auth/password", json={"current_password": "correct horse", "new_password": "battery staple"})
                assert res.status_code == 200
                assert a.get("/api/today").status_code == 200  # this browser re-issued
                assert b.get("/api/today").status_code == 401  # others signed out

    def test_cross_site_post_blocked(self, monkeypatch):
        with make_client(monkeypatch) as c:
            res = c.post("/api/exams", json={"name": "x", "exam_date": "2099-01-01"}, headers={"Origin": "https://evil.example"})
            assert res.status_code == 403


class TestIsolation:
    def test_users_never_see_each_other(self, monkeypatch):
        with make_client(monkeypatch, "a@example.com") as a, make_client(monkeypatch, "b@example.com") as b:
            job = a.post("/api/documents/text", json={"title": "Cells", "text": TEXT}).json()["job_id"]
            assert _wait(a, job)["status"] == "done"

            card = a.get("/api/review/queue").json()["cards"][0]
            concept_id = card["concept_id"]
            doc_id = a.get("/api/documents").json()[0]["id"]

            # B sees an empty library…
            assert b.get("/api/documents").json() == []
            assert b.get("/api/concepts").json() == []
            assert b.get("/api/review/queue").json()["cards"] == []
            assert b.get("/api/search", params={"q": "ATP"}).json() == []
            assert b.get(f"/api/jobs/{job}").status_code == 404
            # …and cannot read or touch A's objects by id.
            assert b.get(f"/api/concepts/{concept_id}").status_code == 404
            assert b.get(f"/api/documents/{doc_id}").status_code == 404
            assert b.get(f"/api/cards/{card['id']}").status_code == 404
            assert b.post("/api/review/answer", json={"card_id": card["id"], "rating": 3}).status_code == 404
            assert b.post("/api/review/grade", json={"card_id": card["id"], "response": "x"}).status_code == 404
            assert b.patch(f"/api/cards/{card['id']}", json={"prompt": "hacked?"}).status_code == 404
            assert b.delete(f"/api/cards/{card['id']}").status_code == 404
            assert b.delete(f"/api/documents/{doc_id}").status_code == 404
            assert b.post(f"/api/concepts/{concept_id}/feynman", json={"explanation": "trying to peek here"}).status_code == 404

            # A's data is intact and A's settings are A's own.
            assert a.get(f"/api/cards/{card['id']}").json()["prompt"] == card["prompt"]
            b.patch("/api/settings", json={"desired_retention": 0.8})
            assert a.get("/api/settings").json()["desired_retention"] == pytest.approx(0.9)

    def test_export_and_delete_account(self, monkeypatch):
        with make_client(monkeypatch) as c:
            job = c.post("/api/documents/text", json={"title": "Cells", "text": TEXT}).json()["job_id"]
            assert _wait(c, job)["status"] == "done"
            data = c.get("/api/auth/export").json()
            assert data["user"]["email"] == "student@example.com"
            assert data["documents"] and data["cards"]

            assert c.post("/api/auth/delete", json={"password": "wrong password"}).status_code == 401
            assert c.post("/api/auth/delete", json={"password": "correct horse"}).status_code == 200
            assert c.get("/api/today").status_code == 401
            again = c.post("/api/auth/login", json={"email": "student@example.com", "password": "correct horse"})
            assert again.status_code == 401

            from memory.schema import get_conn

            with get_conn() as conn:
                for table in ("documents", "cards", "chunks", "concepts", "reviews"):
                    assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0, table


def test_first_account_claims_pre_accounts_library(monkeypatch):
    """A library created before accounts existed belongs to the first sign-up."""
    from core.util import iso, utcnow
    from memory.schema import get_conn, init_db

    init_db()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO documents (id, title, kind, status, created_at) VALUES ('legacy', 'Old notes', 'text', 'ready', ?)",
            (iso(utcnow()),),
        )
    with make_client(monkeypatch, "owner@example.com") as owner, make_client(monkeypatch, "second@example.com") as second:
        assert [d["id"] for d in owner.get("/api/documents").json()] == ["legacy"]
        assert second.get("/api/documents").json() == []
