#!/usr/bin/env python3
"""Keep the two fiverr_fetcher.py copies in sync.

The crawler exists in two standalone distributions:
  - fiverr-niche-fetcher/fiverr_fetcher.py  (canonical source of truth)
  - fiverr-mcp/fiverr_fetcher.py            (MCP distribution copy)

Both folders are shipped as independent zips, so the file must remain
duplicated — but it must never DRIFT. Run this script to sync, or pass
--check to fail (exit 1) when the copies differ (used by CI).

Usage:
  python scripts/sync_fiverr_fetcher.py           # sync (canonical -> mcp)
  python scripts/sync_fiverr_fetcher.py --check   # verify only (CI)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANONICAL = ROOT / "fiverr-niche-fetcher" / "fiverr_fetcher.py"
TARGET = ROOT / "fiverr-mcp" / "fiverr_fetcher.py"


def main() -> int:
    if not CANONICAL.is_file() or not TARGET.is_file():
        print(f"ERROR: missing file: {CANONICAL if not CANONICAL.is_file() else TARGET}")
        return 1

    canonical = CANONICAL.read_bytes()
    target = TARGET.read_bytes()

    if canonical == target:
        print("OK: fiverr_fetcher.py copies are identical")
        return 0

    if "--check" in sys.argv:
        print("FAIL: fiverr-mcp/fiverr_fetcher.py has drifted from the canonical copy.")
        print(f"      canonical: {CANONICAL}")
        print(f"      target:    {TARGET}")
        print("      Run: python scripts/sync_fiverr_fetcher.py  (then re-run tests in BOTH folders)")
        return 1

    TARGET.write_bytes(canonical)
    print(f"SYNCED: {CANONICAL} -> {TARGET}")
    print("        Re-run the Python test suite to verify the sync.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
