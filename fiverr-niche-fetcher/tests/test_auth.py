"""Regression tests for auth (password + HMAC tokens + signed downloads)."""

from __future__ import annotations

import time

import pytest


class TestTokenRoundTrip:
    def test_generate_and_verify(self):
        import auth

        token = auth.generate_token(secret="unit-test-secret")
        assert auth.verify_token(token, secret="unit-test-secret")

    def test_tampered_signature_rejected(self):
        import auth

        token = auth.generate_token(secret="unit-test-secret")
        payload, _random, _sig = token.split(":")
        bad = f"{payload}:{_random}:{'0' * 64}"
        assert bad != token
        assert not auth.verify_token(bad, secret="unit-test-secret")

    def test_expired_token_rejected(self):
        import auth

        token = auth.generate_token(secret="unit-test-secret")
        ts, _random, sig = token.split(":")
        old_ts = int(time.time()) - auth.TOKEN_TTL_SECONDS - 3600
        old_token = f"{old_ts}:{_random}:{sig}"
        assert not auth.verify_token(old_token, secret="unit-test-secret")

    def test_wrong_secret_rejected(self):
        import auth

        token = auth.generate_token(secret="secret-a")
        assert not auth.verify_token(token, secret="secret-b")

    def test_malformed_tokens_rejected(self):
        import auth

        for bad in (None, "", "abc", "a:b", "a:b:c:d", "notanum:xx:yy"):
            assert not auth.verify_token(bad, secret="s")


class TestPasswordComparison:
    def test_case_sensitive(self):
        import auth

        assert auth.password_matches("bilalkhan", "bilalkhan")
        assert not auth.password_matches("bilalkhan", "BILALKHAN")
        assert not auth.password_matches("bilalkhan", "bilal")

    def test_non_string_never_crashes(self):
        import auth

        assert not auth.password_matches("x", None)
        assert not auth.password_matches("x", 42)


class TestSignedDownloads:
    def test_sign_and_verify_roundtrip(self):
        import auth

        url = auth.sign_download_url("job_1-gigs.json", secret="s", now=1_000_000)
        assert url.startswith("/download/job_1-gigs.json?dl=")
        dl = url.split("dl=")[1]
        assert auth.verify_download_signature("job_1-gigs.json", dl, secret="s", now=1_000_000 + 10)

    def test_expired_signature_rejected(self):
        import auth

        url = auth.sign_download_url("j.json", ttl_seconds=60, secret="s", now=1_000_000)
        dl = url.split("dl=")[1]
        assert not auth.verify_download_signature("j.json", dl, secret="s", now=1_000_000 + 61)

    def test_signature_bound_to_filename(self):
        import auth

        url = auth.sign_download_url("j.json", secret="s", now=1_000_000)
        dl = url.split("dl=")[1]
        assert not auth.verify_download_signature("other.csv", dl, secret="s", now=1_000_000 + 5)

    def test_garbage_signature_rejected(self):
        import auth

        for bad in (None, "", "abc", "123", "123.deadbeef", "notanum.sig"):
            assert not auth.verify_download_signature("j.json", bad, secret="s", now=1_000_000)


class TestAppAuthMiddleware:
    """Boot the real FastAPI app and verify the guard end-to-end."""

    @pytest.fixture(scope="class")
    def client(self):
        import os

        import auth
        import app as app_module

        # Fix the credentials for the duration of the test session so the
        # app-under-test uses known values (not the random boot fallback).
        os.environ["APP_PASSWORD"] = "test-password-123"
        os.environ["AUTH_SECRET"] = "unit-test-hmac-secret"
        auth._secret = "unit-test-hmac-secret"
        auth._password = "test-password-123"

        from fastapi.testclient import TestClient

        with TestClient(app_module.app) as c:
            yield c

    def test_unauthenticated_api_401(self, client):
        r = client.get("/api/jobs")
        assert r.status_code == 401
        assert r.json()["authenticated"] is False

    def test_health_is_public(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_login_wrong_password_401(self, client):
        r = client.post("/api/auth/login", json={"password": "wrong"})
        assert r.status_code == 401

    def test_login_correct_password_sets_cookie(self, client):
        r = client.post("/api/auth/login", json={"password": "test-password-123"})
        assert r.status_code == 200
        assert r.cookies.get("auth_token")

    def test_authenticated_api_200_with_cookie(self, client):
        client.post("/api/auth/login", json={"password": "test-password-123"})
        r = client.get("/api/jobs")
        assert r.status_code == 200

    def test_home_redirects_to_login_when_unauthenticated(self, client):
        client.cookies.delete("auth_token")  # ordering-independent: start logged-out
        r = client.get("/", follow_redirects=False)
        assert r.status_code == 302
        assert r.headers["location"].startswith("/login")

    def test_home_served_when_authenticated(self, client):
        client.post("/api/auth/login", json={"password": "test-password-123"})
        r = client.get("/")
        assert r.status_code == 200
        assert "GigCraft" in r.text

    def test_logout_clears_session(self, client):
        client.post("/api/auth/login", json={"password": "test-password-123"})
        client.post("/api/auth/logout")
        r = client.get("/api/jobs")
        assert r.status_code == 401

    def test_download_requires_valid_signature(self, client):
        client.post("/api/auth/login", json={"password": "test-password-123"})
        # No signature at all -> 403 even for an authenticated user.
        r = client.get("/download/nonexistent-job.json")
        assert r.status_code == 403
