"""Per-user API tokens (S8). Issued from the CLI only: no signup, no passwords.

  python -m api.tokens issue --owner "Name"   print a new token once; store only its SHA-256
  python -m api.tokens list                   owners, token ids, created/revoked (no secrets)
  python -m api.tokens revoke <token_id>      the token stops working on the next request

Tokens live in runs/_api/tokens.json (gitignored, mode 0600) as
{token_id, owner, sha256, created, revoked}. The server reads the file on every
authenticated request, so issuing and revoking need no restart.

DAVINCI_API_TOKEN (the original single token) keeps working as the admin token,
owner "admin". With neither an admin token nor an active issued token, live
calls stay refused (fail closed).

Every run, extraction, breakdown and approval started with a token records its
owner in runs/_api/owners.jsonl. The owner always comes from the token, never
from the request body.
"""
import argparse
import hashlib
import json
import os
import re
import secrets
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "runs" / "_api"
TOKENS = API_DIR / "tokens.json"
OWNERS = API_DIR / "owners.jsonl"
PREFIX = "dv_"
OWNER_RE = re.compile(r"^[^\x00-\x1f\x7f]{1,80}$")
_lock = threading.Lock()


@dataclass(frozen=True)
class Identity:
    owner: str
    token_id: str
    admin: bool = False


def _sha(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _load() -> list[dict]:
    if not TOKENS.exists():
        return []
    return json.loads(TOKENS.read_text()).get("tokens", [])


def _save(tokens: list[dict]):
    API_DIR.mkdir(parents=True, exist_ok=True)
    tmp = TOKENS.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"tokens": tokens}, f, indent=2)
    os.replace(tmp, TOKENS)


def issue(owner: str) -> tuple[str, dict]:
    owner = owner.strip()
    if not OWNER_RE.match(owner) or owner.lower() == "admin":
        raise ValueError("owner must be 1-80 printable characters and not 'admin'")
    token = PREFIX + secrets.token_urlsafe(32)
    rec = {"token_id": "t_" + secrets.token_hex(4), "owner": owner, "sha256": _sha(token),
           "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "revoked": None}
    with _lock:
        tokens = _load()
        tokens.append(rec)
        _save(tokens)
    return token, rec


def revoke(token_id: str) -> dict:
    with _lock:
        tokens = _load()
        for t in tokens:
            if t["token_id"] == token_id:
                if not t["revoked"]:
                    t["revoked"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
                    _save(tokens)
                return t
    raise KeyError(token_id)


def active() -> list[dict]:
    return [t for t in _load() if not t.get("revoked")]


def configured() -> bool:
    """True when any credential can authenticate: the admin token or an active issued token."""
    return bool(os.environ.get("DAVINCI_API_TOKEN")) or bool(active())


def authenticate(authorization: str | None) -> Identity | None:
    """None when no Authorization header was sent. Raises PermissionError for a
    header that matches no credential (a wrong token is refused, never ignored)."""
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme != "Bearer" or not token:
        raise PermissionError("Authorization must be 'Bearer <token>'")
    admin = os.environ.get("DAVINCI_API_TOKEN")
    if admin and secrets.compare_digest(token.encode(), admin.encode()):
        return Identity(owner="admin", token_id="admin", admin=True)
    digest = _sha(token)
    match = None
    for t in active():  # compare against every hash; no early exit on a match
        if secrets.compare_digest(digest, t["sha256"]):
            match = t
    if match:
        return Identity(owner=match["owner"], token_id=match["token_id"])
    raise PermissionError("unknown or revoked token")


# ---- ownership index ----------------------------------------------------------

def record_owner(kind: str, obj_id: str, ident: "Identity | None", **extra):
    """Append who started/approved what. Anonymous (replay, fake) entries are recorded too."""
    API_DIR.mkdir(parents=True, exist_ok=True)
    row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "kind": kind, "id": obj_id,
           "owner": ident.owner if ident else None, "token_id": ident.token_id if ident else None, **extra}
    with _lock, OWNERS.open("a") as f:
        f.write(json.dumps(row) + "\n")


def owners(kinds: tuple = ("run", "extraction", "breakdown")) -> dict[str, str | None]:
    """id → owner for objects created (not approved) through the API."""
    out: dict[str, str | None] = {}
    if OWNERS.exists():
        for line in OWNERS.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if r["kind"] in kinds:
                    out.setdefault(r["id"], r["owner"])
    return out


# ---- CLI ------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m api.tokens", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("issue", help="issue a token; it is printed once and never stored")
    p.add_argument("--owner", required=True)
    sub.add_parser("list", help="list tokens (ids and owners only)")
    p = sub.add_parser("revoke", help="revoke a token by id")
    p.add_argument("token_id")
    a = ap.parse_args(argv)

    if a.cmd == "issue":
        try:
            token, rec = issue(a.owner)
        except ValueError as e:
            sys.exit(str(e))
        print(f"issued {rec['token_id']} for {rec['owner']}", file=sys.stderr)
        print("token (shown once; only its SHA-256 is stored):", file=sys.stderr)
        print(token)
    elif a.cmd == "list":
        rows = _load()
        if not rows:
            print("no tokens issued")
        for t in rows:
            state = f"revoked {t['revoked']}" if t["revoked"] else "active"
            print(f"{t['token_id']}  {t['created']}  {state:<34}  {t['owner']}")
    elif a.cmd == "revoke":
        try:
            t = revoke(a.token_id)
        except KeyError:
            sys.exit(f"no token {a.token_id}")
        print(f"revoked {t['token_id']} ({t['owner']}) at {t['revoked']}")


if __name__ == "__main__":
    main()
