"""DaVINCI verified loop: spec → model writes RTL → frozen suite → bounded repair.

The model only ever writes RTL into runs/<id>/. The frozen suite is hashed
before the run, after every simulation and at the end; any change aborts.
Every attempt (seeded, rejected, failed, aborted) is recorded in run.json.

usage:
  python -m agent.pipeline --run-id live01                    # live, Meta
  python -m agent.pipeline --run-id demo01 --seed-bug M1      # demo path
  python -m agent.pipeline --run-id live01 --provider replay  # $0 replay of live01
  python -m agent.pipeline --run-id dry01 --provider fake     # offline dry run
"""
import argparse
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from agent import llm

ROOT = llm.ROOT
RUNS = llm.RUNS
TESTS = ROOT / "tests"
SUITE_LOCK = ROOT / "verify" / "suite.sha256"
SWEEP_LOCK = ROOT / "verify" / "sweep.sha256"
AI_LABEL = "AI interpretation · not verified"

# Generated RTL must not reach outside the simulator. A list of banned system
# tasks was bypassed on 31 Oct (`define + `` token pasting rebuilt $fopen, and
# $fwriteh slipped past the word boundary), so the rule is now total: no `$`
# at all, and no compiler directive except `timescale. The sync FIFO needs
# neither. The sandbox, not this check, is the security boundary.
DOLLAR = re.compile(r"\$")
DIRECTIVE = re.compile(r"`(?!timescale\b)")
# Simulation-only constructs that synthesis ignores or rejects; checked with
# comments removed. `#(` stays legal: it opens the parameter list.
SIM_ONLY = [(re.compile(r"\binitial\b"), "initial block"),
            (re.compile(r"#\s*[\d.A-Za-z_]"), "# delay")]
COMMENTS = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
INTERFACE = json.loads((ROOT / "spec" / "interface.json").read_text())
PORT_DECL = re.compile(r"\b(input|output|inout)\b(?:\s+(?:wire|reg|signed))*\s*(?:\[[^\]]*\]\s*)?"
                       r"((?:(?!input\b|output\b|inout\b|wire\b|reg\b)[A-Za-z_]\w*\s*(?:,\s*)?)+)")
MAX_RTL_BYTES = 64_000
SIM_TIMEOUT_S = 180
SANDBOX_IMAGE = os.environ.get("DAVINCI_SANDBOX_IMAGE", "davinci-sim:latest")
# Same limits as `make sandbox`: no network, capped CPU/memory/processes,
# read-only root, no capabilities, non-root user (set in the image).
DOCKER_LIMITS = ["--network", "none", "--cpus", "1", "--memory", "512m", "--pids-limit", "256",
                 "--read-only", "--tmpfs", "/tmp:size=64m", "--cap-drop", "ALL",
                 "--security-opt", "no-new-privileges"]

SYSTEM = """You are a careful RTL engineer. You write synthesisable Verilog-2001.
Answer with exactly one fenced ```verilog block that contains the complete module.
Do not use any $ system task or function, and no compiler directive other than `timescale.
Keep the module name, parameters and ports exactly as the spec gives them."""


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def suite_hash(block: dict | None = None) -> str:
    sys.path.insert(0, str(ROOT / "verify"))
    if block:  # S7: a registered block other than the FIFO (verify/run_block.py)
        from run_block import suite_hash as bh
        return bh(block)
    from run_suite import suite_hash as h
    return h()


def load_block(name: str) -> dict | None:
    """Registry entry (blocks/<name>/block.json) for a block other than the FIFO;
    None for sync_fifo, whose paths, prompts and gates stay as they were."""
    if name == "sync_fifo":
        return None
    sys.path.insert(0, str(ROOT / "verify"))
    from run_block import load
    return load(name)


def check_suite(expected: str, when: str, block: dict | None = None):
    got = suite_hash(block)
    if got != expected:
        raise SystemExit(f"ABORT: frozen suite changed ({when}): {got} != {expected}")


def check_sweep(expected: str, when: str):
    sys.path.insert(0, str(ROOT / "verify"))
    from run_sweep import sweep_hash
    got = sweep_hash()
    if got != expected:
        raise SystemExit(f"ABORT: parameter sweep changed ({when}): {got} != {expected}")


