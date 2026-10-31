"""Run the parameter sweep (G3) against an RTL file and write sweep.json.

The frozen suite (verify/run_suite.py) checks the default parameters only; this
checks that the design honours WIDTH / DEPTH / AF_THRESH / CW elsewhere,
including a DEPTH that is not a power of two. Its output is never put in a
model prompt.

usage: python verify/run_sweep.py <rtl.v> [--out runs/<id>/sweep]
"""
import argparse
import hashlib
import json
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SWEEP_DIR = ROOT / "tests_sweep"
# (WIDTH, DEPTH, AF_THRESH, CW). CW must hold 0..DEPTH. The default set is the
# frozen suite's job, so it is not repeated here.
SETS = [(8, 12, 9, 4), (1, 2, 1, 2), (32, 32, 32, 6)]
PINNED = [SWEEP_DIR / "test_sweep.py", ROOT / "tests" / "golden_model.py", ROOT / "verify" / "run_sweep.py"]


def sweep_hash():
    h = hashlib.sha256()
    for f in PINNED:
        h.update(f.relative_to(ROOT).as_posix().encode() + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()


def run(rtl: Path, out: Path) -> dict:
    from cocotb_tools.runner import get_runner

    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    verdict = {"rtl_sha256": hashlib.sha256(rtl.read_bytes()).hexdigest(), "sweep_sha256": sweep_hash(),
               "sets": []}
    for width, depth, af, cw in SETS:
        name = f"w{width}_d{depth}_af{af}"
        d = out / name
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
        entry = {"params": {"WIDTH": width, "DEPTH": depth, "AF_THRESH": af, "CW": cw}, "tests": []}
        runner = get_runner("icarus")
        try:
            runner.build(sources=[rtl], hdl_toplevel="sync_fifo", build_dir=d / "build", always=True,
                         parameters={"WIDTH": width, "DEPTH": depth, "AF_THRESH": af, "CW": cw},
                         timescale=("1ns", "1ps"), log_file=d / "build.log")
            runner.test(hdl_toplevel="sync_fifo", test_module="test_sweep", test_dir=SWEEP_DIR,
                        build_dir=d / "build", results_xml=d / "results.xml", log_file=d / "sim.log",
                        extra_env={"PYTHONPATH": f"{SWEEP_DIR}:{ROOT / 'tests'}",
                                   "SWEEP_WIDTH": str(width), "SWEEP_DEPTH": str(depth), "SWEEP_AF": str(af)})
        except Exception as e:  # compile or simulator failure at this parameter set is a measured result
            entry["error"] = str(e)[-1000:]
        if (d / "results.xml").exists():
            for tc in ET.parse(d / "results.xml").getroot().iter("testcase"):
                fail = tc.find("failure")
                entry["tests"].append({"name": tc.get("name"), "passed": fail is None,
                                       "message": (fail.get("message") or "")[:500] if fail is not None else ""})
        entry["passed"] = sum(t["passed"] for t in entry["tests"])
        entry["total"] = len(entry["tests"])
        entry["status"] = "pass" if entry["total"] == 2 and entry["passed"] == 2 else "fail"
        verdict["sets"].append(entry)
    verdict["status"] = "pass" if all(s["status"] == "pass" for s in verdict["sets"]) else "fail"
    verdict["seconds"] = round(time.time() - t0, 2)
    (out / "sweep.json").write_text(json.dumps(verdict, indent=2))
    return verdict


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("rtl", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "runs" / "sweep")
    a = ap.parse_args()
    v = run(a.rtl.resolve(), a.out.resolve())
    print(json.dumps({"status": v["status"], "sets": [(s["params"], s["status"], s["passed"], s["total"])
                                                       for s in v["sets"]]}, indent=1))
    sys.exit(0 if v["status"] == "pass" else 1)
