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
- A wrong, revoked or malformed token is refused (401) for live runs, approvals,
  `?mine=1` and `/me`. Free actions (replay/fake runs, listing) treat it as
  anonymous, so a stale token in a browser tab never blocks a $0 replay.
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

## Sign in and register (2 Nov) — `api/users.py`, `api/auth.py`, `/login/`, `/register/`

Accounts with email + password, Google or GitHub. An account is read-only until the
lead switches on live runs for it; signing up never spends model credit.

```bash
python -m api.users list                 # accounts, sign-in methods, live or read-only
python -m api.users grant <email>        # live model runs + approvals for this account
python -m api.users revoke-live <email>
```

- Passwords: scrypt (n=2^14, r=8, p=1) with a per-account salt, 10-128 characters.
  Wrong email and wrong password give the same 401 and take the same time.
  10 failed sign-ins per IP and per email per 15 min; 5 new accounts per IP per hour.
- Signing in issues a session token (`s_…`, 30 days) in `runs/_api/tokens.json`;
  sign-out revokes it. Its owner is the account email. The board keeps it in
  localStorage (all tabs) until sign-out; a token typed into Connection settings
  still wins for that tab.
- Google / GitHub: OAuth 2 authorization code + PKCE, run by the API (the board is
  static). `state` is single-use and expires after 10 min; `return_to` must be on an
  origin in `DAVINCI_CORS_ORIGINS`; the session comes back in the URL fragment.
  Only a provider-verified email is accepted (GitHub: the verified primary email).
- Linking: a verified Google/GitHub email joins the account with that email. If that
  account only had an (unverified) password, the password is dropped, so someone who
  registered another person's email first loses the way in.
- Setup: set `GOOGLE_CLIENT_ID/SECRET` and/or `GITHUB_CLIENT_ID/SECRET` and
  `DAVINCI_API_PUBLIC_URL` (default `http://127.0.0.1:8000`) in `.env.local`, and
  register `<DAVINCI_API_PUBLIC_URL>/auth/google/callback` (Google Cloud console,
  OAuth client "Web application") and `<…>/auth/github/callback` (GitHub → Settings →
  Developer settings → OAuth Apps). Without them the buttons show as not configured.
- Tested 2 Nov locally: register, duplicate (409), short password (422), login, wrong
  password (401), live run refused until `grant`, fake run allowed, sign-out → 401,
  OAuth redirect URLs + PKCE + state reuse/expiry + foreign `return_to` (400), and the
  callback with the provider call stubbed. Not tested: a real Google/GitHub sign-in
  (no client ids yet). Test accounts were removed afterwards.
