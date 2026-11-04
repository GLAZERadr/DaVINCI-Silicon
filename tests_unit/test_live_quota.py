"""Live access for email/password accounts on the hosted demo, and the daily cap per account."""
import pytest
from fastapi import HTTPException
from types import SimpleNamespace

from api import auth, server, tokens, users


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    d = tmp_path / "_api"
    monkeypatch.setattr(tokens, "API_DIR", d)
    monkeypatch.setattr(tokens, "TOKENS", d / "tokens.json")
    monkeypatch.setattr(tokens, "OWNERS", d / "owners.jsonl")
    monkeypatch.setattr(users, "USERS", d / "users.json")
    monkeypatch.setattr(users, "API_DIR", d)
    auth._hits.clear()
    yield d
    auth._hits.clear()


def _register(email):
    body = auth.Register(name="Judge", email=email, password="judge-password-1")
    return auth.register(body, SimpleNamespace(client=SimpleNamespace(host="10.0.0.1")))


def test_password_accounts_read_only_by_default(isolated, monkeypatch):
    monkeypatch.delenv("DAVINCI_AUTO_LIVE_PASSWORD", raising=False)
    assert _register("a@example.com")["user"]["live"] is False


def test_password_accounts_live_on_hosted_demo(isolated, monkeypatch):
    monkeypatch.setenv("DAVINCI_AUTO_LIVE_PASSWORD", "1")
    r = _register("b@example.com")
    assert r["user"]["live"] is True
    assert tokens.authenticate(f"Bearer {r['token']}").live is True


def test_daily_cap_counts_only_live_calls_of_that_account(isolated, monkeypatch):
    monkeypatch.setattr(server, "LIVE_PER_DAY", 2)
    me = tokens.Identity(owner="c@example.com", token_id="s_1", user_id="u_1")
    other = tokens.Identity(owner="d@example.com", token_id="s_2", user_id="u_2")
    tokens.record_owner("run", "r0", me, live=False)        # a replay: not counted
    tokens.record_owner("run", "r1", other, live=True)      # someone else: not counted
    tokens.record_owner("run", "r2", me, live=True)
    server._live_quota(me)                                   # 1 of 2 used: allowed
    tokens.record_owner("extraction", "x1", me, live=True)
    with pytest.raises(HTTPException) as e:
        server._live_quota(me)
    assert e.value.status_code == 429


def test_admin_and_cli_tokens_not_capped(isolated, monkeypatch):
    monkeypatch.setattr(server, "LIVE_PER_DAY", 0)
    server._live_quota(tokens.Identity(owner="admin", token_id="admin", admin=True))
    server._live_quota(tokens.Identity(owner="Adrian", token_id="t_1"))
