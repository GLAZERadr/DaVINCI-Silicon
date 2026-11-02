"""Formal checks of sync_fifo with SymbiYosys (S5 bounded, S9 unbounded).

The properties live in formal/sync_fifo_props.sv (hand-written, frozen, pinned
in formal/props.sha256, never put in a model prompt). They use only the ports,
so they apply to any RTL with the right interface. Every property is checked
on its own so it gets its own result:

  bmc     BMC to depth 20: "holds for 20 cycles" or "failed" (counterexample stored)
  prove   k-induction (smtbmc, depth 20); if induction does not close, abc pdr.
          Result "proved (unbounded)" only when an engine returns PASS in prove
          mode; otherwise "bounded only (depth 20)"; "failed" with a stored
          counterexample when the base case fails.

A bounded result is never reported as a proof. All results are measured tool
output (sby status + logs).

usage: python3 verify/formal.py <rtl.v> --out <dir>    # inside the formal sandbox
       python verify/formal.py --run runs/<id>         # host: run's final RTL, in Docker
       python verify/formal.py --reference             # host: reference RTL, in Docker
       python verify/formal.py --mutants               # host: each mutant of the reference, in Docker
Stdlib only: the in-sandbox mode runs in the formal image (no cocotb there).
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FORMAL = ROOT / "formal"
PROPS = FORMAL / "sync_fifo_props.sv"
PIN = FORMAL / "props.sha256"
IMAGE = "davinci-sim:formal"
DEPTH = 20
STEP_TIMEOUT_S = 120
SOLVER = "smtbmc z3"
LABEL = "measured (SymbiYosys)"
PROPERTIES = [
    ("P1_count_le_depth", "count <= DEPTH"),
    ("P2_full_iff_count", "full == (count == DEPTH)"),
    ("P3_empty_iff_count", "empty == (count == 0)"),
    ("P4_never_full_and_empty", "never full && empty"),
    ("P5_overflow_cause", "overflow only after a write while full with no read (and no reset) on the previous cycle"),
    ("P6_count_step", "count changes by at most 1 per cycle (outside reset)"),
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def props_hash() -> str:
    return sha(PROPS)


def script_hash() -> str:
    return sha(Path(__file__).resolve())


# ---------------------------------------------------------------- in-sandbox

def tool_versions() -> dict:
    def first(cmd):
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            return (p.stdout or p.stderr).strip().splitlines()[0]
        except Exception as e:  # recorded, not fatal
            return f"unknown ({e.__class__.__name__})"
    return {"yosys": first(["yosys", "-V"]), "sby": first(["sby", "--version"]),
            "z3": first(["z3", "--version"]), "abc": "yosys-abc (bundled with yosys)"}


def sby_file(bit: int, mode: str, engine: str) -> str:
    return f"""[options]
mode {mode}
depth {DEPTH}

[engines]
{engine}

[script]
read_verilog dut.v
read -formal sync_fifo_props.sv
chparam -set EN {1 << bit} fifo_formal
prep -top fifo_formal

