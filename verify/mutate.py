"""Mutation check: inject known bugs into a passing RTL and confirm the frozen
suite catches each one. A surviving mutant means a test is too weak.

usage: python verify/mutate.py rtl/sync_fifo.v [--out runs/mutation]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_suite import ROOT, run  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rtl", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "runs" / "mutation")
    a = ap.parse_args()
    src = a.rtl.read_text()
    mutants = json.loads((ROOT / "verify" / "mutants.json").read_text())
    report = []
    for m in mutants:
        if src.count(m["find"]) != 1:
            report.append({**m, "result": "not_applicable"})
            continue
        d = a.out.resolve() / m["id"]
        d.mkdir(parents=True, exist_ok=True)
        mut = d / "sync_fifo.v"
        mut.write_text(src.replace(m["find"], m["replace"]))
        v = run(mut, d)
        killed = v["status"] != "pass"
        report.append({"id": m["id"], "req": m["req"], "desc": m["desc"],
                       "result": "killed" if killed else "SURVIVED",
                       "killed_by": [t["name"] for t in v["tests"] if not t["passed"]]})
        print(f'{m["id"]} {m["req"]:7} {"killed " if killed else "SURVIVED"} {m["desc"]}', flush=True)
    applied = [r for r in report if r["result"] != "not_applicable"]
    killed = sum(r["result"] == "killed" for r in applied)
    summary = {"killed": killed, "injected": len(applied), "mutants": report}
    (a.out / "mutation.json").write_text(json.dumps(summary, indent=2))
    print(f"mutation score: {killed}/{len(applied)}")
    sys.exit(0 if killed == len(applied) else 1)


if __name__ == "__main__":
    main()
