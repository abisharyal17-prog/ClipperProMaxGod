"""Desktop launcher for Clipper (Windows).

Serves the FastAPI app (``app.api.server:app``) with uvicorn on a background
thread, then opens a native ``pywebview`` window pointed at it. When the window
is closed the server is asked to shut down gracefully.

Fallbacks:
  * The built SPA (``web/dist``) is missing -> a clear message tells you to run
    ``scripts/build_web.ps1``.
  * ``app.api.server`` is missing       -> degrade to opening the browser.
  * ``pywebview`` is not installed       -> degrade to opening the browser
    (install with ``uv sync --extra desktop``).

Run:  python -m app.desktop [--browser] [--host H] [--port P]
"""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DIST = ROOT / "web" / "dist"
INDEX = DIST / "index.html"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def _url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def _dist_ready() -> bool:
    return INDEX.is_file()


def _warn_dist() -> None:
    if _dist_ready():
        return
    print(
        "! web/dist was not found.\n"
        "  Build the SPA first:  powershell -ExecutionPolicy Bypass -File scripts/build_web.ps1\n"
        "  (the desktop window will still open, but the UI may not load)",
        file=sys.stderr,
    )


def _load_asgi_app() -> tuple[Any | None, str | None]:
    """Return the ASGI app, or (None, reason) when it is unavailable."""
    try:
        from app.api.server import app  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001 - missing module or import-time failure
        return None, f"{type(exc).__name__}: {exc}"
    return app, None


def _port_open(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _pairing_url(url: str) -> str:
    """Append the engine token as a URL fragment so the UI can pair itself."""
    try:
        from app.api.server import pairing_url

        return pairing_url(url)
    except Exception:  # noqa: BLE001 - pairing is best-effort
        return url


def _wait_ready(host: str, port: int, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_open(host, port):
            return True
        time.sleep(0.1)
    return False


def _start_server(app: Any, host: str, port: int) -> tuple[threading.Thread, dict[str, Any]]:
    """Run uvicorn in a daemon thread; returns the thread and a holder for the server."""
    import uvicorn

    holder: dict[str, Any] = {}

    def _serve() -> None:
        config = uvicorn.Config(app, host=host, port=port, log_level="warning")
        server = uvicorn.Server(config)
        holder["server"] = server
        server.run()

    thread = threading.Thread(target=_serve, name="clipper-uvicorn", daemon=True)
    thread.start()
    return thread, holder


def _shutdown(thread: threading.Thread | None, holder: dict[str, Any]) -> None:
    server = holder.get("server")
    if server is not None:
        try:
            server.should_exit = True
        except Exception:  # noqa: BLE001 - best effort
            pass
    if thread is not None and thread.is_alive():
        thread.join(timeout=5.0)


def _browser_loop(url: str) -> int:
    """Open the browser and block until Ctrl+C (used for --browser / fallbacks)."""
    webbrowser.open(url)
    print(f"Clipper is running at {url}  (press Ctrl+C to stop)")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nShutting down...")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.desktop", description="Clipper desktop launcher")
    parser.add_argument("--browser", action="store_true", help="skip the native window, use the browser")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    url = _url(args.host, args.port)
    _warn_dist()

    app, reason = _load_asgi_app()

    thread: threading.Thread | None = None
    holder: dict[str, Any] = {}
    already_serving = _port_open(args.host, args.port)

    if already_serving:
        print(f"= server already listening on {url}")
    elif app is None:
        print(
            "! app.api.server is unavailable; cannot start the local server.\n"
            f"  reason: {reason}\n"
            "  Falling back to the browser (start the API yourself if nothing loads).",
            file=sys.stderr,
        )
    else:
        thread, holder = _start_server(app, args.host, args.port)
        if not _wait_ready(args.host, args.port):
            print("! server did not become ready in time; continuing anyway", file=sys.stderr)

    try:
        if args.browser or app is None:
            return _browser_loop(_pairing_url(url))

        try:
            import webview  # type: ignore[import-not-found]
        except ImportError:
            print(
                "! pywebview is not installed - install the desktop extra:\n"
                "    uv sync --extra desktop\n"
                "  or: .venv\\Scripts\\python.exe -m pip install pywebview\n"
                "  Falling back to your default browser.",
                file=sys.stderr,
            )
            return _browser_loop(_pairing_url(url))

        webview.create_window("Clipper", _pairing_url(url), width=1440, height=900)
        webview.start()
        return 0
    finally:
        _shutdown(thread, holder)


if __name__ == "__main__":
    raise SystemExit(main())