[files]
dut.v
sync_fifo_props.sv
"""


def run_sby(work: Path, name: str, bit: int, mode: str, engine: str, logs: Path, cex: Path) -> dict:
    (work / f"{name}.sby").write_text(sby_file(bit, mode, engine))
    t0 = time.time()
    try:
        p = subprocess.run(["sby", "-f", f"{name}.sby"], cwd=work, capture_output=True, text=True,
                           timeout=STEP_TIMEOUT_S)
        log = p.stdout + p.stderr
    except subprocess.TimeoutExpired as e:
        log = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        log += f"\n[davinci] sby exceeded {STEP_TIMEOUT_S} s\n"
    (logs / f"{name}.log").write_text(log)
    status_file = work / name / "status"
    status = status_file.read_text().split()[0] if status_file.exists() else "ERROR"
    if f"exceeded {STEP_TIMEOUT_S} s" in log:
        status = "TIMEOUT"
    res = {"engine": engine, "sby_status": status, "seconds": round(time.time() - t0, 2), "log": f"logs/{name}.log"}
    if status == "FAIL":
        steps = re.findall(r"(?:Checking assertions in step|failed assertion .* step) (\d+)", log)
        if steps:
            res["cex_step"] = int(steps[-1])
        tr = work / name / "engine_0" / "trace.vcd"
        if tr.exists():
            shutil.copy(tr, cex / f"{name}.vcd")
            res["counterexample"] = f"cex/{name}.vcd"
    return res


def check(rtl: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    logs, cex = out / "logs", out / "cex"
    logs.mkdir(exist_ok=True)
    cex.mkdir(exist_ok=True)
    report = {"label": LABEL, "rtl_sha256": sha(rtl), "props_sha256": props_hash(),
              "formal_sha256": script_hash(), "depth": DEPTH, "tools": tool_versions(),
              "assumptions": ["reset asserted in the first cycle", "all other inputs free",
                              "default parameters WIDTH 8, DEPTH 16, AF_THRESH 14"]}
    t0 = time.time()
    with tempfile.TemporaryDirectory(dir="/tmp" if Path("/tmp").exists() else None) as td:
        work = Path(td)
        shutil.copy(rtl, work / "dut.v")
        shutil.copy(PROPS, work / "sync_fifo_props.sv")
        props = []
        for bit, (pid, text) in enumerate(PROPERTIES):
            bmc = run_sby(work, f"{pid}_bmc", bit, "bmc", SOLVER, logs, cex)
            entry = {"id": pid, "text": text, "bmc": bmc, "prove": []}
            if bmc["sby_status"] == "PASS":
                entry["bounded"] = f"holds for {DEPTH} cycles"
                kind = run_sby(work, f"{pid}_kind", bit, "prove", SOLVER, logs, cex)
                entry["prove"].append(kind)
                if kind["sby_status"] != "PASS" and kind["sby_status"] != "FAIL":
                    entry["prove"].append(run_sby(work, f"{pid}_pdr", bit, "prove", "abc pdr", logs, cex))
                last = entry["prove"][-1]
                if last["sby_status"] == "PASS":
                    entry["result"] = "proved"
                    entry["result_text"] = f"proved (unbounded, {last['engine']})"
                elif last["sby_status"] == "FAIL":  # cannot happen after a passing BMC unless deeper; kept honest
                    entry["result"] = "failed"
                    entry["result_text"] = "failed (counterexample stored)"
                else:
                    entry["result"] = "bounded"
                    entry["result_text"] = f"bounded only (depth {DEPTH})"
            elif bmc["sby_status"] == "FAIL":
                entry["bounded"] = "failed"
                entry["result"] = "failed"
                entry["result_text"] = "failed (counterexample stored)"
            else:
                entry["bounded"] = "error"
                entry["result"] = "error"
                entry["result_text"] = f"no result (sby {bmc['sby_status']})"
            props.append(entry)
            print(f"{pid:26} bmc {bmc['sby_status']:7} -> {entry['result_text']}", flush=True)
    report["properties"] = props
    report["seconds"] = round(time.time() - t0, 2)
    report["bmc_holding"] = sum(p["bounded"] == f"holds for {DEPTH} cycles" for p in props)
    report["proved"] = sum(p["result"] == "proved" for p in props)
    report["failed"] = [p["id"] for p in props if p["result"] == "failed"]
    report["errors"] = [p["id"] for p in props if p["result"] == "error"]
    report["summary"] = (f"Bounded formal: {report['bmc_holding']} of {len(props)} properties hold for {DEPTH} cycles; "
                         f"{report['proved']} proved (unbounded)")
    (out / "formal.json").write_text(json.dumps(report, indent=2))
    return report


# ---------------------------------------------------------------- host side

def check_pin():
    want = PIN.read_text().split()[0]
    if props_hash() != want:
        raise SystemExit(f"ABORT: formal/sync_fifo_props.sv does not match formal/props.sha256 ({want[:12]}...)")


def in_docker(rtl: Path, out: Path) -> dict:
    sys.path.insert(0, str(ROOT))
    from agent.pipeline import DOCKER_LIMITS

    check_pin()
    out.mkdir(parents=True, exist_ok=True)
    for old in ("logs", "cex"):  # results of an earlier check of this output dir
        shutil.rmtree(out / old, ignore_errors=True)
    (out / "formal.json").unlink(missing_ok=True)
    cmd = ["docker", "run", "--rm", *DOCKER_LIMITS,
           "-v", f"{rtl.resolve()}:/work/in/dut.v:ro", "-v", f"{out.resolve()}:/work/out", IMAGE]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        raise SystemExit("formal sandbox exceeded 900 s")
    f = out / "formal.json"
    if not f.exists():
        raise SystemExit(f"sandbox wrote no formal.json (exit {p.returncode}): {(p.stdout + p.stderr)[-1500:]}")
    report = json.loads(f.read_text())
    if report.get("formal_sha256") != script_hash() or report.get("props_sha256") != props_hash():
        raise SystemExit("ABORT: the sandbox ran a different verify/formal.py or property file; "
                         "rebuild with `make formal-image`")
    report["sandbox"] = {"backend": "docker", "image": IMAGE, "limits": DOCKER_LIMITS}
    f.write_text(json.dumps(report, indent=2))
    sys.stdout.write(p.stdout)
    return report


def final_rtl(run: Path) -> tuple[int, Path]:
    r = json.loads((run / "run.json").read_text())
    for att in reversed(r["attempts"]):
        f = run / f"attempt_{att['n']}" / "sync_fifo.v"
        if f.exists() and (att.get("measured") or {}).get("status") in ("pass", "fail"):
            return att["n"], f
    raise SystemExit(f"{run}: no simulated attempt with RTL")


def mutants_summary(ref_rtl: Path, base: Path) -> dict:
    src = ref_rtl.read_text()
    mutants = json.loads((ROOT / "verify" / "mutants.json").read_text())
    rows = []
    for m in mutants:
        if src.count(m["find"]) != 1:
            rows.append({"id": m["id"], "req": m["req"], "desc": m["desc"], "result": "not_applicable"})
            continue
        d = base / m["id"]
        d.mkdir(parents=True, exist_ok=True)
        rtl = d / "sync_fifo.v"
        rtl.write_text(src.replace(m["find"], m["replace"]))
        print(f"--- {m['id']} {m['desc']}", flush=True)
        rep = in_docker(rtl, d / "formal")
        failed = rep["failed"]
        rows.append({"id": m["id"], "req": m["req"], "desc": m["desc"],
                     "result": "caught" if failed else "not caught",
                     "failed_properties": failed,
                     "counterexamples": {p["id"]: f"mutants/{m['id']}/formal/" + p["bmc"]["counterexample"]
                                         for p in rep["properties"] if p["bmc"].get("counterexample")},
                     "cex_steps": {p["id"]: p["bmc"].get("cex_step") for p in rep["properties"] if p["result"] == "failed"},
                     "errors": rep["errors"]})
    applied = [r for r in rows if r["result"] != "not_applicable"]
    return {"label": LABEL + ", hand-written mutants from verify/mutants.json",
            "mutants_sha256": sha(ROOT / "verify" / "mutants.json"), "props_sha256": props_hash(),
            "caught": sum(r["result"] == "caught" for r in applied), "injected": len(applied),
            "caught_ids": [r["id"] for r in applied if r["result"] == "caught"], "mutants": rows}


def merge_mutants(ref_out: Path):
    """Put the mutant summary into the reference formal.json (the board reads one file)."""
    mf, rf = ref_out / "mutants.json", ref_out / "formal.json"
    if mf.exists() and rf.exists():
        rep = json.loads(rf.read_text())
        rep["mutants"] = json.loads(mf.read_text())
        rf.write_text(json.dumps(rep, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rtl", type=Path, nargs="?")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--run", type=Path, help="stored run: its final RTL, inside Docker")
    ap.add_argument("--reference", action="store_true", help="reference RTL, inside Docker")
    ap.add_argument("--mutants", action="store_true", help="each mutant of the reference RTL, inside Docker")
    a = ap.parse_args()
    ref_out = ROOT / "runs" / "reference" / "formal"
    if a.run:
        n, rtl = final_rtl(a.run)
        rep = in_docker(rtl, a.run / "formal")
        rep["attempt"] = n
        (a.run / "formal" / "formal.json").write_text(json.dumps(rep, indent=2))
    elif a.reference:
        rep = in_docker(ROOT / "rtl" / "sync_fifo.v", ref_out)
        merge_mutants(ref_out)
    elif a.mutants:
        ref_out.mkdir(parents=True, exist_ok=True)
        s = mutants_summary(ROOT / "rtl" / "sync_fifo.v", ref_out / "mutants")
        (ref_out / "mutants.json").write_text(json.dumps(s, indent=2))
        merge_mutants(ref_out)
        print(f"formal caught {s['caught']}/{s['injected']} mutants: {', '.join(s['caught_ids']) or 'none'}")
    elif a.rtl:
        rep = check(a.rtl, a.out or Path("formal_out"))
        print(rep["summary"])
    else:
        ap.error("give an RTL file, --run, --reference or --mutants")


if __name__ == "__main__":
    main()
