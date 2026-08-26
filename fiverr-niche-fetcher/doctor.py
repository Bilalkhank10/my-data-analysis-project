"""Local installation diagnostics. Never prints secret values."""

from __future__ import annotations

import argparse
import importlib
import os
import platform
import socket
import sqlite3
import sys
import tempfile
import urllib.request
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # Allows doctor.py to report the missing package cleanly.
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parent
if load_dotenv is not None:
    load_dotenv(BASE_DIR / ".env", override=False)


def status(ok: bool, name: str, detail: str) -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}: {detail}")


def warning(name: str, detail: str) -> None:
    print(f"[WARN] {name}: {detail}")


def check_online(url: str, name: str) -> bool:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=15) as response:
            ok = 200 <= response.status < 400
            status(ok, name, f"HTTP {response.status}")
            return ok
    except Exception as exc:
        status(False, name, type(exc).__name__)
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--online", action="store_true", help="Also test public network endpoints"
    )
    args = parser.parse_args()
    failures = 0

    print("Fiverr Gig Growth System — Local Doctor")
    print(f"OS: {platform.platform()}")
    print(f"Python: {sys.version.split()[0]}")
    print()

    version_ok = sys.version_info >= (3, 11)
    status(version_ok, "Python version", "3.11+ required")
    failures += int(not version_ok)

    modules = ["fastapi", "uvicorn", "httpx", "bs4", "pydantic", "dotenv"]
    for module in modules:
        try:
            importlib.import_module(module)
            status(True, f"Module {module}", "installed")
        except Exception as exc:
            status(False, f"Module {module}", type(exc).__name__)
            failures += 1

    data_dir = BASE_DIR / "data"
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        probe = data_dir / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        status(True, "Workspace write access", str(data_dir))
    except Exception as exc:
        status(False, "Workspace write access", type(exc).__name__)
        failures += 1

    try:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "doctor.db"
            connection = sqlite3.connect(path)
            connection.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
            connection.execute("INSERT INTO test(value) VALUES ('ok')")
            connection.commit()
            value = connection.execute("SELECT value FROM test").fetchone()[0]
            connection.close()
            status(value == "ok", "SQLite", sqlite3.sqlite_version)
            failures += int(value != "ok")
    except Exception as exc:
        status(False, "SQLite", type(exc).__name__)
        failures += 1

    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if key:
        status(key.startswith("sk-or-"), "OpenRouter key format", "configured (value hidden)")
        if not key.startswith("sk-or-"):
            failures += 1
    else:
        warning(
            "OpenRouter key",
            "not configured; Phases 1–2 and Phase 3/4 dry runs still work",
        )

    try:
        port = int(os.getenv("PORT", "8000"))
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", port))
        status(True, "Local port", f"{port} is available")
    except OSError:
        warning("Local port", f"{os.getenv('PORT', '8000')} is already in use")
    except ValueError:
        status(False, "Local port", "PORT is not an integer")
        failures += 1

    if args.online:
        if not check_online("https://r.jina.ai/http://example.com", "Jina Reader"):
            failures += 1
        if not check_online("https://openrouter.ai/api/v1/models", "OpenRouter models"):
            failures += 1
    else:
        warning("Online checks", "skipped; run `python doctor.py --online` to enable")

    print()
    if failures:
        print(f"Doctor found {failures} blocking issue(s).")
        return 1
    print("Local environment looks ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
