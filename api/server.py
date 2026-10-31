"""DaVINCI HTTP API. Runs execute one at a time in a background worker, each
as a separate `python -m agent.pipeline` process; the API only reads what the
pipeline writes under runs/.

usage: uvicorn api.server:app --port 8000

  POST /runs                     queue a run → {run_id}
  GET  /runs                     list runs
  GET  /runs/{id}                run.json (or queued/running/error status)
  GET  /runs/{id}/events         progress as server-sent events
  GET  /runs/{id}/attempts/{n}/{file}   RTL, model response, simulator logs
  POST /runs/{id}/replay         replay a finished run at $0 → {run_id}
  GET  /mutation                 latest mutation check + weak-test demo
  GET  /ledger                   every model call with cost, plus budget

  POST /extractions              upload a spec image/PDF → {extraction_id}
  GET  /extractions[/{xid}]      extracted list next to spec/requirements.json
  GET  /extractions/{xid}/pages/{n}   page image the model saw
  POST /extractions/{xid}/approve     human approval (may edit the list)
  POST /runs {extraction_id}     run from an approved list

Live providers (meta, baseten) cost money. A run or extraction that uses one,
and approving an extraction, needs `Authorization: Bearer <DAVINCI_API_TOKEN>`.
If DAVINCI_API_TOKEN is not set, those requests are refused (fail closed);
replay and fake runs stay open. The server, not the client, decides where a
simulation runs: model-written RTL only ever runs in the Docker sandbox.
"""
import asyncio
import json
import os
import queue
import re
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from agent import extract as ex
from agent import llm

ROOT = llm.ROOT
RUNS = llm.RUNS
API_DIR = RUNS / "_api"
JOBS_LOG = API_DIR / "jobs.jsonl"
RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
ATTEMPT_FILES = {"sync_fifo.v", "response.md", "prompt.json",
                 "sim/verdict.json", "sim/sim.log", "sim/build.log"}
MUTANTS = {m["id"] for m in json.loads((ROOT / "verify" / "mutants.json").read_text())}

app = FastAPI(title="DaVINCI Silicon API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.environ.get("DAVINCI_CORS_ORIGINS", "http://localhost:3000").split(",") if o],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
    # Lets the hosted board (a public origin) reach an API running on the viewer's
    # own machine; browsers ask for this before calling localhost. Origins above still apply.
    allow_private_network=True,
)


class RunRequest(BaseModel):
    # Unknown fields (e.g. a client-chosen "sandbox") are rejected, not ignored.
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(default_factory=lambda: os.environ.get("DAVINCI_PROVIDER", "meta"))
    gen_provider: str | None = None
    repair_provider: str | None = None
    seed_bug: str | None = None
    max_repairs: int = Field(3, ge=0, le=3)
    spec: str | None = Field(None, description="spec markdown; default spec/fifo_spec.md", max_length=100_000)
    requirements: dict | None = Field(None, description="approved requirements; default spec/requirements.json")
    extraction_id: str | None = Field(None, description="run from an approved image/PDF extraction")


class Approval(BaseModel):
    approved_by: str = Field(..., min_length=1, max_length=200)
    requirements: list[dict] | None = Field(None, description="edited list of {id, text[, maps_to]}; "
                                                              "omit to approve the extracted list as is")


# ---- job worker: one run at a time --------------------------------------------

_jobs: dict[str, dict] = {}
_lock = threading.Lock()
_queue: "queue.Queue[str]" = queue.Queue()


def _log_job(job: dict):
    API_DIR.mkdir(parents=True, exist_ok=True)
    with JOBS_LOG.open("a") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                            **{k: v for k, v in job.items() if k != "argv"}}) + "\n")


def _set(run_id: str, **kw):
    with _lock:
        _jobs[run_id].update(kw)
        job = dict(_jobs[run_id])
    _log_job(job)


