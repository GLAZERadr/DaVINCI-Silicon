Task: add unit tests for the account and sign-in code of this repository (DaVINCI Silicon).

Code under test (read these first, do NOT modify them):
- api/users.py   accounts: hash_password/check_password (scrypt), register, login, from_provider (Google/GitHub linking), avatar_ok, set_name, set_password, set_live
- api/tokens.py  tokens and sign-in sessions: issue, issue_session, revoke, active, authenticate (Identity with live/user_id/name/avatar)
- api/auth.py    FastAPI router: _return_to, oauth_start, oauth_callback (state is single-use), login rate limit

Write ONE new file: tests_unit/test_auth_accounts.py (pytest). Also add a Makefile target `unit` that runs `python3 -m pytest -q tests_unit` and add `unit` to the .PHONY line. Change nothing else.

Rules:
- Never touch the real store under runs/_api. In a fixture, monkeypatch tokens.API_DIR, tokens.TOKENS, tokens.OWNERS, users.USERS (and users.API_DIR if it is imported there) to paths under pytest's tmp_path.
- No network. For OAuth, set GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET and DAVINCI_CORS_ORIGINS=http://127.0.0.1:4320 with monkeypatch.setenv, and monkeypatch auth._identity to return a fixed (subject, email, name, avatar) tuple. Call the router functions directly (fastapi.testclient is not installed).
- Cover at least: password round-trip and wrong password; register rejects duplicate email, short password, bad email; login returns None for unknown email; session token authenticates with live=False until set_live(..., True); revoked and expired sessions are refused (PermissionError); from_provider links by verified email and drops an unverified password; avatar_ok accepts https googleusercontent/githubusercontent hosts and rejects http, other hosts and look-alike hosts such as googleusercontent.com.evil.io; oauth_start rejects a return_to on a foreign origin (HTTPException 400); oauth_callback state cannot be reused; a successful callback redirects to return_to with #dv_session= and stores the avatar.
- Keep tests short and readable; one behaviour per test.

When done, run `.venv/bin/python -m pytest -q tests_unit` and make sure every test passes. Report the number of tests and anything you could not test.
