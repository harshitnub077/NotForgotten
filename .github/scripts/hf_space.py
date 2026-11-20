"""
Create and configure the Hugging Face Space that hosts NotForgotten.

Run by .github/workflows/deploy-hf.yml before each deploy. Idempotent:

1. Creates the Space (Docker SDK, free CPU basic hardware) if it doesn't exist.
2. Moves an existing Space onto CPU basic if it's on other hardware.
3. Copies the app's secrets from the environment (GitHub secrets) and sets the
   app's variables, so nothing has to be typed into Hugging Face's settings.
4. Prints the Space's public URL to $GITHUB_OUTPUT as `url`.

Environment: HF_TOKEN (Write token), HF_SPACE ("owner/name"), and optionally
DATABASE_URL, GROQ_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, BETA_INVITE_CODES.
Uses only the standard library.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

API = os.environ.get("HF_API", "https://huggingface.co")
SECRET_NAMES = ("DATABASE_URL", "GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "BETA_INVITE_CODES")


class Fail(SystemExit):
    def __init__(self, message: str) -> None:
        print(f"::error::{message}")
        super().__init__(1)


def call(method: str, path: str, token: str, body: Optional[Dict[str, Any]] = None) -> Tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API}{path}", data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            raw = res.read().decode() or "{}"
            return res.status, _json(raw)
    except urllib.error.HTTPError as err:
        return err.code, _json(err.read().decode() or "{}")


def _json(raw: str) -> Any:
    try:
        return json.loads(raw)
    except ValueError:
        return {"raw": raw[:300]}


def subdomain(space: str) -> str:
    return re.sub(r"[._/]", "-", space.replace("/", "-")).lower()


def ensure_space(token: str, space: str) -> Dict[str, Any]:
    owner, _, name = space.partition("/")
    if not owner or not name:
        raise Fail(f"HF_SPACE must look like 'owner/name', got {space!r}.")

    code, me = call("GET", "/api/whoami-v2", token)
    if code != 200:
        raise Fail("HF_TOKEN was rejected by Hugging Face. Create a new token with the 'Write' role.")
    user = me.get("name", "")
    orgs = {o.get("name") for o in me.get("orgs", []) if isinstance(o, dict)}
    print(f"Token belongs to Hugging Face user: {user}")
    if owner != user and owner not in orgs:
        raise Fail(
            f"HF_SPACE owner '{owner}' doesn't match the token's account '{user}'. "
            f"Set HF_SPACE to '{user}/{name}' or use a token from the '{owner}' account."
        )

    code, info = call("GET", f"/api/spaces/{space}", token)
    if code == 404:
        print(f"Space {space} doesn't exist yet. Creating it (Docker, CPU basic, public)…")
        body: Dict[str, Any] = {
            "type": "space",
            "name": name,
            "private": False,
            "sdk": "docker",
            "hardware": "cpu-basic",
        }
        if owner != user:
            body["organization"] = owner
        code, created = call("POST", "/api/repos/create", token, body)
        if code == 403 or code == 401:
            raise Fail(
                "The token can't create Spaces. Create a token with the 'Write' role "
                "(not fine-grained) and save it as the HF_TOKEN GitHub secret."
            )
        if code >= 400:
            raise Fail(f"Creating the Space failed (HTTP {code}): {created}")
        code, info = call("GET", f"/api/spaces/{space}", token)
    if code >= 400:
        raise Fail(f"Couldn't read the Space (HTTP {code}): {info}. Check that HF_TOKEN has write access to it.")

    if info.get("sdk") not in (None, "docker"):
        print(f"Space SDK is '{info.get('sdk')}'; the deploy will switch it to Docker.")

    hardware = ((info.get("runtime") or {}).get("hardware") or {}).get("requested")
    if hardware and hardware != "cpu-basic":
        print(f"Space hardware is '{hardware}'; requesting free CPU basic…")
        code, res = call("POST", f"/api/spaces/{space}/hardware", token, {"flavor": "cpu-basic"})
        if code == 402:
            raise Fail(
                f"Hugging Face won't move this Space off '{hardware}' without a PRO plan. "
                f"Set HF_SPACE to a new name (e.g. '{owner}/notforgotten-web') and the deploy will create a fresh one."
            )
        if code >= 400:
            raise Fail(f"Changing the hardware failed (HTTP {code}): {res}")
    return info


def configure(token: str, space: str, url: str) -> None:
    present = [n for n in SECRET_NAMES if os.environ.get(n, "").strip()]
    for key in present:
        code, res = call("POST", f"/api/spaces/{space}/secrets", token, {"key": key, "value": os.environ[key].strip()})
        if code >= 400:
            raise Fail(f"Setting secret {key} failed (HTTP {code}): {res}")
    print("Secrets set: " + (", ".join(present) if present else "none"))

    variables = {"COOKIE_SECURE": "1", "CORS_ORIGINS": url}
    if os.environ.get("GROQ_API_KEY", "").strip():
        variables.update({"LLM_PROVIDER": "groq", "LLM_MODEL": "openai/gpt-oss-120b"})
    for key, value in variables.items():
        code, res = call("POST", f"/api/spaces/{space}/variables", token, {"key": key, "value": value})
        if code >= 400:
            raise Fail(f"Setting variable {key} failed (HTTP {code}): {res}")
    print("Variables set: " + ", ".join(f"{k}={v}" for k, v in variables.items()))

    if "DATABASE_URL" not in present:
        print(
            "::warning::No DATABASE_URL secret: the app will use SQLite inside the Space, and accounts and "
            "libraries are lost whenever the Space restarts. Add your Neon URL as the DATABASE_URL GitHub secret."
        )


def main() -> None:
    token = os.environ.get("HF_TOKEN", "").strip()
    space = os.environ.get("HF_SPACE", "").strip()
    if not token:
        raise Fail("Add the HF_TOKEN repository secret (a Hugging Face token with the 'Write' role).")
    info = ensure_space(token, space)
    url = info.get("host") or f"https://{info.get('subdomain') or subdomain(space)}.hf.space"
    configure(token, space, url)
    print(f"Space ready: https://huggingface.co/spaces/{space} -> {url}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as fh:
            fh.write(f"url={url}\n")


if __name__ == "__main__":
    try:
        main()
    except Fail:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"::error::Unexpected error while preparing the Space: {exc}")
        sys.exit(1)