def apply_mutant(src: str, mutant_id: str, mutants_file: Path = ROOT / "verify" / "mutants.json") -> tuple[str, dict]:
    mutants = {m["id"]: m for m in json.loads(mutants_file.read_text())}
    if mutant_id not in mutants:
        raise SystemExit(f"unknown mutant {mutant_id}; have {sorted(mutants)}")
    m = mutants[mutant_id]
    if src.count(m["find"]) != 1:
        raise SystemExit(f"{mutant_id} does not apply to the reference RTL")
    return src.replace(m["find"], m["replace"]), m


def extract(text: str, top: str = "sync_fifo") -> tuple[str | None, str]:
    """Return (rtl, diagnosis) from a model reply. rtl is the last fenced block
    that defines the top module; diagnosis is the prose before the first fence."""
    blocks = re.findall(r"```[a-zA-Z]*\n(.*?)```", text, flags=re.S)
    rtl = next((b for b in reversed(blocks) if re.search(rf"\bmodule\s+{top}\b", b)), None)
    if rtl is None and re.search(rf"\bmodule\s+{top}\b", text) and "```" not in text:
        rtl = text  # bare Verilog with no fence
    prose = text.split("```", 1)[0].strip()
    prose = re.sub(r"^\s*DIAGNOSIS:\s*", "", prose, flags=re.I)
    return rtl, prose


def validate(rtl: str | None, top: str = "sync_fifo", interface: dict | None = None) -> str | None:
    """Reason to reject the RTL before simulation, or None if it may run."""
    if rtl is None:
        return f"no Verilog block defining module {top} in the reply"
    if len(rtl.encode()) > MAX_RTL_BYTES:
        return f"RTL larger than {MAX_RTL_BYTES} bytes"
    for rule, what in ((DOLLAR, "system task or function ($)"), (DIRECTIVE, "compiler directive (`)")):
        m = rule.search(rtl)
        if m:
            line = rtl.count("\n", 0, m.start()) + 1
            snippet = rtl.splitlines()[line - 1].strip()[:80]
            return f"forbidden {what} on line {line}: {snippet!r}"
    code = COMMENTS.sub(" ", rtl)
    for rule, what in SIM_ONLY:
        if rule.search(code):
            return f"simulation-only construct not allowed in synthesisable RTL: {what}"
    got = ports(code)
    want = {p["name"]: p["dir"] for p in (interface or INTERFACE)["ports"]}
    if got != want:
        missing = sorted(set(want) - set(got))
        extra = sorted(set(got) - set(want))
        wrong = sorted(k for k in set(got) & set(want) if got[k] != want[k])
        parts = [f"{label} {names}" for label, names in (("missing", missing), ("extra", extra),
                                                         ("wrong direction", wrong)) if names]
        return f"port list does not match the spec interface ({'; '.join(parts)})"
    return None


def ports(code: str) -> dict:
    """{port name: direction} declared in the module, ANSI header or body."""
    found = {}
    # Arguments of functions and tasks are declared with input/output too; they are not ports.
    code = re.sub(r"\b(function|task)\b.*?\bend\1\b", "", code, flags=re.S)
    for direction, names in PORT_DECL.findall(code):
        for name in re.split(r"\s*,\s*", names.strip().rstrip(",")):
            if name:
                found[name] = direction
    return found


def compile_check(rtl_path: Path, backend: str) -> tuple[bool, str]:
    """Measured: does the RTL compile as plain Verilog-2001 (no SystemVerilog)?
    Runs where the simulation would run. Returns (ok, compiler output)."""
    cmd = ["iverilog", "-g2001", "-Wall", "-o", "/dev/null"]
    if backend == "docker":
        cmd = ["docker", "run", "--rm", *DOCKER_LIMITS, "--entrypoint", "timeout",
               "-v", f"{rtl_path.resolve()}:/work/in/dut.v:ro", SANDBOX_IMAGE, "60", *cmd, "/work/in/dut.v"]
        env = None
    else:
        cmd = [*cmd, str(rtl_path)]
        env = local_env()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)
    except subprocess.TimeoutExpired:
        return False, "compile check exceeded 120 s"
    out = (p.stdout + p.stderr).replace(str(rtl_path.resolve()), "dut.v").replace("/work/in/dut.v", "dut.v")
    return p.returncode == 0, out.strip()[-2000:]


