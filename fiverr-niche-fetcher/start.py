"""Cross-platform local launcher with browser opening and port fallback."""

from __future__ import annotations

import os
import socket
import threading
import webbrowser
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=False)


def enabled(name: str, default: bool = True) -> bool:
    fallback = "true" if default else "false"
    return os.getenv(name, fallback).strip().lower() not in {"0", "false", "no", "off"}


def port_is_available(host: str, port: int) -> bool:
    bind_host = "127.0.0.1" if host in {"0.0.0.0", "localhost"} else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((bind_host, port))
            return True
        except OSError:
            return False


def choose_port(host: str, preferred: int) -> int | None:
    if port_is_available(host, preferred):
        return preferred
    if not enabled("AUTO_FIND_PORT", True):
        return None
    for candidate in range(preferred + 1, min(preferred + 21, 65536)):
        if port_is_available(host, candidate):
            print(f"Port {preferred} is busy; using {candidate} instead.")
            return candidate
    return None


def main() -> int:
    host = os.getenv("HOST", "127.0.0.1").strip() or "127.0.0.1"
    try:
        preferred_port = int(os.getenv("PORT", "8000"))
    except ValueError:
        print("ERROR: PORT must be an integer.")
        return 1
    if not 1 <= preferred_port <= 65535:
        print("ERROR: PORT must be between 1 and 65535.")
        return 1

    port = choose_port(host, preferred_port)
    if port is None:
        print(f"ERROR: Port {preferred_port} is already in use and no fallback was found.")
        print("Close the other program or set a different PORT in .env.")
        return 1

    import uvicorn

    browser_host = "127.0.0.1" if host in {"0.0.0.0", "localhost"} else host
    url = f"http://{browser_host}:{port}"
    print(f"Starting Fiverr Gig Growth System at {url}")
    print("Keep this terminal open. Press Ctrl+C to stop.")

    if enabled("AUTO_OPEN_BROWSER", True):
        timer = threading.Timer(1.4, lambda: webbrowser.open(url))
        timer.daemon = True
        timer.start()

    uvicorn.run("app:app", host=host, port=port, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
