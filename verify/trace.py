"""Per-cycle simulation trace for the waveform and FIFO views.

Runs the frozen suite with waveform dumping (the same build as
verify/coverage.py; the frozen files are not touched), then cuts the VCD into
one trace per test using the start/stop times cocotb records in results.xml.
For every test cycle it keeps the inputs as the DUT saw them before the rising
edge, the outputs just after it (what the test compares), the golden model's
expected outputs for the same inputs, and the RTL's own wr_ptr/rd_ptr when the
design has signals with those names. Cycle numbers match the test messages
("cycle 19"). Everything here is measured simulator output except `exp`, which
is the golden model. Never put in a model prompt.

usage: python verify/trace.py <rtl.v> --out <dir>     # simulate + trace (inside the sandbox for model RTL)
       python verify/trace.py --run runs/<id>         # host: every simulated attempt of a run, in Docker
       python verify/trace.py --reference             # host: reference RTL, local (hand-written)
"""
import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run_suite import ROOT, TESTS, suite_hash, tool_version  # noqa: E402

sys.path.insert(0, str(TESTS))
from golden_model import FifoModel  # noqa: E402

_spec = importlib.util.spec_from_file_location("davinci_coverage", HERE / "coverage.py")
cov = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cov)

P = json.loads((ROOT / "spec" / "interface.json").read_text())["params"]
INPUTS = ["rst", "wr_en", "din", "rd_en"]
OUTPUTS = ["dout", "count", "full", "empty", "almost_full", "overflow", "underflow"]
POINTERS = ["wr_ptr", "rd_ptr"]
WANTED = {"clk", *INPUTS, *OUTPUTS, *POINTERS}
LONG_TEST = 120   # cycles; longer tests keep the start and the window around the first mismatch
WINDOW = 40


def trace_hash() -> str:
    return hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest()


def parse_vcd(vcd: Path):
    """Yield (time_ps, pre, post, clk_rose, clk_fell) per timestamp. Values are
    ints, None while unknown (x/z)."""
    ids, scopes = {}, []
    vals = {s: None for s in WANTED}
    t, changes = None, {}

    def value(bits: str):
        return None if any(c in "xzXZ" for c in bits) else int(bits, 2)

    def flush():
        pre = dict(vals)
        vals.update(changes)
        return t, pre, dict(vals), pre["clk"] == 0 and vals["clk"] == 1, pre["clk"] == 1 and vals["clk"] == 0

    with vcd.open() as f:
        for line in f:
            tok = line.split()
            if not tok:
                continue
            head = tok[0]
            if head == "$scope":
                scopes.append(tok[2])
            elif head == "$upscope":
                scopes.pop()
            elif head == "$var":
                if scopes[-1:] == ["sync_fifo"] and scopes.count("sync_fifo") == 1 and tok[4] in WANTED:
                    ids.setdefault(tok[3], tok[4])
            elif head.startswith("#"):
                if t is not None:
                    yield flush()
                t, changes = int(head[1:]), {}
            elif head[0] in "bB" and len(tok) == 2 and tok[1] in ids:
                changes[ids[tok[1]]] = value(head[1:])
            elif head[0] in "01xzXZ" and len(tok) == 1 and head[1:] in ids:
                changes[ids[head[1:]]] = value(head[0])
    if t is not None:
        yield flush()


def test_windows(results: Path) -> list[dict]:
    out = []
    for tc in ET.parse(results).getroot().iter("testcase"):
        props = {p.get("name"): p.get("value") for p in tc.iter("property")}
        fail = tc.find("failure")
        out.append({"name": tc.get("name"), "start_ps": float(props["sim_time_start"]) * 1000,
                    "stop_ps": float(props["sim_time_stop"]) * 1000, "passed": fail is None,
                    "message": (fail.get("message") or "")[:300] if fail is not None else ""})
    return out


