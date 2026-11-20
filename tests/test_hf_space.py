"""The deploy's Space setup script, against a fake Hugging Face API."""
from __future__ import annotations

import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / ".github" / "scripts" / "hf_space.py"


def load_script():
    spec = importlib.util.spec_from_file_location("hf_space", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeHub:
    """Just enough of the Hub API: whoami, spaces, create, hardware, secrets, variables."""

    def __init__(self, user="asha", spaces=None, valid_token="hf_good"):
        self.user = user
        self.valid_token = valid_token
        self.spaces = spaces or {}
        self.calls = []

    def handle(self, method, path, token, body):
        self.calls.append((method, path, body))
        if token != self.valid_token:
            return 401, {"error": "Invalid username or password."}
        if path == "/api/whoami-v2":
            return 200, {"name": self.user, "orgs": []}
        if path == "/api/repos/create" and method == "POST":
            sid = f"{body.get('organization') or self.user}/{body['name']}"
            self.spaces[sid] = {"id": sid, "sdk": body["sdk"], "hardware": body["hardware"], "secrets": {}, "variables": {}}
            return 200, {"url": f"https://huggingface.co/spaces/{sid}"}
        parts = path.split("/")  # ['', 'api', 'spaces', owner, name, (action)]
        sid = "/".join(parts[3:5])
        space = self.spaces.get(sid)
        if space is None:
            return 404, {"error": "Repository not found"}
        action = parts[5] if len(parts) > 5 else None
        if action is None:
            sub = sid.replace("/", "-").lower()
            return 200, {"id": sid, "sdk": space["sdk"], "subdomain": sub, "host": f"https://{sub}.hf.space",
                         "runtime": {"hardware": {"requested": space["hardware"]}}}
        if action == "hardware":
            if space["hardware"].startswith("zero"):
                return 402, {"error": "Without a PRO subscription, you can't downgrade this Space to cpu-basic."}
            space["hardware"] = body["flavor"]
            return 200, {}
        if action in ("secrets", "variables"):
            space[action][body["key"]] = body["value"]
            return 200, {}
        return 404, {"error": "unknown"}


@pytest.fixture()
def hub(monkeypatch):
    fake = FakeHub()

    class Handler(BaseHTTPRequestHandler):
        def _go(self, method):
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length)) if length else None
            token = (self.headers.get("Authorization") or "")[7:]
            code, payload = fake.handle(method, self.path, token, body)
            data = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            self._go("GET")

        def do_POST(self):
            self._go("POST")

        def log_message(self, *_):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("HF_API", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setenv("HF_TOKEN", "hf_good")
    for name in ("DATABASE_URL", "GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "BETA_INVITE_CODES", "GITHUB_OUTPUT"):
        monkeypatch.delenv(name, raising=False)
    yield fake
    server.shutdown()


def test_creates_missing_space_and_configures_it(hub, monkeypatch, tmp_path):
    monkeypatch.setenv("HF_SPACE", "asha/notforgotten-app")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db/neon")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_x")
    monkeypatch.setenv("BETA_INVITE_CODES", "NF-1")
    out = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    load_script().main()

    space = hub.spaces["asha/notforgotten-app"]
    assert space["sdk"] == "docker" and space["hardware"] == "cpu-basic"
    assert space["secrets"] == {"DATABASE_URL": "postgresql://u:p@db/neon", "GROQ_API_KEY": "gsk_x", "BETA_INVITE_CODES": "NF-1"}
    assert space["variables"]["CORS_ORIGINS"] == "https://asha-notforgotten-app.hf.space"
    assert space["variables"]["COOKIE_SECURE"] == "1"
    assert space["variables"]["LLM_PROVIDER"] == "groq"
    assert out.read_text().strip() == "url=https://asha-notforgotten-app.hf.space"


def test_existing_space_is_reused(hub, monkeypatch):
    hub.spaces["asha/app"] = {"sdk": "docker", "hardware": "cpu-basic", "secrets": {}, "variables": {}}
    monkeypatch.setenv("HF_SPACE", "asha/app")
    load_script().main()
    assert not any(path == "/api/repos/create" for _, path, _ in hub.calls)


def test_zerogpu_space_gives_clear_fix(hub, monkeypatch, capsys):
    hub.spaces["asha/Notforgotten"] = {"sdk": "docker", "hardware": "zero-a10g", "secrets": {}, "variables": {}}
    monkeypatch.setenv("HF_SPACE", "asha/Notforgotten")
    with pytest.raises(SystemExit):
        load_script().main()
    assert "PRO" in capsys.readouterr().out


def test_owner_must_match_token(hub, monkeypatch, capsys):
    monkeypatch.setenv("HF_SPACE", "someone-else/app")
    with pytest.raises(SystemExit):
        load_script().main()
    assert "doesn't match the token's account 'asha'" in capsys.readouterr().out


def test_rejected_token(hub, monkeypatch, capsys):
    monkeypatch.setenv("HF_TOKEN", "hf_bad")
    monkeypatch.setenv("HF_SPACE", "asha/app")
    with pytest.raises(SystemExit):
        load_script().main()
    assert "Write" in capsys.readouterr().out
