"""Hosted DaVINCI API on Modal (temporary, Starter credit).

  modal deploy modal_app.py                       deploy the API
  modal run modal_app.py::grant --email <email>   switch on live runs for an account

The FastAPI app from api/server.py runs in one container (max_containers=1: the run
queue, SSE progress and the sign-in rate limit live in memory) that scales to zero
when idle. runs/ (accounts, sessions, ledger, recorded runs) is a Modal Volume.
Model-written RTL is never simulated here: the pipeline runs with DAVINCI_SANDBOX=modal,
so every compile, test and sweep runs in a separate throwaway Modal Sandbox with no
network and no secrets (agent/modal_sandbox.py).

Secrets come from the Modal secret "davinci-silicon" (META_API_KEY, prices, budget,
admin token, Google/GitHub client ids); .env files are never uploaded.
"""
from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parent
WORKSPACE = "adrianbadjideh"
LABEL = "davinci-api"
PUBLIC_URL = f"https://{WORKSPACE}--{LABEL}.modal.run"
BOARD = "https://davinci-silicon-fe.vercel.app"

app = modal.App("davinci-silicon")
runs = modal.Volume.from_name("davinci-runs", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("fastapi==0.162.0", "uvicorn==0.54.0", "python-multipart==0.0.32",
                 "pillow==13.0.0", "pypdfium2==5.14.0", "modal")
    # Judging window (4-8 Nov 2026): every new account starts live, capped per account per day.
    .env({"DAVINCI_SANDBOX": "modal", "DAVINCI_API_PUBLIC_URL": PUBLIC_URL,
          "DAVINCI_AUTO_LIVE": "1", "DAVINCI_AUTO_LIVE_UNTIL": "2026-11-08", "DAVINCI_LIVE_PER_DAY": "5",
          "DAVINCI_CORS_ORIGINS": f"{BOARD},http://127.0.0.1:4320,http://localhost:3000"})
    .add_local_dir(ROOT, "/root/app", copy=True, ignore=[
        ".git", ".venv", ".claude", "web", "runs", "evidence", "docs", "learn", "**/__pycache__",
        ".env", ".env.*", "CLAUDE.md", "AGENTS.md", "**/*.gds", "layout", "sta"])
)


@app.function(image=image, volumes={"/root/app/runs": runs}, secrets=[modal.Secret.from_name("davinci-silicon")],
              max_containers=1, scaledown_window=120, cpu=0.25, memory=512, timeout=900)
@modal.concurrent(max_inputs=50)
@modal.asgi_app(label=LABEL)
def api():
    import os
    import sys
    os.chdir("/root/app")
    sys.path.insert(0, "/root/app")
    from api.server import app as fastapi_app
    return fastapi_app


@app.function(image=image, volumes={"/root/app/runs": runs})
def grant(email: str, live: bool = True):
    import sys
    sys.path.insert(0, "/root/app")
    from api import users
    u = users.set_live(email, live)
    runs.commit()
    print(f"{u['email']}: live access {'granted' if live else 'removed'}")