# Model-written RTL is untrusted: it may only be simulated inside the sandbox.
# The fake provider returns the reference RTL, so local runs stay possible for
# development; DAVINCI_ALLOW_LOCAL_SIM=1 is an explicit operator override.
def model_rtl_possible(providers: set, source_run: str | None) -> bool:
    if providers & set(llm.LIVE):
        return True
    if source_run:  # a replay re-simulates whatever the source run's model wrote
        src = json.loads((RUNS / source_run / "run.json").read_text()).get("providers", {})
        return bool(set(src.values()) & (set(llm.LIVE) | {"replay"}))
    return False


def choose_sandbox(requested: str | None, providers: set, source_run: str | None) -> str:
    untrusted = model_rtl_possible(providers, source_run)
    backend = requested or ("docker" if untrusted else "local")
    if backend == "local" and untrusted and os.environ.get("DAVINCI_ALLOW_LOCAL_SIM") != "1":
        raise SystemExit("refusing to simulate model-written RTL outside the sandbox: use --sandbox docker "
                         "(or set DAVINCI_ALLOW_LOCAL_SIM=1 to override deliberately)")
    return backend


def local_env() -> dict:
    """Environment for a local simulation: enough to find the tools, no secrets."""
    keep = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT")
    return {k: os.environ[k] for k in keep if k in os.environ}


def sandbox_image_id() -> str | None:
    r = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", SANDBOX_IMAGE],
                       capture_output=True, text=True)
    return r.stdout.strip() or None


def simulate(rtl_path: Path, out: Path, backend: str = "local", block: dict | None = None) -> dict:
    """Run the frozen suite on rtl_path and return the verdict (measured).
    local:  a separate Python process with a hard timeout.
    docker: the locked-down sandbox image; RTL mounted read-only."""
    out.mkdir(parents=True, exist_ok=True)
    if backend == "docker":
        cmd = ["docker", "run", "--rm", *DOCKER_LIMITS,
               "-v", f"{rtl_path.resolve()}:/work/in/dut.v:ro", "-v", f"{out.resolve()}:/work/out", SANDBOX_IMAGE]
    else:
        cmd = [sys.executable, str(ROOT / "verify" / "run_suite.py"), str(rtl_path), "--out", str(out)]
    if block:  # S7: other blocks run through verify/run_block.py (same limits in docker)
        if backend == "docker":
            cmd = [*cmd[:-1], "--entrypoint", "timeout", SANDBOX_IMAGE, "120", "python", "verify/run_block.py",
                   block["name"], "/work/in/dut.v", "--out", "/work/out"]
        else:
            cmd = [sys.executable, str(ROOT / "verify" / "run_block.py"), block["name"], str(rtl_path), "--out", str(out)]
    env = None if backend == "docker" else local_env()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=SIM_TIMEOUT_S, cwd=ROOT, env=env)
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "passed": 0, "total": 0, "tests": [],
                "error": f"simulation exceeded {SIM_TIMEOUT_S}s", "sandbox": backend}
    vf = out / "verdict.json"
    if not vf.exists():
        # The in-container `timeout 120` exits 124 without a verdict.
        status = "timeout" if p.returncode == 124 else "sim_error"
        return {"status": status, "passed": 0, "total": 0, "tests": [], "sandbox": backend,
                "error": f"runner wrote no verdict (exit {p.returncode}): {p.stderr[-1500:]}"}
    return json.loads(vf.read_text()) | {"sandbox": backend}


def sweep(rtl_path: Path, out: Path, backend: str) -> dict:
    """G3: run the parameter sweep (verify/run_sweep.py) where the simulation ran.
    Measured; its output never goes into a prompt."""
    out.mkdir(parents=True, exist_ok=True)
    if backend == "docker":
        cmd = ["docker", "run", "--rm", *DOCKER_LIMITS, "--entrypoint", "timeout",
               "-v", f"{rtl_path.resolve()}:/work/in/dut.v:ro", "-v", f"{out.resolve()}:/work/out",
               SANDBOX_IMAGE, "120", "python", "verify/run_sweep.py", "/work/in/dut.v", "--out", "/work/out"]
        env = None
    else:
        cmd = [sys.executable, str(ROOT / "verify" / "run_sweep.py"), str(rtl_path), "--out", str(out)]
        env = local_env()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=SIM_TIMEOUT_S, cwd=ROOT, env=env)
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "sets": [], "error": f"sweep exceeded {SIM_TIMEOUT_S}s"}
    f = out / "sweep.json"
    if not f.exists():
        return {"status": "sim_error", "sets": [], "error": f"sweep wrote no result (exit {p.returncode}): "
                                                           f"{p.stderr[-1000:]}"}
    return json.loads(f.read_text())


