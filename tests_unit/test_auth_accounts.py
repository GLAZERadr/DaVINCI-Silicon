"""Unit tests for accounts and sign-in (api/users.py, api/tokens.py, api/auth.py).

The real store under runs/_api is never touched: the `isolated` fixture
repoints every store path under pytest's tmp_path.
"""

import json
import urllib.parse
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api import auth, tokens, users


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    api_dir = tmp_path / "_api"
    monkeypatch.setattr(tokens, "API_DIR", api_dir)
    monkeypatch.setattr(tokens, "TOKENS", api_dir / "tokens.json")
    monkeypatch.setattr(tokens, "OWNERS", api_dir / "owners.jsonl")
    monkeypatch.setattr(users, "USERS", api_dir / "users.json")
    monkeypatch.setattr(users, "API_DIR", api_dir)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("DAVINCI_CORS_ORIGINS", "http://127.0.0.1:4320")
    auth._states.clear()
    auth._hits.clear()
    yield api_dir
    auth._states.clear()
    auth._hits.clear()


def _request(host="127.0.0.1"):
    return SimpleNamespace(client=SimpleNamespace(host=host))


# ---- passwords ---------------------------------------------------------------

def test_password_roundtrip(isolated):
    stored = users.hash_password("correct-horse-123")
    assert users.check_password("correct-horse-123", stored)


def test_wrong_password_rejected(isolated):
    stored = users.hash_password("correct-horse-123")
    assert not users.check_password("wrong-password-!", stored)


# ---- register / login --------------------------------------------------------

def test_register_rejects_duplicate_email(isolated):
    users.register("dup@example.com", "Dup", "0123456789ab")
    with pytest.raises(FileExistsError):
        users.register("dup@example.com", "Dup", "0123456789ab")


def test_register_rejects_short_password(isolated):
    with pytest.raises(ValueError):
        users.register("short@example.com", "Short", "too-short")


def test_register_rejects_bad_email(isolated):
    with pytest.raises(ValueError):
        users.register("not-an-email", "Name", "0123456789ab")


def test_login_unknown_email_returns_none(isolated):
    assert users.login("nobody@example.com", "0123456789ab") is None


def test_login_rate_limit(isolated):
    body = auth.Login(email="ghost@example.com", password="wrong-password")
    for _ in range(auth.LOGIN_TRIES):
        with pytest.raises(HTTPException) as e:
            auth.login(body, _request(host="9.9.9.9"))
        assert e.value.status_code == 401
    with pytest.raises(HTTPException) as e:
        auth.login(body, _request(host="9.9.9.9"))
    assert e.value.status_code == 429


# ---- sessions ----------------------------------------------------------------

def test_session_live_false_until_granted(isolated):
    u = users.register("live@example.com", "Live", "0123456789ab")
    tok = tokens.issue_session(u)
    assert tokens.authenticate(f"Bearer {tok}").live is False
    users.set_live(u["email"], True)
    ident = tokens.authenticate(f"Bearer {tok}")
    assert ident.live is True
    assert ident.user_id == u["user_id"]


def test_revoked_session_refused(isolated):
    u = users.register("rev@example.com", "Rev", "0123456789ab")
    tok = tokens.issue_session(u)
    tid = next(t["token_id"] for t in tokens.active())
    tokens.revoke(tid)
    with pytest.raises(PermissionError):
        tokens.authenticate(f"Bearer {tok}")


def test_expired_session_refused(isolated):
    u = users.register("old@example.com", "Old", "0123456789ab")
    tok = tokens.issue_session(u)
    recs = json.loads(tokens.TOKENS.read_text())
    for t in recs["tokens"]:
        t["expires"] = 1
    tokens.TOKENS.write_text(json.dumps(recs))
    with pytest.raises(PermissionError):
        tokens.authenticate(f"Bearer {tok}")


# ---- provider linking --------------------------------------------------------

def test_from_provider_links_by_email_and_drops_password(isolated):
    u = users.register("owner@example.com", "Owner", "0123456789ab")
    linked = users.from_provider("google", "g-sub-1", "owner@example.com", "Owner")
    assert linked["user_id"] == u["user_id"]
    assert linked["password"] is None
    assert linked["google"] == "g-sub-1"


# ---- avatars -----------------------------------------------------------------

def test_avatar_ok_accepts_provider_hosts(isolated):
    assert users.avatar_ok("https://lh3.googleusercontent.com/a/avatar") is not None
    assert users.avatar_ok("https://avatars.githubusercontent.com/u/123?v=4") is not None


@pytest.mark.parametrize("url", [
    "http://lh3.googleusercontent.com/a/avatar",
    "https://example.com/a.png",
    "https://googleusercontent.com.evil.io/a",
    "https://evilgithubusercontent.com/u/1",
])
def test_avatar_ok_rejects(isolated, url):
    assert users.avatar_ok(url) is None


# ---- OAuth -------------------------------------------------------------------

def test_oauth_start_rejects_foreign_origin(isolated):
    with pytest.raises(HTTPException) as e:
        auth.oauth_start("google", "https://evil.example/board")
    assert e.value.status_code == 400


def _start_state(return_to="http://127.0.0.1:4320/board"):
    resp = auth.oauth_start("google", return_to)
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(resp.headers["location"]).query)
    return q["state"][0]


def test_oauth_callback_state_single_use(isolated, monkeypatch):
    state = _start_state()
    monkeypatch.setattr(auth, "_identity",
                        lambda provider, code, verifier: ("sub-1", "cb@example.com", "CB", None))
    auth.oauth_callback("google", state=state, code="code-1")
    with pytest.raises(HTTPException):
        auth.oauth_callback("google", state=state, code="code-1")


def test_oauth_callback_redirect_stores_avatar(isolated, monkeypatch):
    avatar = "https://lh3.googleusercontent.com/a/x"
    state = _start_state()
    monkeypatch.setattr(auth, "_identity",
                        lambda provider, code, verifier: ("sub-9", "cb2@example.com", "CB", avatar))
    resp = auth.oauth_callback("google", state=state, code="code-9")
    assert resp.status_code == 302
    loc = resp.headers["location"]
    assert loc.startswith("http://127.0.0.1:4320/board#")
    session = urllib.parse.parse_qs(urllib.parse.urlsplit(loc).fragment)["dv_session"][0]
    assert tokens.authenticate(f"Bearer {session}").user_id is not None
    assert users.by_email("cb2@example.com")["avatar"] == avatar
