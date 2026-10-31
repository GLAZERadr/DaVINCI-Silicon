"""Scenario coverage counters: how often the frozen suite drove the design into
each FIFO situation, counted from a waveform of the same frozen tests.

The frozen files are not touched: this builds its own simulation of
tests/test_sync_fifo.py with waveform dumping on, writes a VCD and counts
scenarios at every rising clock edge from the port values just before the
edge. Counts describe the stimulus as the design under test saw it (flags come
from the DUT's own outputs). Pinned in verify/coverage.sha256; never put in a
model prompt.

usage: python verify/coverage.py <rtl.v> --out <dir>      # simulate + count (inside the sandbox for model RTL)
       python verify/coverage.py --run runs/<id>          # host: final RTL of a stored run, in Docker
       python verify/coverage.py --reference              # host: reference RTL, local (hand-written)
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_suite import ROOT, TESTS, suite_hash, tool_version  # noqa: E402

INTERFACE = json.loads((ROOT / "spec" / "interface.json").read_text())
DEPTH = INTERFACE["params"]["DEPTH"]
SIGNALS = ["clk", "rst", "wr_en", "rd_en", "full", "empty", "almost_full", "overflow", "underflow"]
# Scenario → (description, test on the port values just before a rising edge).
SCENARIOS = {
    "reset": ("rst high at the edge", lambda v: v["rst"]),
    "full": ("full high", lambda v: not v["rst"] and v["full"]),
    "empty": ("empty high", lambda v: not v["rst"] and v["empty"]),
    "almost_full": ("almost_full high", lambda v: not v["rst"] and v["almost_full"]),
    "write_when_full": ("write, no read, while full (overflow case)",
                        lambda v: not v["rst"] and v["wr_en"] and not v["rd_en"] and v["full"]),
    "read_when_empty": ("read while empty (underflow case)",
                        lambda v: not v["rst"] and v["rd_en"] and v["empty"]),
    "rw_when_full": ("read and write together while full",
                     lambda v: not v["rst"] and v["wr_en"] and v["rd_en"] and v["full"]),
    "rw_when_empty": ("read and write together while empty",
                      lambda v: not v["rst"] and v["wr_en"] and v["rd_en"] and v["empty"]),
    "overflow_pulse": ("overflow output high", lambda v: v["overflow"]),
    "underflow_pulse": ("underflow output high", lambda v: v["underflow"]),
}
WRAP = ("write_pointer_wrap", f"accepted writes since reset reach a multiple of DEPTH={DEPTH}")


def coverage_hash() -> str:
    return hashlib.sha256((Path(__file__).resolve()).read_bytes()).hexdigest()


def simulate(rtl: Path, out: Path) -> Path:
    """Run the full frozen suite with a VCD dump. Returns the VCD path."""
    from cocotb_tools.runner import Icarus

    class VcdIcarus(Icarus):  # the stock runner dumps FST; VCD is plain text
        def _test_command(self):
            return [[("-vcd" if a == "-fst" else a) for a in cmd] for cmd in super()._test_command()]

    build = out / "sim_build"
    shutil.rmtree(build, ignore_errors=True)
    vcd = build / "waves.vcd"
    runner = VcdIcarus()
    runner.build(sources=[rtl], hdl_toplevel="sync_fifo", build_dir=build, always=True, waves=True,
                 timescale=("1ns", "1ps"), log_file=out / "build.log")
    runner.test(hdl_toplevel="sync_fifo", test_module="test_sync_fifo", test_dir=TESTS, build_dir=build,
                waves=True, plusargs=[f"+dumpfile_path={vcd}"], results_xml=out / "results.xml",
                log_file=out / "sim.log", extra_env={"PYTHONPATH": str(TESTS)})
    return vcd


def edges(vcd: Path):
    """Yield port values (bools, x/z as False) just before each rising clk edge."""
    ids, scopes = {}, []
    vals = {s: False for s in SIGNALS}
    pending, clk_rose = {}, False
    with vcd.open() as f:
        for line in f:
            tok = line.split()
            if not tok:
                continue
            if tok[0] == "$scope":
                scopes.append(tok[2])
            elif tok[0] == "$upscope":
                scopes.pop()
            elif tok[0] == "$var" and scopes[-1:] == ["sync_fifo"] and scopes.count("sync_fifo") == 1 \
                    and tok[4] in SIGNALS and tok[2] == "1":
                ids.setdefault(tok[3], tok[4])
            elif tok[0].startswith("#"):
                if clk_rose:
                    yield dict(vals)
                vals.update(pending)
                pending, clk_rose = {}, False
            elif tok[0][0] in "01xzXZ" and len(tok) == 1 and tok[0][1:] in ids:
                name = ids[tok[0][1:]]
                v = tok[0][0] == "1"
                pending[name] = v
                if name == "clk" and v and not vals["clk"]:
                    clk_rose = True
    if clk_rose:
        yield dict(vals)


def count(vcd: Path) -> dict:
    counts = {k: 0 for k in SCENARIOS} | {WRAP[0]: 0}
    writes, cycles = 0, 0
    for v in edges(vcd):
        cycles += 1
        for k, (_, hit) in SCENARIOS.items():
            counts[k] += bool(hit(v))
        if v["rst"]:
            writes = 0
        elif v["wr_en"] and (not v["full"] or v["rd_en"]):
            writes += 1
            counts[WRAP[0]] += writes % DEPTH == 0
    return {"cycles": cycles, "counts": counts}


def run(rtl: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    report = {"label": "measured", "rtl_sha256": hashlib.sha256(rtl.read_bytes()).hexdigest(),
              "suite_sha256": suite_hash(), "coverage_sha256": coverage_hash(), "simulator": tool_version(),
              "scenarios": {k: d for k, (d, _) in SCENARIOS.items()} | {WRAP[0]: WRAP[1]}}
    try:
        vcd = simulate(rtl, out)
        report |= count(vcd) | {"status": "ok"}
        report["zero"] = [k for k, n in report["counts"].items() if n == 0]
        vcd.unlink()  # can be large; the counts are the result
    except Exception as e:  # a design that does not simulate gets no counts, recorded as such
        report |= {"status": "sim_error", "error": str(e)[-1500:]}
    report["seconds"] = round(time.time() - t0, 2)
    (out / "coverage.json").write_text(json.dumps(report, indent=2))
    return report


def final_rtl(run_dir: Path) -> Path:
    """RTL of the last attempt that was simulated."""
    r = json.loads((run_dir / "run.json").read_text())
    for a in reversed(r["attempts"]):
        m = a.get("measured") or {}
        if m.get("status") in ("pass", "fail"):
            return run_dir / f"attempt_{a['n']}" / "sync_fifo.v"
    raise SystemExit(f"{run_dir}: no simulated attempt")


def in_docker(rtl: Path, out: Path) -> dict:
    sys.path.insert(0, str(ROOT))
    from agent.pipeline import DOCKER_LIMITS, SANDBOX_IMAGE, SIM_TIMEOUT_S

    out.mkdir(parents=True, exist_ok=True)
    cmd = ["docker", "run", "--rm", *DOCKER_LIMITS, "--entrypoint", "timeout",
           "-v", f"{rtl.resolve()}:/work/in/dut.v:ro", "-v", f"{out.resolve()}:/work/out",
           SANDBOX_IMAGE, "120", "python", "verify/coverage.py", "/work/in/dut.v", "--out", "/work/out"]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=SIM_TIMEOUT_S)
    f = out / "coverage.json"
    if not f.exists():
        raise SystemExit(f"sandbox wrote no coverage.json (exit {p.returncode}): {p.stderr[-1000:]}")
    report = json.loads(f.read_text())
    if report.get("coverage_sha256") != coverage_hash():
        raise SystemExit("ABORT: the sandbox ran a different verify/coverage.py; rebuild with `make image`")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rtl", type=Path, nargs="?")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--run", type=Path, help="stored run: count on its final RTL inside Docker")
    ap.add_argument("--reference", action="store_true", help="reference RTL, locally")
    a = ap.parse_args()
    pin = (ROOT / "verify" / "coverage.sha256").read_text().strip()
    if coverage_hash() != pin:
        raise SystemExit(f"ABORT: verify/coverage.py does not match verify/coverage.sha256 ({coverage_hash()})")
    if a.run:
        r = in_docker(final_rtl(a.run), a.run / "coverage")
    elif a.reference:
        r = run(ROOT / "rtl" / "sync_fifo.v", ROOT / "runs" / "reference" / "coverage")
    elif a.rtl:
        r = run(a.rtl, a.out or ROOT / "runs" / "coverage")
    else:
        ap.error("give an RTL file, --run or --reference")
    print(json.dumps({k: r.get(k) for k in ("status", "cycles", "counts", "zero")}, indent=1))
    sys.exit(0 if r.get("status") == "ok" else 1)


if __name__ == "__main__":
    main()
