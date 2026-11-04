"""Sign in and register: email + password, Google, GitHub (OAuth 2 authorization
code flow with PKCE, run by this API, so the static board needs no server).

  GET  /auth/providers                  which sign-in methods this server has configured
  POST /auth/register {name, email, password}  → {token, user}
  POST /auth/login    {email, password}        → {token, user}
  POST /auth/logout                             revokes the session token sent
  GET  /auth/account                          your account, sessions and what you own
  POST /auth/account  {name}                  rename
  POST /auth/password {new, current?}         change (or add) a password
  POST /auth/sessions/{token_id}/revoke       sign one of your sessions out
  GET  /auth/{google|github}/start?return_to=<board page>
  GET  /auth/{google|github}/callback           → redirect to return_to#dv_session=<token>

A session token says who you are. Live model runs and approvals additionally need
live access, which the lead grants per account (`python -m api.users grant`).

Google and GitHub are on only when their client id + secret are set
(GOOGLE_CLIENT_ID/SECRET, GITHUB_CLIENT_ID/SECRET). Register the callback
<DAVINCI_API_PUBLIC_URL>/auth/<provider>/callback with each provider.
return_to must be on an origin in DAVINCI_CORS_ORIGINS. The token travels back in
the URL fragment, which browsers never send to a server.
"""
import base64
import hashlib
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

from api import tokens as tk
from api import users

router = APIRouter()

OAUTH = {
    "google": {
        "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "scope": "openid email profile",
    },
    "github": {
        "authorize": "https://github.com/login/oauth/authorize",
        "token": "https://github.com/login/oauth/access_token",
        "scope": "read:user user:email",
    },
}
STATE_TTL = 600
LOGIN_TRIES = 10          # failed password logins per IP and per email ...
LOGIN_WINDOW = 900        # ... per 15 minutes
REGISTER_PER_IP = 5       # new accounts per IP per hour

_states: dict[str, dict] = {}
_hits: dict[str, deque] = {}
_lock = threading.Lock()


def _creds(provider: str) -> tuple[str, str] | None:
    cid = os.environ.get(f"{provider.upper()}_CLIENT_ID", "")
    sec = os.environ.get(f"{provider.upper()}_CLIENT_SECRET", "")
    return (cid, sec) if cid and sec else None


def _api_url() -> str:
    return os.environ.get("DAVINCI_API_PUBLIC_URL", "http://127.0.0.1:8000").rstrip("/")


def _origins() -> set[str]:
    return {o.rstrip("/") for o in os.environ.get("DAVINCI_CORS_ORIGINS", "").split(",") if o}


def _limited(key: str, limit: int, window: int, count: bool = True) -> bool:
    now = time.time()
    with _lock:
        q = _hits.setdefault(key, deque())
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return True
        if count:
            q.append(now)
        return False


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


class Register(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(..., min_length=1, max_length=80)
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=10, max_length=128)


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=128)


@router.get("/auth/providers")
def providers():
    return {"password": True, **{p: _creds(p) is not None for p in OAUTH},
            # Shown on the register form: whether a new email account can start live runs right away.
            "password_live": os.environ.get("DAVINCI_AUTO_LIVE_PASSWORD") == "1",
            "live_per_day": int(os.environ.get("DAVINCI_LIVE_PER_DAY", "5"))}


@router.post("/auth/register", status_code=201)
def register(body: Register, request: Request):
    if _limited(f"reg:{_ip(request)}", REGISTER_PER_IP, 3600):
        raise HTTPException(429, "too many new accounts from this address; try again in an hour")
    try:
        # DAVINCI_AUTO_LIVE_PASSWORD=1 (hosted demo): email/password accounts start with live
        # runs on, so judges can try them; the daily per-account cap in api/server.py still applies.
        u = users.register(body.email, body.name, body.password,
                           live=os.environ.get("DAVINCI_AUTO_LIVE_PASSWORD") == "1")
    except FileExistsError as e:
        raise HTTPException(409, str(e)) from None
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    return {"token": tk.issue_session(u), "user": users.public(u)}


@router.post("/auth/login")
def login(body: Login, request: Request):
    keys = (f"login:{_ip(request)}", f"login:{body.email.strip().lower()}")
    if any(_limited(k, LOGIN_TRIES, LOGIN_WINDOW, count=False) for k in keys):
        raise HTTPException(429, "too many failed sign-ins; try again in 15 minutes")
    u = users.login(body.email, body.password)
    if u is None:
        for k in keys:
            _limited(k, LOGIN_TRIES, LOGIN_WINDOW)
        raise HTTPException(401, "wrong email or password")
    return {"token": tk.issue_session(u), "user": users.public(u)}


@router.post("/auth/logout")
def logout(authorization: str | None = Header(None)):
    try:
        ident = tk.authenticate(authorization)
    except PermissionError:
        return {"ok": True}
    if ident and ident.token_id.startswith("s_"):
        tk.revoke(ident.token_id)
    return {"ok": True}


# ---- account (profile page) ----------------------------------------------------------

def _account_caller(authorization: str | None) -> tuple["tk.Identity", dict]:
    try:
        ident = tk.authenticate(authorization)
    except PermissionError as e:
        raise HTTPException(401, str(e)) from None
    if ident is None or ident.user_id is None:
        raise HTTPException(401, "sign in to see your account")
    u = users.get(ident.user_id)
    if u is None:
        raise HTTPException(401, "unknown account")
    return ident, u


