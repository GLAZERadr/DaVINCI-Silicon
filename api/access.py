"""Request access (S11). The public site stays read-only; anyone can ask for a
token here, and the lead grants it by hand with `python -m api.tokens issue`.
Nothing is created automatically and nothing is emailed.

  POST /access-requests   {name, email, role, verify} → stored in runs/_api/access_requests.jsonl

Fields are validated and size-limited; each IP may send a few requests per hour
and the file stops growing past a global cap. The IP is used only for the
in-memory rate limit and is not stored.
"""
import json
import re
import threading
import time
from collections import deque

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.tokens import API_DIR

REQUESTS = API_DIR / "access_requests.jsonl"
PER_IP = 3              # requests per IP per window
WINDOW_S = 3600
MAX_STORED = 1000       # stop accepting once the file holds this many
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[A-Za-z]{2,24}$")
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")

router = APIRouter()
_hits: dict[str, deque] = {}
_lock = threading.Lock()


class AccessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=3, max_length=254)
    role: str = Field(..., min_length=1, max_length=100)
    verify: str = Field(..., min_length=1, max_length=1000, description="what they would verify")

    @field_validator("name", "email", "role", "verify")
    @classmethod
    def no_control_chars(cls, v: str) -> str:
        if CONTROL.search(v):
            raise ValueError("control characters are not allowed")
        return v

    @field_validator("email")
    @classmethod
    def email_shape(cls, v: str) -> str:
        if not EMAIL.match(v):
            raise ValueError("not an email address")
        return v.lower()


def _rate_limited(ip: str) -> bool:
    now = time.time()
    with _lock:
        q = _hits.setdefault(ip, deque())
        while q and now - q[0] > WINDOW_S:
            q.popleft()
        if len(q) >= PER_IP:
            return True
        q.append(now)
        if len(_hits) > 10_000:  # forget idle IPs so the table stays small
            for k in [k for k, d in _hits.items() if not d or now - d[-1] > WINDOW_S]:
                _hits.pop(k, None)
        return False


@router.post("/access-requests", status_code=201)
def create_access_request(body: AccessRequest, request: Request):
    ip = request.client.host if request.client else "unknown"
    if _rate_limited(ip):
        raise HTTPException(429, "too many requests from this address; try again in an hour")
    with _lock:
        count = len(REQUESTS.read_text().splitlines()) if REQUESTS.exists() else 0
        if count >= MAX_STORED:
            raise HTTPException(503, "the access list is full; try again later")
        API_DIR.mkdir(parents=True, exist_ok=True)
        with REQUESTS.open("a") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **body.model_dump()}) + "\n")
    return {"ok": True, "message": "Request stored. Access is granted by hand; you will be contacted at the email you gave."}
