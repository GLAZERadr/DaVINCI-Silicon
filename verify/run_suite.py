"""Run the frozen cocotb suite against an RTL file and print a JSON verdict.

usage: python verify/run_suite.py <rtl.v> [--out runs/<id>] [--drop test_a,test_b]

--drop runs a reduced suite (used only by the weak-test demo in mutate.py).
The frozen files are never edited; the verdict lists what was left out.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
FROZEN = [TESTS / "test_sync_fifo.py", TESTS / "golden_model.py"]


def suite_hash():
    h = hashlib.sha256()
    for f in FROZEN:
        h.update(f.read_bytes())
    return h.hexdigest()


def all_tests():
    src = (TESTS / "test_sync_fifo.py").read_text()
    return re.findall(r"@cocotb\.test\(\)\s*async def (\w+)", src)


def tool_version():
    out = subprocess.run(["iverilog", "-V"], capture_output=True, text=True).stdout
    return out.splitlines()[0] if out else "unknown"


def run(rtl: Path, out: Path, timeout_s: int = 120, drop=()) -> dict:
    from cocotb_tools.runner import get_runner

    out.mkdir(parents=True, exist_ok=True)
    build = out / "sim_build"
    shutil.rmtree(build, ignore_errors=True)
    t0 = time.time()
    verdict = {
        "rtl": str(rtl),
        "rtl_sha256": hashlib.sha256(rtl.read_bytes()).hexdigest(),
        "suite_sha256": suite_hash(),
        "simulator": tool_version(),
        "tests": [],
    }
    drop = list(drop)
    unknown = set(drop) - set(all_tests())
    if unknown:
        raise ValueError(f"unknown tests to drop: {sorted(unknown)}")
    if drop:
        verdict["tests_dropped"] = drop
    runner = get_runner("icarus")
    try:
        runner.build(
            sources=[rtl],
            hdl_toplevel="sync_fifo",
            build_dir=build,
            always=True,
            timescale=("1ns", "1ps"),
            log_file=out / "build.log",
        )
    except Exception as e:  # compile error is a measured result, not a crash
        verdict.update(status="compile_error", error=str(e)[-2000:],
                       log=(out / "build.log").read_text()[-4000:] if (out / "build.log").exists() else "")
        verdict.update(passed=0, total=0, seconds=round(time.time() - t0, 2))
        (out / "verdict.json").write_text(json.dumps(verdict, indent=2))
        return verdict
    results = out / "results.xml"
    try:
        runner.test(
            hdl_toplevel="sync_fifo",
            test_module="test_sync_fifo",
            test_dir=TESTS,
            testcase=[t for t in all_tests() if t not in drop] if drop else None,
            build_dir=build,
            results_xml=results,
            log_file=out / "sim.log",
            extra_env={"PYTHONPATH": str(TESTS)},
        )
    except Exception as e:
        verdict.update(status="sim_error", error=str(e)[-2000:])
    if results.exists():
        for tc in ET.parse(results).getroot().iter("testcase"):
            fail = tc.find("failure")
            verdict["tests"].append({
                "name": tc.get("name"),
                "passed": fail is None,
                "message": (fail.get("message") or "")[:500] if fail is not None else "",
            })
    passed = sum(t["passed"] for t in verdict["tests"])
    verdict["passed"], verdict["total"] = passed, len(verdict["tests"])
    verdict.setdefault("status", "pass" if verdict["total"] and passed == verdict["total"] else "fail")
    verdict["seconds"] = round(time.time() - t0, 2)
    (out / "verdict.json").write_text(json.dumps(verdict, indent=2))
    return verdict


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("rtl", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "runs" / "manual")
    ap.add_argument("--drop", default="", help="comma-separated tests to leave out")
    a = ap.parse_args()
    v = run(a.rtl.resolve(), a.out.resolve(), drop=[t for t in a.drop.split(",") if t])
    print(json.dumps({k: v[k] for k in v if k != "tests"} | {"failed": [t for t in v["tests"] if not t["passed"]]}, indent=2))
    sys.exit(0 if v["status"] == "pass" else 1)
