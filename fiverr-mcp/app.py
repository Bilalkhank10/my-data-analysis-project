"""Compatibility shim — the GigCraft web app lives in ``fiverr-niche-fetcher``.

This folder is the standalone MCP distribution (``mcp_server.py`` +
``fiverr_fetcher.py``). The full FastAPI web app is the ``fiverr-niche-fetcher``
package; previously a second full copy of ``app.py`` was committed here that
could never import its seven dependency modules (ai_manager, job_manager,
storage, ...) from this folder, breaking ``import app``.

The shim below loads the real ``app.py`` from the sibling package when the
repository layout is available (both folders side by side), and raises a
clear error otherwise so users know where the web app actually lives.
"""

from __future__ import annotations

import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SIBLING = os.path.normpath(os.path.join(_HERE, os.pardir, "fiverr-niche-fetcher"))

if os.path.isdir(_SIBLING) and os.path.exists(os.path.join(_SIBLING, "app.py")):
    _SIBLING_APP = os.path.join(_SIBLING, "app.py")
    # The sibling package's imports (ai_manager, job_manager, ...) are
    # top-level, so make its directory importable first.
    if _SIBLING not in sys.path:
        sys.path.insert(0, _SIBLING)
    # Load by explicit path under a unique module name. A plain
    # ``from app import app`` would be a circular import (this file is
    # itself the ``app`` module of the fiverr-mcp directory).
    _spec = importlib.util.spec_from_file_location("gigcraft_web_app", _SIBLING_APP)
    if _spec is None or _spec.loader is None:  # pragma: no cover
        raise SystemExit("Failed to load fiverr-niche-fetcher/app.py")
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_spec.name] = _module
    _spec.loader.exec_module(_module)

    app = _module.app  # noqa: F841  (re-exported FastAPI instance)
    __all__ = ["app"]
else:  # pragma: no cover - standalone MCP distribution layout
    raise SystemExit(
        "fiverr-mcp/app.py is a compatibility shim: the GigCraft web app is "
        "shipped in the 'fiverr-niche-fetcher' package (look for "
        "fiverr-niche-fetcher/app.py next to this folder). "
        "The MCP server itself is 'mcp_server.py' in this folder."
    )