def _worker():
    while True:
        run_id = _queue.get()
        job = _jobs[run_id]
        _set(run_id, state="running", started=time.time())
        log = API_DIR / "logs" / f"{run_id}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("w") as f:
            p = subprocess.run([sys.executable, "-m", "agent.pipeline", *job["argv"]],
                               cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
        rj = RUNS / run_id / "run.json"
        status = json.loads(rj.read_text())["status"] if rj.exists() else "error"
        # A run that died before writing run.json is still recorded, with its log tail.
        err = None if rj.exists() else log.read_text()[-2000:]
        _set(run_id, state="done", status=status, exit_code=p.returncode, error=err,
             finished=time.time())


threading.Thread(target=_worker, daemon=True).start()


def _enqueue(run_id: str, argv: list, kind: str) -> dict:
    with _lock:
        if run_id in _jobs or (RUNS / run_id).exists():
            raise HTTPException(409, f"run {run_id} already exists")
        _jobs[run_id] = {"run_id": run_id, "kind": kind, "state": "queued", "argv": argv,
                         "queued": time.time()}
        ahead = sum(j["state"] in ("queued", "running") for j in _jobs.values()) - 1
    _log_job(_jobs[run_id])
    _queue.put(run_id)
    return {"run_id": run_id, "state": "queued", "runs_ahead": ahead}


def _new_id(prefix: str) -> str:
    return f"{prefix}-{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}"


def _check_id(run_id: str):
    if not RUN_ID.match(run_id) or ".." in run_id:
        raise HTTPException(400, "bad run id")


def _require_token(providers: set, authorization: str | None):
    if not providers & set(llm.LIVE):
        return
    token = os.environ.get("DAVINCI_API_TOKEN")
    if not token:
        raise HTTPException(403, "live model calls are disabled: DAVINCI_API_TOKEN is not set on the server")
    if not secrets.compare_digest((authorization or "").encode(), f"Bearer {token}".encode()):
        raise HTTPException(401, "live model runs need the API token; replay and fake runs are open")


# ---- endpoints ------------------------------------------------------------------

@app.post("/runs", status_code=202)
def create_run(req: RunRequest, authorization: str | None = Header(None)):
    providers = {p for p in (req.provider, req.gen_provider, req.repair_provider) if p}
    allowed = [p for p in llm.PROVIDERS if p != "replay"]
    if providers - set(allowed):
        raise HTTPException(422, f"provider must be one of {allowed} (use POST /runs/{{id}}/replay to replay)")
    if req.seed_bug and req.seed_bug not in MUTANTS:
        raise HTTPException(422, f"seed_bug must be one of {sorted(MUTANTS)}")
    _require_token(providers, authorization)

    run_id = _new_id("run")
    # No --sandbox: the pipeline puts any model-written RTL in the Docker sandbox.
    argv = ["--run-id", run_id, "--provider", req.provider, "--max-repairs", str(req.max_repairs)]
    if req.gen_provider:
        argv += ["--gen-provider", req.gen_provider]
    if req.repair_provider:
        argv += ["--repair-provider", req.repair_provider]
    if req.seed_bug:
        argv += ["--seed-bug", req.seed_bug]
    if req.extraction_id:
        if req.spec is not None or req.requirements is not None:
            raise HTTPException(422, "give extraction_id or spec/requirements, not both")
        rec = _extraction(req.extraction_id)
        if "approved" not in rec:
            raise HTTPException(409, f"extraction {req.extraction_id} is not approved ({rec['status']})")
        d = ex.EXTRACT_DIR / req.extraction_id
        argv += ["--requirements", str(d / "approved.json"), "--spec", str(d / "interface_spec.md")]
    elif req.spec is not None or req.requirements is not None:
        inputs = API_DIR / "inputs" / run_id
        inputs.mkdir(parents=True)
        if req.spec is not None:
            (inputs / "spec.md").write_text(req.spec)
            argv += ["--spec", str(inputs / "spec.md")]
        if req.requirements is not None:
            (inputs / "requirements.json").write_text(json.dumps(req.requirements, indent=2))
            argv += ["--requirements", str(inputs / "requirements.json")]
    return _enqueue(run_id, argv, "run")


@app.post("/runs/{run_id}/replay", status_code=202)
def replay_run(run_id: str):
    _check_id(run_id)
    src = RUNS / run_id
    if not (src / "run.json").exists() or not (src / "calls.jsonl").exists():
        raise HTTPException(404, f"no finished run {run_id} with recorded model calls")
    new_id = f"{run_id[:40]}-replay-{secrets.token_hex(2)}"
    return _enqueue(new_id, ["--run-id", new_id, "--provider", "replay", "--replay-from", run_id], "replay")


def _summary(d: Path) -> dict:
    r = json.loads((d / "run.json").read_text())
    return {k: r.get(k) for k in ("run_id", "status", "started", "providers", "seed_bug", "replayed_from",
                                  "attempts_total", "attempts_to_green", "time_to_green_s", "cost_usd")}


@app.get("/runs")
def list_runs():
    done = [_summary(d) for d in RUNS.iterdir() if (d / "run.json").exists()] if RUNS.exists() else []
    done.sort(key=lambda r: r.get("started") or "", reverse=True)
    with _lock:
        jobs = [{k: v for k, v in j.items() if k != "argv"} for j in _jobs.values()]
    return {"jobs": jobs, "runs": done}


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    _check_id(run_id)
    rj = RUNS / run_id / "run.json"
    if rj.exists():
        return json.loads(rj.read_text())
    with _lock:
        job = dict(_jobs.get(run_id) or {})
    if not job:
        raise HTTPException(404, f"no run {run_id}")
    job.pop("argv", None)
    if job["state"] == "running":
        ev = RUNS / run_id / "events.jsonl"
        job["events"] = [json.loads(l) for l in ev.read_text().splitlines()] if ev.exists() else []
    return job


@app.get("/runs/{run_id}/events")
async def run_events(run_id: str, request: Request):
    """Server-sent events: one per line of runs/<id>/events.jsonl, then `end`.
    The SSE id is the line number, so a client can resume with Last-Event-ID."""
    _check_id(run_id)
    if run_id not in _jobs and not (RUNS / run_id).exists():
        raise HTTPException(404, f"no run {run_id}")
    start = int(request.headers.get("last-event-id", "-1")) + 1

    async def stream():
        sent, ev, said_queued = start, RUNS / run_id / "events.jsonl", False
        while True:
            lines = ev.read_text().splitlines() if ev.exists() else []
            for i in range(sent, len(lines)):
                kind = json.loads(lines[i]).get("type", "message")
                yield f"id: {i}\nevent: {kind}\ndata: {lines[i]}\n\n"
            sent = max(sent, len(lines))
            job = _jobs.get(run_id)
            finished = (RUNS / run_id / "run.json").exists() or (job and job["state"] == "done")
            if finished and sent >= len(ev.read_text().splitlines() if ev.exists() else []):
                status = job.get("status") if job else json.loads((RUNS / run_id / "run.json").read_text())["status"]
                yield f"event: end\ndata: {json.dumps({'status': status})}\n\n"
                return
            if job and job["state"] == "queued" and not said_queued:
                said_queued = True
                yield f"event: queued\ndata: {json.dumps({'run_id': run_id})}\n\n"
            if await request.is_disconnected():
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/runs/{run_id}/attempts/{n}/{path:path}", response_class=PlainTextResponse)
def attempt_file(run_id: str, n: int, path: str):
    _check_id(run_id)
    if path not in ATTEMPT_FILES:
        raise HTTPException(404, f"file must be one of {sorted(ATTEMPT_FILES)}")
    f = RUNS / run_id / f"attempt_{n}" / path
    if not f.exists():
        raise HTTPException(404, f"{path} not recorded for attempt {n}")
    return f.read_text(errors="replace")


@app.get("/mutation")
def mutation():
    out = {"label": "measured"}
    for key, f in (("mutation", RUNS / "mutation" / "mutation.json"),
                   ("weak_demo", RUNS / "weak_demo" / "weak_demo.json")):
        out[key] = json.loads(f.read_text()) if f.exists() else None
    if out["mutation"] is None:
        raise HTTPException(404, "no mutation check recorded yet: run `make mutate`")
    # A score only means something next to runs that used the same suite.
    pinned = (ROOT / "verify" / "suite.sha256").read_text().strip()
    out["pinned_suite_sha256"] = pinned
    for key in ("mutation", "weak_demo"):
        if out[key] is not None:
            out[key]["matches_pinned_suite"] = out[key].get("suite_sha256") == pinned
    return out


@app.get("/ledger")
def ledger():
    entries = [json.loads(l) for l in llm.LEDGER.read_text().splitlines() if l.strip()] \
        if llm.LEDGER.exists() else []
    by_provider: dict = {}
    for e in entries:
        b = by_provider.setdefault(e["provider"], {"calls": 0, "ok": 0, "cost_usd": 0.0})
        b["calls"] += 1
        b["ok"] += e.get("status") == "ok"
        b["cost_usd"] = round(b["cost_usd"] + float(e.get("cost_usd") or 0), 6)
    spent = round(sum(b["cost_usd"] for b in by_provider.values()), 6)
    return {"label": "measured", "spent_usd": spent, "budget_usd": llm.budget_usd(),
            "remaining_usd": round(llm.budget_usd() - spent, 6), "by_provider": by_provider, "entries": entries}


@app.get("/health")
def health():
    return {"ok": True, "queue": _queue.qsize()}


# ---- image/PDF spec input -----------------------------------------------------

MAX_UPLOAD = 20_000_000
_extractions: dict[str, dict] = {}


def _extraction(xid: str) -> dict:
    try:
        return ex.load(xid)
    except ValueError:
        raise HTTPException(400, "bad extraction id") from None
    except FileNotFoundError:
        job = _extractions.get(xid)
        if not job:
            raise HTTPException(404, f"no extraction {xid}") from None
        return dict(job)


def _run_extraction(xid: str, path: Path, provider: str):
    log = API_DIR / "logs" / f"{xid}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w") as f:
        p = subprocess.run([sys.executable, "-m", "agent.extract", str(path), "--provider", provider, "--xid", xid],
                           cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    done = (ex.EXTRACT_DIR / xid / "extracted.json").exists()
    _extractions[xid].update(status="done" if done else "error", exit_code=p.returncode,
                             error=None if done else log.read_text()[-2000:])
    _log_job({"run_id": xid, "kind": "extraction", **_extractions[xid]})


@app.post("/extractions", status_code=202)
async def create_extraction(file: UploadFile = File(...), provider: str = Form("meta"),
                            authorization: str | None = Header(None)):
    if provider not in ("meta", "baseten", "fake"):
        raise HTTPException(422, "provider must be meta, baseten or fake")
    _require_token({provider}, authorization)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix != ".pdf" and suffix not in ex.IMAGE_MIME:
        raise HTTPException(422, f"file must be PDF or one of {sorted(ex.IMAGE_MIME)}")
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, f"file larger than {MAX_UPLOAD} bytes")
    xid = ex.new_xid()
    up = API_DIR / "uploads" / xid
    up.mkdir(parents=True)
    # Keep the original name (it is recorded as the source), made safe for the filesystem.
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(file.filename or "upload").stem).strip("._")[:80] or "upload"
    path = up / f"{stem}{suffix}"
    path.write_bytes(data)
    _extractions[xid] = {"extraction_id": xid, "status": "running", "provider": provider,
                         "source": {"name": Path(file.filename or "upload").name, "bytes": len(data)}}
    _log_job({"run_id": xid, "kind": "extraction", **_extractions[xid]})
    threading.Thread(target=_run_extraction, args=(xid, path, provider), daemon=True).start()
    return {"extraction_id": xid, "status": "running"}