class Rename(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(..., min_length=1, max_length=80)


class Password(BaseModel):
    model_config = ConfigDict(extra="forbid")
    new: str = Field(..., min_length=10, max_length=128)
    current: str | None = Field(None, max_length=128)


@router.get("/auth/account")
def account(authorization: str | None = Header(None)):
    ident, u = _account_caller(authorization)
    now = time.time()
    sessions = [{"token_id": t["token_id"], "created": t["created"], "expires": t["expires"],
                 "current": t["token_id"] == ident.token_id}
                for t in tk.active() if t.get("user_id") == u["user_id"] and t.get("expires", 0) > now]
    return {**users.public(u), "created": u["created"], "email_verified": bool(u.get("email_verified")),
            "sessions": sorted(sessions, key=lambda s: s["created"], reverse=True),
            "owned": {k: sum(1 for o in tk.owners((k,)).values() if o == u["email"])
                      for k in ("run", "extraction", "breakdown")}}


@router.post("/auth/account")
def rename(body: Rename, authorization: str | None = Header(None)):
    _, u = _account_caller(authorization)
    try:
        return users.public(users.set_name(u["user_id"], body.name))
    except ValueError as e:
        raise HTTPException(422, str(e)) from None


@router.post("/auth/password")
def password(body: Password, request: Request, authorization: str | None = Header(None)):
    _, u = _account_caller(authorization)
    key = f"pw:{u['user_id']}"
    if _limited(key, LOGIN_TRIES, LOGIN_WINDOW, count=False):
        raise HTTPException(429, "too many attempts; try again in 15 minutes")
    try:
        return users.public(users.set_password(u["user_id"], body.new, body.current))
    except PermissionError as e:
        _limited(key, LOGIN_TRIES, LOGIN_WINDOW)
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(422, str(e)) from None


@router.post("/auth/sessions/{token_id}/revoke")
def revoke_session(token_id: str, authorization: str | None = Header(None)):
    _, u = _account_caller(authorization)
    t = next((t for t in tk.active() if t["token_id"] == token_id and t.get("user_id") == u["user_id"]), None)
    if t is None:
        raise HTTPException(404, "no such session on your account")
    tk.revoke(token_id)
    return {"ok": True}


# ---- Google / GitHub ----------------------------------------------------------------

def _return_to(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    if f"{p.scheme}://{p.netloc}" not in _origins():
        raise HTTPException(400, "return_to is not on an allowed origin")
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path or "/", "", ""))


def _back(return_to: str, **frag) -> RedirectResponse:
    return RedirectResponse(f"{return_to}#{urllib.parse.urlencode(frag)}", status_code=302)


@router.get("/auth/{provider}/start")
def oauth_start(provider: str, return_to: str):
    if provider not in OAUTH:
        raise HTTPException(404, "unknown provider")
    creds = _creds(provider)
    if creds is None:
        raise HTTPException(503, f"{provider} sign-in is not configured on this server")
    back = _return_to(return_to)
    state, verifier = secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    now = time.time()
    with _lock:
        for k in [k for k, v in _states.items() if v["exp"] < now]:
            _states.pop(k, None)
        _states[state] = {"provider": provider, "verifier": verifier, "return_to": back, "exp": now + STATE_TTL}
    q = {"client_id": creds[0], "redirect_uri": f"{_api_url()}/auth/{provider}/callback",
         "response_type": "code", "scope": OAUTH[provider]["scope"], "state": state,
         "code_challenge": challenge, "code_challenge_method": "S256"}
    if provider == "google":
        q["prompt"] = "select_account"
    return RedirectResponse(f"{OAUTH[provider]['authorize']}?{urllib.parse.urlencode(q)}", status_code=302)


def _http(url: str, data: dict | None = None, token: str | None = None) -> dict | list:
    headers = {"Accept": "application/json", "User-Agent": "davinci-silicon"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers), timeout=15) as r:
        return json.loads(r.read())


def _identity(provider: str, code: str, verifier: str) -> tuple[str, str, str, str | None]:
    """(subject, verified email, name) from the provider; ValueError if the email is not verified."""
    cid, sec = _creds(provider)
    tok = _http(OAUTH[provider]["token"], {
        "client_id": cid, "client_secret": sec, "code": code, "code_verifier": verifier,
        "redirect_uri": f"{_api_url()}/auth/{provider}/callback", "grant_type": "authorization_code"})
    access = tok.get("access_token")
    if not access:
        raise ValueError(tok.get("error_description") or tok.get("error") or "no access token")
    if provider == "google":
        info = _http("https://openidconnect.googleapis.com/v1/userinfo", token=access)
        if not info.get("email") or not info.get("email_verified"):
            raise ValueError("Google did not return a verified email")
        return str(info["sub"]), info["email"], info.get("name") or "", info.get("picture")
    user = _http("https://api.github.com/user", token=access)
    emails = _http("https://api.github.com/user/emails", token=access)
    primary = next((e["email"] for e in emails if e.get("primary") and e.get("verified")), None)
    if not primary:
        raise ValueError("GitHub has no verified primary email for this account")
    return str(user["id"]), primary, user.get("name") or user.get("login") or "", user.get("avatar_url")


@router.get("/auth/{provider}/callback")
def oauth_callback(provider: str, state: str = "", code: str = "", error: str = ""):
    with _lock:
        st = _states.pop(state, None)
    if st is None or st["provider"] != provider or st["exp"] < time.time():
        raise HTTPException(400, "sign-in expired or was not started here; start again")
    if error or not code:
        return _back(st["return_to"], auth_error=error or "cancelled")
    try:
        subject, email, name, avatar = _identity(provider, code, st["verifier"])
    except (ValueError, KeyError, urllib.error.URLError, TimeoutError) as e:
        return _back(st["return_to"], auth_error=str(e)[:200])
    u = users.from_provider(provider, subject, email, name, avatar)
    return _back(st["return_to"], dv_session=tk.issue_session(u))
