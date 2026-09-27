"""Authentication + pairing behaviour of the local engine.

The engine binds to loopback, but any page the user visits can still reach
``127.0.0.1`` — so every ``/api`` and ``/media`` call must carry the bearer
token, while ``/api/health`` and ``/api/auth/status`` stay public for discovery.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.api import middleware

TOKEN = "secret-token"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("CLIPPER_AUTH", "1")
    monkeypatch.setenv("CLIPPER_TOKEN", TOKEN)
    from app.api.server import app

    return TestClient(app)


# --- token helpers --------------------------------------------------------
def test_token_from_header():
    assert auth.token_from_header("Bearer abc") == "abc"
    assert auth.token_from_header("bearer   abc  ") == "abc"
    assert auth.token_from_header("abc") is None
    assert auth.token_from_header("") is None
    assert auth.token_from_header(None) is None


def test_ensure_token_persists_and_rotates(monkeypatch, tmp_path):
    monkeypatch.delenv("CLIPPER_TOKEN", raising=False)
    monkeypatch.setattr(auth, "TOKEN_FILE", tmp_path / "auth.json")

    token = auth.ensure_token()
    assert token
    assert auth.get_token() == token          # stable across calls
    assert auth.verify(token)
    assert not auth.verify("nope")

    rotated = auth.rotate()
    assert rotated != token
    assert auth.verify(rotated)
    assert not auth.verify(token)             # old token is dead


def test_env_token_wins_and_never_writes(monkeypatch, tmp_path):
    monkeypatch.setenv("CLIPPER_TOKEN", "from-env")
    monkeypatch.setattr(auth, "TOKEN_FILE", tmp_path / "auth.json")
    assert auth.get_token() == "from-env"
    assert auth.ensure_token() == "from-env"
    assert not (tmp_path / "auth.json").exists()


def test_auth_enabled_toggle(monkeypatch):
    monkeypatch.delenv("CLIPPER_AUTH", raising=False)
    assert auth.auth_enabled() is True
    monkeypatch.setenv("CLIPPER_AUTH", "0")
    assert auth.auth_enabled() is False
    monkeypatch.setenv("CLIPPER_AUTH", "off")
    assert auth.auth_enabled() is False


# --- path classification --------------------------------------------------
def test_public_and_protected_paths():
    assert middleware.is_protected("/api/health") is False
    assert middleware.is_protected("/api/auth/status") is False
    assert middleware.is_protected("/") is False
    assert middleware.is_protected("/assets/index.js") is False
    assert middleware.is_protected("/api/nodes") is True
    assert middleware.is_protected("/api/projects/foo") is True
    assert middleware.is_protected("/media/foo/bar.mp4") is True


# --- HTTP enforcement -----------------------------------------------------
def test_health_is_public_and_identifies_engine(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "clipper-engine"
    assert body["auth_required"] is True


def test_auth_status_is_public(client):
    response = client.get("/api/auth/status")
    assert response.status_code == 200
    assert response.json()["auth_required"] is True


def test_api_requires_token(client):
    assert client.get("/api/nodes").status_code == 401
    assert client.get("/api/nodes", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert (
        client.get("/api/nodes", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 200
    )


def test_token_via_query_string(client):
    assert client.get(f"/api/nodes?token={TOKEN}").status_code == 200


def test_unauthorized_is_structured(client):
    response = client.get("/api/nodes")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "unauthorized"


def test_auth_verify_endpoint(client):
    assert client.get("/api/auth/verify").status_code == 401
    assert (
        client.get("/api/auth/verify", headers={"Authorization": f"Bearer {TOKEN}"}).status_code
        == 200
    )


def test_private_network_preflight_is_granted(client):
    response = client.options(
        "/api/nodes",
        headers={
            "Origin": "https://clipperpromaxgod.vercel.app",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Private-Network": "true",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-private-network"] == "true"
    assert (
        response.headers["access-control-allow-origin"]
        == "https://clipperpromaxgod.vercel.app"
    )


def test_cors_allows_project_domain_and_rejects_foreign(client):
    allowed = client.get(
        "/api/nodes", headers={"Origin": "https://clipperpromaxgod.vercel.app"}
    )
    assert allowed.status_code == 401  # auth still required
    assert (
        allowed.headers["access-control-allow-origin"]
        == "https://clipperpromaxgod.vercel.app"
    )

    foreign = client.options(
        "/api/nodes",
        headers={"Origin": "https://some-other-app.vercel.app", "Access-Control-Request-Method": "GET"},
    )
    assert foreign.status_code == 400  # tightened default rejects other Vercel apps


def test_default_origin_regex_is_scoped():
    import re

    from app.api import server

    pattern = re.compile(server.DEFAULT_ORIGIN_REGEX)
    assert pattern.match("https://clipperpromaxgod.vercel.app")
    assert pattern.match("https://clipper-promax-god.vercel.app")
    assert pattern.match("https://clipperpromaxgod-git-main-team.vercel.app")
    assert pattern.match("http://localhost:5173")
    assert pattern.match("http://127.0.0.1:8765")
    assert not pattern.match("https://some-other-app.vercel.app")
    assert not pattern.match("https://evil.vercel.app")
    assert not pattern.match("https://clipperpromaxgod.example.com")


def test_auth_disabled_allows_anonymous(monkeypatch):
    monkeypatch.setenv("CLIPPER_AUTH", "0")
    from app.api.server import app

    anonymous = TestClient(app)
    assert anonymous.get("/api/nodes").status_code == 200


# --- websockets -----------------------------------------------------------
def test_websocket_rejects_bad_token(client):
    with client.websocket_connect("/ws/jobs/does-not-exist?token=bad") as socket:
        assert socket.receive_json()["status"] == "unauthorized"


# --- pairing url ----------------------------------------------------------
def test_pairing_url_embeds_token_in_fragment(monkeypatch):
    monkeypatch.setenv("CLIPPER_AUTH", "1")
    monkeypatch.setenv("CLIPPER_TOKEN", "abc123")
    from app.api.server import pairing_url

    assert pairing_url("http://127.0.0.1:8765") == "http://127.0.0.1:8765/#token=abc123"


def test_pairing_url_without_auth(monkeypatch):
    monkeypatch.setenv("CLIPPER_AUTH", "0")
    from app.api.server import pairing_url

    assert pairing_url("http://127.0.0.1:8765") == "http://127.0.0.1:8765"