@app.get("/extractions")
def list_extractions():
    out = []
    if ex.EXTRACT_DIR.exists():
        for d in sorted(ex.EXTRACT_DIR.iterdir(), reverse=True):
            if (d / "extracted.json").exists():
                r = ex.load(d.name)
                out.append({k: r.get(k) for k in ("extraction_id", "status", "created", "provider", "cost_usd")}
                           | {"source": r["source"]["name"], "approved": "approved" in r})
    running = [j for j in _extractions.values() if j["status"] != "done"]
    return {"running": running, "extractions": out}


@app.get("/extractions/{xid}")
def get_extraction(xid: str):
    rec = _extraction(xid)
    rec["reference"] = json.loads(ex.REFERENCE.read_text())
    # The newest re-run of the map step (python -m agent.extract --remap), if any:
    # AI interpretation like the original mapping, shown in its place by the UI.
    d = ex.EXTRACT_DIR / xid
    remaps = sorted(d.glob("remap_*.json")) if d.exists() else []
    rec["latest_remap"] = json.loads(remaps[-1].read_text()) if remaps else None
    return rec


@app.get("/extractions/{xid}/pages/{n}")
def extraction_page(xid: str, n: int):
    _extraction(xid)
    f = ex.EXTRACT_DIR / xid / "pages" / f"page_{n}.png"
    if not f.exists():
        raise HTTPException(404, f"no page {n}")
    return FileResponse(f, media_type="image/png")


@app.post("/extractions/{xid}/approve")
def approve_extraction(xid: str, body: Approval, authorization: str | None = Header(None)):
    _require_token(set(llm.LIVE), authorization)  # approval is a trust decision: same gate as live runs
    _extraction(xid)
    try:
        rec = ex.approve(xid, body.approved_by, body.requirements)
    except ValueError as e:
        code = 409 if "already approved" in str(e) or "is running" in str(e) or "is aborted" in str(e) else 422
        raise HTTPException(code, str(e)) from None
    _log_job({"run_id": xid, "kind": "approval", "status": "approved", "approved_by": body.approved_by,
              "approved_sha256": rec["approved_sha256"]})
    return rec
