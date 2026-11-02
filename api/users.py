"""Accounts for signing in (email + password, Google, GitHub). Signing in gives a
session token (api/tokens.py); it does not give live model access. The lead grants
that per account, by hand:

  python -m api.users list                 accounts: id, email, sign-in methods, live access
  python -m api.users grant <email>        allow live model runs and approvals
  python -m api.users revoke-live <email>  take live access away (next request)

Accounts live in runs/_api/users.json (gitignored, mode 0600). Passwords are stored
as scrypt hashes with a per-account salt, never in plain text.

Linking: a Google or GitHub sign-in with a verified email joins the account that
has that email. Password accounts are never email-verified, so when a provider
proves the email first, the unverified password is dropped: whoever typed that
email before cannot keep a way in to the owner's account.
"""
import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import threading
import time

from api.tokens import API_DIR

USERS = API_DIR / "users.json"
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[A-Za-z]{2,24}$")
NAME = re.compile(r"^[^\x00-\x1f\x7f]{1,80}$")
PROVIDERS = ("google", "github")
SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1}
_lock = threading.Lock()


def _load() -> list[dict]:
    if not USERS.exists():
        return []
    return json.loads(USERS.read_text()).get("users", [])


def _save(users: list[dict]):
    API_DIR.mkdir(parents=True, exist_ok=True)
    tmp = USERS.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"users": users}, f, indent=2)
    os.replace(tmp, USERS)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **SCRYPT)
    return f"scrypt${SCRYPT['n']}${SCRYPT['r']}${SCRYPT['p']}${salt.hex()}${h.hex()}"


def check_password(password: str, stored: str | None) -> bool:
    if not stored:
        # Same work as a real check, so a missing account takes as long as a wrong password.
        hashlib.scrypt(password.encode(), salt=b"\0" * 16, dklen=32, **SCRYPT)
        return False
    _, n, r, p, salt, h = stored.split("$")
    got = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), dklen=32, n=int(n), r=int(r), p=int(p))
    return hmac.compare_digest(got.hex(), h)


def public(u: dict) -> dict:
    """What the account owner may see about their own account."""
    return {"user_id": u["user_id"], "email": u["email"], "name": u["name"], "live": bool(u.get("live")),
            "methods": (["password"] if u.get("password") else []) + [p for p in PROVIDERS if u.get(p)]}


def get(user_id: str) -> dict | None:
    return next((u for u in _load() if u["user_id"] == user_id), None)


def by_email(email: str) -> dict | None:
    email = email.strip().lower()
    return next((u for u in _load() if u["email"] == email), None)


def any_live() -> bool:
    return any(u.get("live") for u in _load())


def _new(email: str, name: str) -> dict:
    return {"user_id": "u_" + secrets.token_hex(6), "email": email, "name": name, "password": None,
            "google": None, "github": None, "email_verified": False, "live": False,
            "created": time.strftime("%Y-%m-%dT%H:%M:%S%z")}


def register(email: str, name: str, password: str) -> dict:
    email, name = email.strip().lower(), name.strip()
    if not EMAIL.match(email):
        raise ValueError("not an email address")
    if not NAME.match(name):
        raise ValueError("name must be 1-80 printable characters")
    if not 10 <= len(password) <= 128:
        raise ValueError("password must be 10-128 characters")
    pw = hash_password(password)
    with _lock:
        users = _load()
        if any(u["email"] == email for u in users):
            raise FileExistsError("an account with this email already exists; sign in instead")
        u = _new(email, name)
        u["password"] = pw
        users.append(u)
        _save(users)
    return u


def login(email: str, password: str) -> dict | None:
    u = by_email(email)
    return u if check_password(password, u.get("password") if u else None) else None


def from_provider(provider: str, subject: str, email: str, name: str) -> dict:
    """Account for a Google/GitHub identity whose email the provider verified:
    the one already linked to this identity, else the one with this email, else a new one."""
    assert provider in PROVIDERS
    email = email.strip().lower()
    with _lock:
        users = _load()
        u = next((x for x in users if x.get(provider) == subject), None)
        if u is None:
            u = next((x for x in users if x["email"] == email), None)
            if u is None:
                u = _new(email, (name or email.split("@")[0]).strip()[:80] or email)
                users.append(u)
            elif not u.get("email_verified"):
                u["password"] = None  # unverified password on someone else's email: drop it
            u[provider] = subject
        u["email_verified"] = True
        _save(users)
    return u


def set_live(email: str, live: bool) -> dict:
    with _lock:
        users = _load()
        u = next((x for x in users if x["email"] == email.strip().lower()), None)
        if u is None:
            raise KeyError(email)
        u["live"] = live
        _save(users)
    return u


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m api.users", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list accounts (no secrets)")
    for c in ("grant", "revoke-live"):
        sub.add_parser(c).add_argument("email")
    a = ap.parse_args(argv)
    if a.cmd == "list":
        rows = _load()
        if not rows:
            print("no accounts")
        for u in rows:
            p = public(u)
            print(f"{u['user_id']}  {u['created']}  {'live' if p['live'] else 'read-only':<9}  "
                  f"{','.join(p['methods']) or '-':<22}  {u['email']}")
    else:
        try:
            u = set_live(a.email, a.cmd == "grant")
        except KeyError:
            sys.exit(f"no account {a.email}")
        print(f"{u['email']}: live access {'granted' if u['live'] else 'removed'}")


if __name__ == "__main__":
    main()
