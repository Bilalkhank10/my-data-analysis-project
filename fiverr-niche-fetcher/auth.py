"""Password + HMAC token authentication for the GigCraft web app.

Mirrors the TypeScript server (server.ts) so both implementations behave
identically:

- ``APP_PASSWORD`` selects the login password. NO hardcoded fallback: when it
  is unset a random temporary password is generated for the process lifetime
  and printed to the log (never silently wide-open with a known default).
- ``AUTH_SECRET`` signs session tokens (HMAC-SHA256). When unset a random
  per-boot secret is used, which invalidates tokens on restart.
- Tokens are valid for 30 days and compared in constant time.
- Passwords are compared case-sensitively in constant time.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Optional

AUTH_COOKIE = "auth_token"
TOKEN_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days

_secret: Optional[str] = None
_password: Optional[str] = None


def _env(name: str) -> str:
    import os

    return os.getenv(name, "").strip()


def get_auth_secret() -> str:
    """Return the HMAC signing secret (random per boot when unset)."""
    global _secret
    if _secret is None:
        _secret = _env("AUTH_SECRET") or secrets.token_hex(32)
    return _secret


def get_app_password() -> str:
    """Return the login password (random temporary one when unset)."""
    global _password
    if _password is None:
        password = _env("APP_PASSWORD")
        if not password:
            password = secrets.token_urlsafe(12)
            print(
                "[security] APP_PASSWORD is not set. A temporary password "
                "was generated for this session:\n"
                f"           {password}\n"
                "           Set APP_PASSWORD in your environment to use a "
                "stable password.",
                flush=True,
            )
        _password = password
    return _password


def password_matches(app_password: str, candidate: str) -> bool:
    """Case-sensitive, constant-time password comparison."""
    if not isinstance(candidate, str):
        return False
    a = candidate.encode("utf-8", "ignore")
    b = app_password.encode("utf-8", "ignore")
    # Compare against a same-length buffer when lengths differ so timing does
    # not leak the password length.
    ref = b if len(a) == len(b) else secrets.token_bytes(len(a))
    return len(a) == len(b) and hmac.compare_digest(a, ref)


def generate_token(secret: Optional[str] = None) -> str:
    secret = secret or get_auth_secret()
    timestamp = int(time.time())
    random_part = secrets.token_hex(16)
    payload = f"{timestamp}:{random_part}"
    signature = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"


def verify_token(token: Optional[str], secret: Optional[str] = None, now: Optional[int] = None) -> bool:
    """Verify a session token (HMAC + 30-day expiry)."""
    if not token or not isinstance(token, str):
        return False
    secret = secret or get_auth_secret()
    now = now if now is not None else int(time.time())
    parts = token.split(":")
    if len(parts) != 3:
        return False
    ts_str, _random, signature = parts
    try:
        timestamp = int(ts_str)
    except ValueError:
        return False
    if now - timestamp > TOKEN_TTL_SECONDS:
        return False
    payload = f"{ts_str}:{_random}"
    expected = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature.encode("utf-8"), expected.encode("utf-8"))


def cookie_flags(is_https: bool, max_age_seconds: int) -> str:
    """Cookie attribute string: Secure only when the request is HTTPS."""
    secure = "; Secure" if is_https else ""
    return f"Path=/; HttpOnly; SameSite=Lax{secure}; Max-Age={max_age_seconds}"


def extract_token(cookie_token: Optional[str], authorization: Optional[str], x_auth_token: Optional[str]) -> Optional[str]:
    """Pick the first usable token candidate (cookie, bearer, custom header).

    NOTE: intentionally no query-string token — session tokens in URLs leak
    via logs and referrers. Downloads use short-lived signed URLs instead.
    """
    if cookie_token:
        return cookie_token
    if authorization and authorization.startswith("Bearer "):
        bearer = authorization[len("Bearer "):].strip()
        if bearer:
            return bearer
    if x_auth_token:
        return x_auth_token
    return None


# ---------------------------------------------------------------------------
# Short-lived signed download URLs (replace session tokens in query strings)
# ---------------------------------------------------------------------------

DOWNLOAD_TTL_SECONDS = 60 * 60  # 1 hour


def _download_signature(filename: str, expiry: int, secret: str) -> str:
    message = f"{filename}:{expiry}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def sign_download_url(filename: str, ttl_seconds: int = DOWNLOAD_TTL_SECONDS, secret: Optional[str] = None, now: Optional[int] = None) -> str:
    """Return a signed, time-limited download URL for ``filename``."""
    secret = secret or get_auth_secret()
    now = now if now is not None else int(time.time())
    expiry = now + max(30, ttl_seconds)
    return f"/download/{filename}?dl={expiry}.{_download_signature(filename, expiry, secret)}"


def verify_download_signature(filename: str, dl_param: Optional[str], secret: Optional[str] = None, now: Optional[int] = None) -> bool:
    """Verify a ``?dl=<expiry>.<hmac>`` download signature."""
    if not dl_param or not isinstance(dl_param, str) or "." not in dl_param:
        return False
    secret = secret or get_auth_secret()
    now = now if now is not None else int(time.time())
    expiry_str, signature = dl_param.split(".", 1)
    try:
        expiry = int(expiry_str)
    except ValueError:
        return False
    if expiry < now:
        return False
    expected = _download_signature(filename, expiry, secret)
    return hmac.compare_digest(signature.encode("utf-8"), expected.encode("utf-8"))