def interface_problems(spec: str, reqs: dict, block: dict | None = None) -> list[str]:
    """Can the frozen suite verify a design built from this spec and requirement
    list at all? A syntactic guard: block, parameters, port names, test names.
    It cannot judge whether the requirement text matches what the tests check."""
    sys.path.insert(0, str(ROOT / "verify"))
    from run_suite import all_tests
    INTERFACE, top = globals()["INTERFACE"], "sync_fifo"
    if block:
        from run_block import all_tests as block_tests
        INTERFACE, top = json.loads((ROOT / block["interface"]).read_text()), block["top"]
        all_tests = lambda: block_tests(block)  # noqa: E731
    problems = []
    if reqs.get("block") != INTERFACE["block"]:
        problems.append(f"block is {reqs.get('block')!r}, the suite verifies {INTERFACE['block']!r}")
    params = {k: v for k, v in (reqs.get("params") or {}).items() if k in INTERFACE["params"]}
    if params != INTERFACE["params"]:
        problems.append(f"params {reqs.get('params')} differ from the suite's {INTERFACE['params']}")
    known = set(all_tests())
    unknown = sorted({t for r in reqs.get("requirements", []) for t in r.get("tests", [])} - known)
    if unknown:
        problems.append(f"requirements name tests the suite does not have: {unknown}")
    if not re.search(rf"\bmodule\s+{top}\b", spec):
        problems.append(f"spec does not define module {top}")
    missing = [p["name"] for p in INTERFACE["ports"] if not re.search(rf"\b{p['name']}\b", spec)]
    if missing:
        problems.append(f"spec does not mention ports {missing}")
    return problems


def measured_feedback(verdict: dict | None, rejection: str | None) -> str:
    """What the simulator (or the pre-check) actually reported, for the repair prompt."""
    if rejection:
        return f"The previous answer was rejected before simulation: {rejection}."
    v = verdict
    lines = [f"Simulator verdict: {v['status']}, {v.get('passed', 0)}/{v.get('total', 0)} tests passed."]
    if v["status"] == "compile_error":
        lines.append("Compile output:\n" + (v.get("log") or v.get("error", ""))[-3000:])
    for t in v.get("tests", []):
        if not t["passed"]:
            lines.append(f"- {t['name']}: {t['message']}")
    if v.get("error") and v["status"] != "compile_error":
        lines.append(v["error"][-1500:])
    return "\n".join(lines)


def spec_context(spec: str, reqs: str) -> str:
    return f"## Specification\n\n{spec}\n\n## Approved requirements\n\n```json\n{reqs}\n```"


def gen_messages(ctx: str, top: str = "sync_fifo") -> list:
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"{ctx}\n\nWrite the complete `{top}` module that meets every requirement."}]


def repair_messages(ctx: str, rtl: str | None, feedback: str) -> list:
    # rtl is the last version that was simulated, even if a later answer was rejected.
    prev = f"```verilog\n{rtl}```" if rtl else "(no RTL has been simulated yet)"
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content":
                f"{ctx}\n\n## Last simulated RTL\n\n{prev}\n\n## Measured result\n\n{feedback}\n\n"
                "Start with one line `DIAGNOSIS:` explaining the root cause in one or two sentences, "
                "then give the complete corrected module in one ```verilog block."}]


