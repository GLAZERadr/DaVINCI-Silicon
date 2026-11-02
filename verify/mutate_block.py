"""Mutation check for a registered block (blocks/<name>/block.json): inject the
block's hand-written bugs into its reference RTL and confirm the frozen suite
catches each one. Same output shape as verify/mutate.py (which stays the FIFO's).

usage: python verify/mutate_block.py <block> [--rtl path.v] [--out runs/blocks/<block>/mutation]
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_block import ROOT, load, run, suite_hash, tool_version  # noqa: E402

LABEL = "Suite mutation score vs reference RTL (hand-written mutants)"


def mutation_check(block: dict, src: str, out: Path) -> dict:
    mutants = json.loads((ROOT / block["mutants"]).read_text())
    report = []
    for m in mutants:
        if src.count(m["find"]) != 1:
            report.append({**m, "result": "not_applicable"})
            continue
        d = out / m["id"]
        d.mkdir(parents=True, exist_ok=True)
        mut = d / f"{block['top']}.v"
        mut.write_text(src.replace(m["find"], m["replace"]))
        v = run(block, mut, d)
        killed = v["status"] != "pass"
        report.append({"id": m["id"], "req": m["req"], "desc": m["desc"],
                       "result": "killed" if killed else "SURVIVED",
                       "killed_by": [t["name"] for t in v["tests"] if not t["passed"]]})
        print(f'{m["id"]} {m["req"]:7} {"killed " if killed else "SURVIVED"} {m["desc"]}', flush=True)
    applied = [r for r in report if r["result"] != "not_applicable"]
    killed = sum(r["result"] == "killed" for r in applied)
    summary = {"label": LABEL, "block": block["name"], "suite_sha256": suite_hash(block),
               "ref_rtl_sha256": hashlib.sha256(src.encode()).hexdigest(),
               "mutants_sha256": hashlib.sha256((ROOT / block["mutants"]).read_bytes()).hexdigest(),
               "simulator": tool_version(), "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
               "killed": killed, "injected": len(applied), "tests_dropped": [],
               "survivors": [r["id"] for r in applied if r["result"] == "SURVIVED"], "mutants": report}
    out.mkdir(parents=True, exist_ok=True)
    (out / "mutation.json").write_text(json.dumps(summary, indent=2))
    print(f"{block['name']} mutation score: {killed}/{len(applied)}")
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("block")
    ap.add_argument("--rtl", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    block = load(a.block)
    src = (a.rtl or ROOT / block["reference_rtl"]).read_text()
    out = (a.out or ROOT / "runs" / "blocks" / block["name"] / "mutation").resolve()
    s = mutation_check(block, src, out)
    sys.exit(0 if s["injected"] and s["killed"] == s["injected"] else 1)


if __name__ == "__main__":
    main()
