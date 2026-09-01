"""Regression tests: fiverr-mcp/app.py must import cleanly (shim fix)."""

from __future__ import annotations

import os
import subprocess
import sys

_MCP_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "fiverr-mcp"))


class TestMcpAppShim:
    def test_import_app_from_mcp_folder(self):
        # Runs in a clean interpreter with cwd=fiverr-mcp, exactly like a user
        # doing `python app.py` from that folder.
        code = (
            "import os, sys; import app; "
            "print(app.app.__class__.__name__); "
            "print(os.path.abspath(sys.modules['gigcraft_web_app'].__file__))"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=_MCP_DIR,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 0, f"import app failed in fiverr-mcp: {proc.stderr}"
        lines = proc.stdout.strip().splitlines()
        assert lines[0] == "FastAPI"
        # The module that actually got imported must be the sibling package's
        # app.py, not a local copy.
        assert lines[1].replace(os.sep, "/").endswith("fiverr-niche-fetcher/app.py")

    def test_mcp_server_still_imports(self):
        proc = subprocess.run(
            [sys.executable, "-c", "import mcp_server; print(len(mcp_server.TOOLS))"],
            cwd=_MCP_DIR,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 0, f"mcp_server import failed: {proc.stderr}"
        assert proc.stdout.strip() == "3"


class TestFetcherCopySync:
    """The duplicated crawler must never drift between the two distributions."""

    def test_fiverr_fetcher_copies_identical(self):
        import pathlib

        here = pathlib.Path(__file__).resolve().parent
        canonical = here.parent / "fiverr_fetcher.py"
        target = here.parent.parent / "fiverr-mcp" / "fiverr_fetcher.py"
        assert canonical.is_file() and target.is_file()
        assert canonical.read_bytes() == target.read_bytes(), (
            "fiverr-mcp/fiverr_fetcher.py has drifted from the canonical copy. "
            "Run: python scripts/sync_fiverr_fetcher.py"
        )