class Run:
    def __init__(self, run_id: str):
        self.id, self.dir = run_id, RUNS / run_id
        if self.dir.exists():
            raise SystemExit(f"{self.dir} exists; pick a new --run-id (runs are never overwritten)")
        self.dir.mkdir(parents=True)
        self.t0 = time.time()

    def event(self, kind: str, **data):
        with (self.dir / "events.jsonl").open("a") as f:
            f.write(json.dumps({"t": round(time.time() - self.t0, 2), "type": kind, **data}) + "\n")
        print(f"[{time.time() - self.t0:6.1f}s] {kind} " + " ".join(f"{k}={v}" for k, v in data.items()
                                                                      if not isinstance(v, (dict, list))), flush=True)

    def log_call(self, step: str, attempt: int, reply: "llm.Reply | None", error: str | None, h: str | None):
        rec = {"step": step, "attempt": attempt, "ok": reply is not None, "error": error,
               **(llm.reply_dict(reply) if reply else {"request_sha256": h})}
        with (self.dir / "calls.jsonl").open("a") as f:
            f.write(json.dumps(rec) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--provider", default=os.environ.get("DAVINCI_PROVIDER", "meta"), choices=llm.PROVIDERS)
    ap.add_argument("--gen-provider", default=os.environ.get("DAVINCI_PROVIDER_GEN"), choices=llm.PROVIDERS)
    ap.add_argument("--repair-provider", default=os.environ.get("DAVINCI_PROVIDER_REPAIR"), choices=llm.PROVIDERS)
    ap.add_argument("--replay-from", help="run to replay; --run-id then names the new run")
    ap.add_argument("--seed-bug", help="start from the reference RTL with this mutant applied (e.g. M1)")
    ap.add_argument("--max-repairs", type=int, default=3)
    ap.add_argument("--sandbox", default=os.environ.get("DAVINCI_SANDBOX") or None, choices=["local", "docker"],
                    help="where the simulator runs; default docker whenever model-written RTL is involved")
    ap.add_argument("--reasoning-effort", default=os.environ.get("DAVINCI_REASONING_EFFORT"))
    ap.add_argument("--spec", type=Path, default=ROOT / "spec" / "fifo_spec.md")
    ap.add_argument("--requirements", type=Path, default=ROOT / "spec" / "requirements.json")
    ap.add_argument("--breakdown", metavar="BID", help="approved design breakdown to pass into the RTL prompt (agent.breakdown)")
    ap.add_argument("--block", default="sync_fifo", help="registered block (blocks/<name>/block.json); default sync_fifo")
    a = ap.parse_args(argv)

    replayer, source = None, None
    if "replay" in (a.provider, a.gen_provider, a.repair_provider):
        a.provider = a.gen_provider = a.repair_provider = "replay"
        # --replay-from X --run-id Y replays X into Y; --run-id X alone replays X into X-replayN.
        source = a.replay_from or a.run_id
        replayer = llm.Replayer(source)
        src_run = json.loads((RUNS / source / "run.json").read_text())
        a.seed_bug = src_run.get("seed_bug")
        a.block = src_run.get("block", "sync_fifo")
        # Replay against the inputs the source run used, unless overridden.
        if not a.breakdown and src_run.get("breakdown"):
            a.breakdown = src_run["breakdown"]["breakdown_id"]
        for opt, key in (("spec", "spec_file"), ("requirements", "requirements_file")):
            if getattr(a, opt) == ap.get_default(opt) and src_run.get(key) and Path(src_run[key]).exists():
                setattr(a, opt, Path(src_run[key]))
        if not a.replay_from:
            n = 1
            while (RUNS / f"{source}-replay{n}").exists():
                n += 1
            a.run_id = f"{source}-replay{n}"
    gen_p = a.gen_provider or a.provider
    rep_p = a.repair_provider or a.provider
    # S7: blocks other than the FIFO bring their own spec, suite pin, interface and
    # mutants; G3 (parameter sweep) exists for the FIFO only. blk is None for sync_fifo.
    blk = load_block(a.block)
    top = blk["top"] if blk else "sync_fifo"
    iface = json.loads((ROOT / blk["interface"]).read_text()) if blk else INTERFACE
    if blk:
        for opt in ("spec", "requirements"):
            if getattr(a, opt) == ap.get_default(opt):
                setattr(a, opt, ROOT / blk[opt])
        if a.breakdown:
            raise SystemExit("--breakdown is FIFO-only for now")

    a.sandbox = choose_sandbox(a.sandbox, {gen_p, rep_p}, source)
    locked = (ROOT / blk["suite_lock"] if blk else SUITE_LOCK).read_text().strip()
    check_suite(locked, "before run", blk)
    sweep_locked = SWEEP_LOCK.read_text().strip() if not blk else None
    if not blk:
        check_sweep(sweep_locked, "before run")
    image_id = None
    if a.sandbox == "docker":
        image_id = sandbox_image_id()
        if not image_id:
            raise SystemExit(f"sandbox image {SANDBOX_IMAGE} not found: run `make image`")
    run = Run(a.run_id)
    spec, reqs = a.spec.read_text(), a.requirements.read_text()
    ctx = spec_context(spec, reqs)
    approved_breakdown = None
    if a.breakdown:  # S1: the human-approved breakdown goes into every RTL prompt
        from agent import breakdown as bd
        rec_b = bd.load(a.breakdown)
        if "approved" not in rec_b:
            raise SystemExit(f"breakdown {a.breakdown} is not approved (python -m agent.breakdown --approve {a.breakdown} --by NAME)")
        approved_breakdown = rec_b["approved"]
        ctx = f"{ctx}\n\n{bd.prompt_section(approved_breakdown)}"
    # Reasoning counts toward output; 8000 cut off a full module on 31 Oct.
    opts = {"max_tokens": int(os.environ.get("DAVINCI_MAX_OUTPUT_TOKENS", "24000"))}
    if a.reasoning_effort:
        opts["reasoning_effort"] = a.reasoning_effort

    record = {
        "run_id": run.id, "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "providers": {"generate": gen_p, "repair": rep_p}, "seed_bug": a.seed_bug,
        "replayed_from": source, "max_repairs": a.max_repairs,
        "sandbox": {"backend": a.sandbox, "image": SANDBOX_IMAGE if image_id else None, "image_id": image_id},
        "suite_sha256": locked, "spec_sha256": sha256(spec.encode()), "requirements_sha256": sha256(reqs.encode()),
        "attempts": [],
    }
    if blk:
        record["block"] = blk["name"]
    approved = json.loads(reqs)
    if approved.get("extraction_id"):  # requirements came from an approved image/PDF extraction
        record["extraction"] = {"extraction_id": approved["extraction_id"], "approved_sha256": sha256(reqs.encode()),
                                "approved_by": approved.get("approved_by"), "approved_at": approved.get("approved_at"),
                                "source": approved.get("source", {}).get("name"), "untested": approved.get("untested")}
    record["spec_file"], record["requirements_file"] = str(a.spec), str(a.requirements)
    if approved_breakdown:
        record["breakdown"] = {"breakdown_id": approved_breakdown["breakdown_id"],
                               "approved_sha256": rec_b["approved_sha256"],
                               "approved_by": approved_breakdown["approved_by"],
                               "approved_at": approved_breakdown["approved_at"],
                               "cost_usd": rec_b.get("cost_usd"), "provider": rec_b.get("provider")}
        (run.dir / "breakdown.json").write_text(json.dumps(approved_breakdown, indent=2))
    record["sweep_sha256"] = sweep_locked
    if blk:
        record["sweep"] = "not run: the G3 parameter sweep exists for sync_fifo only"
    run.event("run_started", run_id=run.id, generate=gen_p, repair=rep_p, seed_bug=a.seed_bug or "-")

    problems = interface_problems(spec, approved, blk)
    if problems:  # the frozen suite cannot judge this design: no model call, no verdict
        record.update(finished=time.strftime("%Y-%m-%dT%H:%M:%S%z"), status="not_verifiable",
                      not_verifiable=problems, attempts_total=0, attempts_to_green=None, first_pass=False,
                      time_to_green_s=None, wall_seconds=round(time.time() - run.t0, 2), cost_usd=0.0,
                      tokens={"in": 0, "out": 0})
        (run.dir / "run.json").write_text(json.dumps(record, indent=2))
        run.event("run_finished", status="not_verifiable", attempts=0, cost_usd=0.0)
        return 3

    # last_rtl is the last version that was simulated; a rejected answer never replaces it.
    last_rtl, verdict, rejection, final, simulated = None, None, None, "fail", {}
    for n in range(1, a.max_repairs + 2):
        adir = run.dir / f"attempt_{n}"
        adir.mkdir()
        att = {"n": n, "started_s": round(time.time() - run.t0, 2)}
        step = "generate" if n == 1 else "repair"
        diagnosis, reply = None, None

        if n == 1 and a.seed_bug:
            rtl, m = apply_mutant((ROOT / (blk["reference_rtl"] if blk else "rtl/sync_fifo.v")).read_text(), a.seed_bug,
                                  ROOT / (blk["mutants"] if blk else "verify/mutants.json"))
            att.update(source="seeded", seeded={"mutant": m["id"], "req": m["req"], "desc": m["desc"]})
            run.event("seeded", attempt=n, mutant=m["id"], desc=m["desc"])
        else:
            provider = gen_p if step == "generate" else rep_p
            msgs = gen_messages(ctx, top) if step == "generate" else \
                repair_messages(ctx, last_rtl, measured_feedback(verdict, rejection))
            (adir / "prompt.json").write_text(json.dumps(msgs, indent=1))
            run.event("model_call", attempt=n, step=step, provider=provider)
            h = llm.request_hash(msgs, opts)
            try:
                reply = llm.call(msgs, provider=provider, step=step, run_id=run.id, replayer=replayer, **opts)
            except (llm.BudgetError, llm.LLMError) as e:
                run.log_call(step, n, None, str(e), h)
                att.update(source="model", provider=provider, status="aborted", error=str(e))
                record["attempts"].append(att)
                run.event("aborted", attempt=n, error=str(e))
                final = "aborted"
                break
            run.log_call(step, n, reply, None, h)
            (adir / "response.md").write_text(reply.text)
            rtl, diagnosis = extract(reply.text, top)
            att.update(source="model", provider=reply.provider, model=reply.model,
                       tokens_in=reply.tokens_in, tokens_out=reply.tokens_out,
                       cost_usd=reply.cost_usd, model_seconds=reply.seconds, **reply.extra)

        if step == "repair" and diagnosis:
            att["ai_interpretation"] = {"label": AI_LABEL, "diagnosis": diagnosis[:2000]}
            run.event("diagnosis", attempt=n, label=AI_LABEL, text=diagnosis[:300])

        rejection = validate(rtl, top, iface)
        status = "rejected"
        if rejection and reply is not None and reply.extra.get("finish_reason") == "length":
            # A configuration limit, not a model mistake: counted, but under its own status.
            status = "truncated"
            rejection = f"reply cut off at the output token limit ({opts['max_tokens']} tokens); {rejection}"
        rtl_path = adir / f"{top}.v"
        if not rejection:
            assert TESTS not in rtl_path.parents
            rtl_path.write_text(rtl)
            ok, compiler = compile_check(rtl_path, a.sandbox)
            att["measured_compile"] = {"label": "measured", "ok": ok, "tool": "iverilog -g2001 -Wall",
                                       "output": compiler}
            if not ok:
                rejection = f"does not compile as Verilog-2001 (iverilog -g2001 -Wall):\n{compiler}"
        if rejection:
            att.update(status=status, measured={"label": "measured", "rejection": rejection})
            record["attempts"].append(att)
            run.event(status, attempt=n, reason=rejection[:300])
            verdict = None
            continue

        att["rtl_sha256"] = sha256(rtl.encode())
        if last_rtl:
            att["diff_vs_prev"] = "".join(difflib.unified_diff(
                last_rtl.splitlines(True), rtl.splitlines(True), "last_simulated", f"attempt_{n}"))
        if att["rtl_sha256"] in simulated:  # the same design again: repair has stalled
            att.update(status="no_progress", measured={"label": "measured",
                                                       "same_as_attempt": simulated[att["rtl_sha256"]]})
            record["attempts"].append(att)
            run.event("no_progress", attempt=n, same_as=simulated[att["rtl_sha256"]])
            final = "no_progress"
            break
        simulated[att["rtl_sha256"]] = n
        run.event("simulating", attempt=n)
        verdict = simulate(rtl_path, adir / "sim", a.sandbox, blk)
        check_suite(locked, f"after attempt {n}", blk)
        if verdict.get("suite_sha256") not in (None, locked):
            raise SystemExit(f"ABORT: simulator ran a different suite ({verdict['suite_sha256']}); "
                             "rebuild the sandbox image with `make image`")
        att["status"] = verdict["status"]
        att["measured"] = {
            "label": "measured", "status": verdict["status"],
            "passed": verdict.get("passed", 0), "total": verdict.get("total", 0),
            "failed": [{"name": t["name"], "message": t["message"]} for t in verdict.get("tests", []) if not t["passed"]],
            "simulator": verdict.get("simulator"), "sim_seconds": verdict.get("seconds"),
            "suite_sha256": verdict.get("suite_sha256"), "sandbox": verdict.get("sandbox"),
        }
        if verdict.get("error"):
            att["measured"]["error"] = verdict["error"][-1500:]
        run.event("verdict", attempt=n, status=verdict["status"],
                  passed=verdict.get("passed", 0), total=verdict.get("total", 0))
        last_rtl = rtl
        if verdict["status"] == "pass" and not blk:
            # G3: same design at other parameter sets. Never shown to the model;
            # a visible pass that fails here is an escape, not a pass.
            run.event("sweeping", attempt=n)
            sw = sweep(rtl_path, adir / "sweep", a.sandbox)
            check_sweep(sweep_locked, f"after attempt {n}")
            if sw.get("sweep_sha256") not in (None, sweep_locked):
                raise SystemExit(f"ABORT: sandbox ran a different sweep ({sw['sweep_sha256']}); "
                                 "rebuild the sandbox image with `make image`")
            att["sweep"] = {"label": "measured", "status": sw["status"], "seconds": sw.get("seconds"),
                            "sets": [{"params": s["params"], "status": s["status"], "passed": s["passed"],
                                      "total": s["total"]} for s in sw.get("sets", [])]}
            if sw.get("error"):
                att["sweep"]["error"] = sw["error"][-500:]
            run.event("sweep", attempt=n, status=sw["status"])
            if sw["status"] != "pass":
                att["status"] = "escaped"
                final = "escaped"
        att["finished_s"] = round(time.time() - run.t0, 2)
        record["attempts"].append(att)
        if verdict["status"] == "pass":
            final = "pass" if final != "escaped" else final
            break

    if final == "fail":  # repairs exhausted: hand over to a person with what was measured
        final = "needs_engineer"
        diag = next((x["ai_interpretation"]["diagnosis"] for x in reversed(record["attempts"])
                     if "ai_interpretation" in x), None)
        record["handoff"] = {
            "failing_tests": [t["name"] for t in (verdict or {}).get("tests", []) if not t["passed"]],
            "last_rejection": rejection,
            "last_simulated_attempt": max(simulated.values()) if simulated else None,
            "last_diagnosis": {"label": AI_LABEL, "text": diag} if diag else None,
        }
    check_suite(locked, "after run", blk)
    if not blk:
        check_sweep(sweep_locked, "after run")
    atts = record["attempts"]
    record.update(
        finished=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        status=final,
        attempts_total=len(atts),
        attempts_to_green=len(atts) if final == "pass" else None,
        first_pass=bool(atts) and atts[0].get("status") == "pass" and atts[0].get("source") == "model",
        time_to_green_s=atts[-1]["finished_s"] if final == "pass" else None,
        wall_seconds=round(time.time() - run.t0, 2),
        cost_usd=round(sum(x.get("cost_usd", 0) for x in atts), 6),
        tokens={"in": sum(x.get("tokens_in", 0) for x in atts), "out": sum(x.get("tokens_out", 0) for x in atts)},
    )
    if source:
        record["replay_check"] = replay_check(source, atts)
    (run.dir / "run.json").write_text(json.dumps(record, indent=2))
    if approved_breakdown:  # measured: did the final RTL follow the approved breakdown?
        from agent import breakdown as bd
        chk = bd.check_run(run.dir)
        if chk:
            record["breakdown_check"] = {k: chk[k] for k in ("attempt", "present", "total", "width_match",
                                                             "width_differs", "missing", "reqs_without_element")}
            (run.dir / "run.json").write_text(json.dumps(record, indent=2))
    run.event("run_finished", status=final, attempts=len(atts), cost_usd=record["cost_usd"])
    return 0 if final == "pass" else 1


def replay_check(source: str, atts: list) -> dict:
    """Does the replay reproduce the source run attempt for attempt?"""
    src = json.loads((RUNS / source / "run.json").read_text())["attempts"]
    rows = []
    for i in range(max(len(src), len(atts))):
        s = src[i] if i < len(src) else {}
        r = atts[i] if i < len(atts) else {}
        rows.append({"n": i + 1, "status": [s.get("status"), r.get("status")],
                     "rtl_match": s.get("rtl_sha256") == r.get("rtl_sha256"),
                     "request_match": r.get("request_matches")})
    same = all(x["status"][0] == x["status"][1] and x["rtl_match"] for x in rows)
    return {"reproduced": same, "attempts": rows}


if __name__ == "__main__":
    sys.exit(main())
