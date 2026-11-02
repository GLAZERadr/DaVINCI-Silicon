# S8 per-user tokens · S11 request access (2 Nov)

The public link stays read-only: Evidence, Run Console and replays ($0) need no
token. Live model runs, live extractions/breakdowns and approvals need a token.
There is no signup, no password, no OAuth and no email sending.

## Tokens (S8) — `api/tokens.py`

```bash
python -m api.tokens issue --owner "Name"   # prints the token once (stdout); stores only its SHA-256
python -m api.tokens list                   # token ids, owners, created/revoked; no secrets
python -m api.tokens revoke t_1a2b3c4d      # refused from the next request on, no restart
```

- Store: `runs/_api/tokens.json` (gitignored with `runs/`, written 0600).
- `DAVINCI_API_TOKEN` keeps working as the admin token (owner `admin`). With no
  admin token and no active issued token, live calls are refused (403, fail closed).
- A request with a wrong, revoked or malformed token is refused (401) on every
  endpoint, also for replay/fake runs: a bad token is never silently ignored.
- Owner comes from the token only. `POST /runs` rejects unknown fields, so a body
  `owner` is a 422. Owners are recorded in `runs/_api/owners.jsonl` (kind, id,
  owner, token id; approvals also keep the typed `approved_by`) and in
  `runs/_api/jobs.jsonl`.
- Only the owner of an extraction or breakdown, or the admin token, can approve it.
- `GET /runs?mine=1` lists the caller's runs; with a token every row carries
  `mine`. Owner names are never listed to anyone. `GET /me` says whose token it is.
- UI: Connection settings show whose token is set (or "✕ token not accepted");
  the Run Console index has a "My runs only" filter when a token is set.

## Request access (S11) — `api/access.py`, `/access/`

- "Request access" in the header opens `/access/`: name, email, role, what they
  would verify, and "used only to contact you about DaVINCI access".
- `POST /access-requests` appends `{ts, name, email, role, verify}` to
  `runs/_api/access_requests.jsonl`. Unknown fields rejected; lengths capped
  (100/254/100/1000); control characters and malformed emails rejected; 3 per IP
  per hour (in memory; the IP is not stored); the file stops at 1000 requests.
- Access is granted by hand: read the file, then `python -m api.tokens issue`.
  Send the token over a private channel.
- With no reachable API the page says so and disables the submit button.

## Verified 2 Nov (test API on :8011, fake runs, no model call)

- No tokens configured → live `POST /runs` 403. Tokens configured → live with no
  token, a wrong token or a non-Bearer header → 401; `repair_provider: baseten`
  alone also needs a token. Live extraction without a token → 401.
- Two issued tokens started two fake runs; `?mine=1` returned only each owner's
  run; the public `/runs` contains no owner field.
- B approving A's extraction or breakdown → 403; A → 200; admin approving an
  anonymous extraction → 200. Revoked tokens → 401 at once.
- Access form submitted from the built site → stored; bad email, oversize field,
  extra field → 422; 4th request from one IP in an hour → 429.

## Risks and limits

- Bearer tokens over plain HTTP are readable on the network: host the API behind HTTPS.
- No per-user spend cap: any issued token can spend up to the global budget stop
  (`DAVINCI_BUDGET_USD`). Issue tokens sparingly and revoke after the demo.
- The rate limit is per process and per client IP; behind a proxy every client
  may share one IP. Restarting the API resets it.
- The token sits in the browser's sessionStorage for the tab: an XSS on the board
  would expose it.
