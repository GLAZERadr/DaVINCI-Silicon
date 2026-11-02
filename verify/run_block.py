"""Run a registered block's frozen cocotb suite against an RTL file and write a
JSON verdict. The same shape as verify/run_suite.py, for blocks other than the
sync FIFO (whose runner, verify/run_suite.py, is frozen and stays as it is).

usage: python verify/run_block.py <block> <rtl.v> [--out runs/<id>] [--candidate]

The block registry is blocks/<name>/block.json. The suite hash covers the
files the block lists under "frozen" (tests, golden model, this runner, the
mutant set) and is pinned in the block's own suite_lock file.

--candidate runs the block's candidate tests instead (not frozen, not pinned):
tests that still have to earn trust by agreeing with the reference RTL.
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
BLOCKS = ROOT / "blocks"


def names() -> list[str]:
    return sorted(p.parent.name for p in BLOCKS.glob("*/block.json"))


def load(name: str) -> dict:
    f = BLOCKS / name / "block.json"
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name or "") or not f.exists():
        raise SystemExit(f"unknown block {name!r}; registered: {names()}")
    return json.loads(f.read_text())


def suite_hash(block: dict) -> str:
    h = hashlib.sha256()
    for rel in block["frozen"]:
        f = ROOT / rel
        h.update(f.relative_to(ROOT).as_posix().encode() + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()


def _tests_in(path: Path) -> list[str]:
    return re.findall(r"@cocotb\.test\(\)\s*async def (\w+)", path.read_text())


def all_tests(block: dict) -> list[str]:
    return _tests_in(ROOT / block["tests_dir"] / f"{block['test_module']}.py")


def tool_version():
    out = subprocess.run(["iverilog", "-V"], capture_output=True, text=True).stdout
    return out.splitlines()[0] if out else "unknown"


def run(block: dict, rtl: Path, out: Path, candidate: bool = False, extra_env: dict | None = None,
        test_module: str | None = None, test_dir: Path | None = None) -> dict:
    from cocotb_tools.runner import get_runner

    if block.get("runner") != "verify/run_block.py":
        raise SystemExit(f"block {block['name']} has its own runner: {block.get('runner')}")
    if candidate:
        test_dir, test_module = ROOT / block["candidate_tests"]["dir"], block["candidate_tests"]["module"]
    test_dir = test_dir or ROOT / block["tests_dir"]
    test_module = test_module or block["test_module"]
    out.mkdir(parents=True, exist_ok=True)
    build = out / "sim_build"
    shutil.rmtree(build, ignore_errors=True)
    t0 = time.time()
    verdict = {
        "block": block["name"],
        "rtl": str(rtl),
        "rtl_sha256": hashlib.sha256(rtl.read_bytes()).hexdigest(),
        "suite_sha256": suite_hash(block),
        "simulator": tool_version(),
        "tests": [],
    }
    if candidate or test_module != block["test_module"]:
        # Not the frozen suite: never let this verdict pass for the pinned one.
        verdict["suite_sha256"] = None
        verdict["candidate"] = {"module": test_module, "dir": str(test_dir.relative_to(ROOT)),
                                "sha256": hashlib.sha256((test_dir / f"{test_module}.py").read_bytes()).hexdigest(),
                                "label": "candidate tests: not frozen, not pinned"}
    runner = get_runner("icarus")
    try:
        runner.build(sources=[rtl], hdl_toplevel=block["top"], build_dir=build, always=True,
                     timescale=("1ns", "1ps"), log_file=out / "build.log")
    except Exception as e:  # compile error is a measured result, not a crash
        verdict.update(status="compile_error", error=str(e)[-2000:],
                       log=(out / "build.log").read_text()[-4000:] if (out / "build.log").exists() else "")
        verdict.update(passed=0, total=0, seconds=round(time.time() - t0, 2))
        (out / "verdict.json").write_text(json.dumps(verdict, indent=2))
        return verdict
    results = out / "results.xml"
    env = {"PYTHONPATH": str(test_dir), **(extra_env or {})}
    try:
        runner.test(hdl_toplevel=block["top"], test_module=test_module, test_dir=test_dir, build_dir=build,
                    results_xml=results, log_file=out / "sim.log", extra_env=env)
    except Exception as e:
        verdict.update(status="sim_error", error=str(e)[-2000:])
    if results.exists():
        for tc in ET.parse(results).getroot().iter("testcase"):
            fail = tc.find("failure")
            verdict["tests"].append({"name": tc.get("name"), "passed": fail is None,
                                     "message": (fail.get("message") or "")[:500] if fail is not None else ""})
    passed = sum(t["passed"] for t in verdict["tests"])
    verdict["passed"], verdict["total"] = passed, len(verdict["tests"])
    verdict.setdefault("status", "pass" if verdict["total"] and passed == verdict["total"] else "fail")
    verdict["seconds"] = round(time.time() - t0, 2)
    (out / "verdict.json").write_text(json.dumps(verdict, indent=2))
    return verdict


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("block")
    ap.add_argument("rtl", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "runs" / "manual")
    ap.add_argument("--candidate", action="store_true", help="run the block's candidate (unfrozen) tests")
    a = ap.parse_args()
    v = run(load(a.block), a.rtl.resolve(), a.out.resolve(), candidate=a.candidate)
    print(json.dumps({k: v[k] for k in v if k != "tests"} | {"failed": [t for t in v["tests"] if not t["passed"]]},
                     indent=2))
    sys.exit(0 if v["status"] == "pass" else 1)
