"""Local engine authentication.

The engine binds to loopback by default, but *any* web page the user visits can
still reach ``127.0.0.1`` from their browser. To stop hostile pages from driving
the engine (downloading video, writing files, reading the cookie store) every
``/api`` and ``/media`` request must carry a **bearer token**.

The token is generated once per install and stored in ``data/auth.json``
(gitignored). It can be overridden for automation with ``CLIPPER_TOKEN`` and the
whole check disabled for tests with ``CLIPPER_AUTH=0``.

Pairing UX: the launcher hands the token to the browser in the URL *fragment*
(``https://app/#token=...``). Fragments are never sent to a server, so the token
never leaves the machine.
"""

from __future__ import annotations

import json
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app import paths

TOKEN_FILE: Path = paths.DATA / "auth.json"

ENV_TOKEN = "CLIPPER_TOKEN"
ENV_AUTH = "CLIPPER_AUTH"

_FALSEY = {"0", "false", "no", "off", ""}


def auth_enabled() -> bool:
    """Whether bearer auth is enforced (default: yes)."""
    raw = os.environ.get(ENV_AUTH)
    if raw is None:
        return True
    return raw.strip().lower() not in _FALSEY


def _read_file() -> dict[str, Any]:
    try:
        data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _stored_token() -> str | None:
    token = _read_file().get("token")
    return token if isinstance(token, str) and token else None


def _write(payload: dict[str, Any]) -> None:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    try:
        os.chmod(TOKEN_FILE, 0o600)
    except OSError:
        pass


def get_token() -> str | None:
    """Return the active token without creating one (env wins over the file)."""
    env = os.environ.get(ENV_TOKEN)
    if env and env.strip():
        return env.strip()
    return _stored_token()


def ensure_token() -> str:
    """Return the active token, generating and persisting one on first use."""
    existing = get_token()
    if existing:
        return existing
    token = secrets.token_urlsafe(32)
    _write({"token": token, "created": datetime.now(UTC).isoformat()})
    return token


def rotate() -> str:
    """Generate a fresh token, invalidating the old one."""
    token = secrets.token_urlsafe(32)
    _write({"token": token, "created": datetime.now(UTC).isoformat()})
    return token


def verify(candidate: str | None) -> bool:
    """Constant-time comparison of a presented token against the active one."""
    if not candidate:
        return False
    expected = get_token()
    if not expected:
        return False
    return secrets.compare_digest(candidate, expected)


def token_from_header(value: str | None) -> str | None:
    """Extract the token from an ``Authorization: Bearer <token>`` header."""
    if not value:
        return None
    parts = value.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip() or None
    return None


def status() -> dict[str, Any]:
    data = _read_file()
    return {
        "auth_required": auth_enabled(),
        "token_set": bool(get_token()),
        "source": "env" if os.environ.get(ENV_TOKEN) else ("file" if _stored_token() else None),
        "created": data.get("created"),
    }