def build(vcd: Path, results: Path) -> list[dict]:
    tests = test_windows(results)
    stamps = list(parse_vcd(vcd))
    traces = []
    for w in tests:
        inside = [s for s in stamps if w["start_ps"] <= s[0] <= w["stop_ps"]]
        fell = next((i for i, s in enumerate(inside) if s[4]), None)
        edges = [s for s in inside[fell + 1:] if s[3]] if fell is not None else []
        model = FifoModel(P["WIDTH"], P["DEPTH"], P["AF_THRESH"])
        cycles = []
        for k, (t, pre, post, _, _) in enumerate(edges, start=1):
            ins = {s: pre[s] for s in INPUTS}
            exp = model.step(ins["wr_en"] or 0, ins["din"] or 0, ins["rd_en"] or 0, ins["rst"] or 0)
            outs = {s: post[s] for s in OUTPUTS}
            c = {"k": k, "t_ns": t / 1000, "in": ins, "out": outs, "exp": exp,
                 "mismatch": [f for f in OUTPUTS if outs[f] != exp[f]]}
            ptr = {s: post[s] for s in POINTERS if post[s] is not None}
            if ptr:
                c["ptr"] = ptr
            cycles.append(c)
        first_bad = next((c["k"] for c in cycles if c["mismatch"]), None)
        kept, truncated = cycles, False
        if len(cycles) > LONG_TEST:
            keep = set(range(1, WINDOW + 1))
            if first_bad:
                keep |= set(range(max(1, first_bad - WINDOW // 2), first_bad + WINDOW // 2))
            kept, truncated = [c for c in cycles if c["k"] in keep], True
        traces.append({"name": w["name"], "passed": w["passed"], "message": w["message"],
                       "cycles_total": len(cycles), "first_mismatch": first_bad,
                       "truncated": truncated, "cycles": kept})
    return traces


def run(rtl: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    report = {"label": "measured (exp = golden model)", "rtl_sha256": hashlib.sha256(rtl.read_bytes()).hexdigest(),
              "suite_sha256": suite_hash(), "trace_sha256": trace_hash(), "simulator": tool_version(),
              "params": P, "inputs": INPUTS, "outputs": OUTPUTS}
    try:
        vcd = cov.simulate(rtl, out)
        report |= {"status": "ok", "tests": build(vcd, out / "results.xml")}
        vcd.unlink()
    except Exception as e:  # a design that does not simulate gets no trace, recorded as such
        report |= {"status": "sim_error", "error": str(e)[-1500:], "tests": []}
    report["seconds"] = round(time.time() - t0, 2)
    (out / "trace.json").write_text(json.dumps(report, separators=(",", ":")))
    return report


def in_docker(rtl: Path, out: Path) -> dict:
    sys.path.insert(0, str(ROOT))
    from agent.pipeline import DOCKER_LIMITS, SANDBOX_IMAGE, SIM_TIMEOUT_S

    out.mkdir(parents=True, exist_ok=True)
    cmd = ["docker", "run", "--rm", *DOCKER_LIMITS, "--entrypoint", "timeout",
           "-v", f"{rtl.resolve()}:/work/in/dut.v:ro", "-v", f"{out.resolve()}:/work/out",
           SANDBOX_IMAGE, "120", "python", "verify/trace.py", "/work/in/dut.v", "--out", "/work/out"]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=SIM_TIMEOUT_S)
    f = out / "trace.json"
    if not f.exists():
        raise SystemExit(f"sandbox wrote no trace.json (exit {p.returncode}): {p.stderr[-1000:]}")
    report = json.loads(f.read_text())
    if report.get("trace_sha256") != trace_hash():
        raise SystemExit("ABORT: the sandbox ran a different verify/trace.py; rebuild with `make image`")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rtl", type=Path, nargs="?")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--run", type=Path, help="stored run: trace every simulated attempt inside Docker")
    ap.add_argument("--reference", action="store_true", help="reference RTL, locally")
    a = ap.parse_args()
    if a.run:
        r = json.loads((a.run / "run.json").read_text())
        done = []
        for att in r["attempts"]:
            if (att.get("measured") or {}).get("status") in ("pass", "fail"):
                rep = in_docker(a.run / f"attempt_{att['n']}" / "sync_fifo.v", a.run / f"attempt_{att['n']}" / "trace")
                done.append(f"attempt {att['n']}: {rep['status']}, {len(rep['tests'])} tests")
        print("\n".join(done) or "no simulated attempts")
    elif a.reference:
        rep = run(ROOT / "rtl" / "sync_fifo.v", ROOT / "runs" / "reference" / "trace")
        print(rep["status"], len(rep["tests"]), "tests")
    elif a.rtl:
        rep = run(a.rtl, a.out or ROOT / "runs" / "trace")
        print(rep["status"], len(rep["tests"]), "tests")
    else:
        ap.error("give an RTL file, --run or --reference")


if __name__ == "__main__":
    main()
