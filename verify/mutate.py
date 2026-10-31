"""Mutation check: inject known bugs into a passing RTL and confirm the frozen
suite catches each one. A surviving mutant means a test is too weak.

usage: python verify/mutate.py rtl/sync_fifo.v [--out runs/mutation]
       python verify/mutate.py rtl/sync_fifo.v --weak-demo [--drop a,b]

--weak-demo runs the check twice: first with directed tests left out (a
deliberately weakened suite), then with the full frozen suite. It shows the
check flagging the weak suite and the restored suite killing the survivor.
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_suite import ROOT, run, suite_hash, tool_version  # noqa: E402

LABEL = "Suite mutation score vs reference RTL (hand-written mutants)"


def provenance(src: str) -> dict:
    """What this score was measured against, so it is only shown next to runs
    that used the same suite. It describes the suite, not any generated RTL."""
    return {"label": LABEL, "suite_sha256": suite_hash(),
            "ref_rtl_sha256": hashlib.sha256(src.encode()).hexdigest(),
            "mutants_sha256": hashlib.sha256((ROOT / "verify" / "mutants.json").read_bytes()).hexdigest(),
            "simulator": tool_version(), "created": time.strftime("%Y-%m-%dT%H:%M:%S%z")}

# REQ-06 has one directed test; the random regression also hits it, so both go.
WEAK_DEMO_DROP = ["test_full_simultaneous_rw", "test_random_regression"]


def mutation_check(src: str, out: Path, drop=(), label="") -> dict:
    mutants = json.loads((ROOT / "verify" / "mutants.json").read_text())
    report = []
    for m in mutants:
        if src.count(m["find"]) != 1:
            report.append({**m, "result": "not_applicable"})
            continue
        d = out / m["id"]
        d.mkdir(parents=True, exist_ok=True)
        mut = d / "sync_fifo.v"
        mut.write_text(src.replace(m["find"], m["replace"]))
        v = run(mut, d, drop=drop)
        killed = v["status"] != "pass"
        report.append({"id": m["id"], "req": m["req"], "desc": m["desc"],
                       "result": "killed" if killed else "SURVIVED",
                       "killed_by": [t["name"] for t in v["tests"] if not t["passed"]]})
        print(f'{label}{m["id"]} {m["req"]:7} {"killed " if killed else "SURVIVED"} {m["desc"]}', flush=True)
    applied = [r for r in report if r["result"] != "not_applicable"]
    killed = sum(r["result"] == "killed" for r in applied)
    summary = {**provenance(src), "killed": killed, "injected": len(applied), "tests_dropped": list(drop),
               "survivors": [r["id"] for r in applied if r["result"] == "SURVIVED"], "mutants": report}
    out.mkdir(parents=True, exist_ok=True)
    (out / "mutation.json").write_text(json.dumps(summary, indent=2))
    print(f"{label}mutation score: {killed}/{len(applied)}")
    return summary


def weak_demo(src: str, out: Path, drop: list) -> dict:
    print(f"== weakened suite (left out: {', '.join(drop)})")
    weak = mutation_check(src, out / "weak", drop=drop, label="weak     ")
    print("== restored full suite")
    full = mutation_check(src, out / "restored", label="restored ")
    caught = [m for m in weak["survivors"] if m not in full["survivors"]]
    demo = {
        **provenance(src),
        "label": "measured: weakened suite vs restored suite, against the reference RTL",
        "tests_dropped": drop,
        "weak": {"killed": weak["killed"], "injected": weak["injected"], "survivors": weak["survivors"]},
        "restored": {"killed": full["killed"], "injected": full["injected"], "survivors": full["survivors"]},
        "weak_suite_flagged": bool(weak["survivors"]),
        "survivors_killed_after_restore": caught,
        "killed_by_after_restore": {m["id"]: m["killed_by"] for m in full["mutants"] if m["id"] in caught},
    }
    (out / "weak_demo.json").write_text(json.dumps(demo, indent=2))
    ok = demo["weak_suite_flagged"] and not full["survivors"]
    print(f"weak suite flagged: {demo['weak_suite_flagged']} · survivors {weak['survivors']} "
          f"killed after restore: {caught}")
    return demo | {"ok": ok}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rtl", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--weak-demo", action="store_true")
    ap.add_argument("--drop", default=",".join(WEAK_DEMO_DROP), help="tests left out in --weak-demo")
    a = ap.parse_args()
    src = a.rtl.read_text()
    if a.weak_demo:
        out = (a.out or ROOT / "runs" / "weak_demo").resolve()
        sys.exit(0 if weak_demo(src, out, [t for t in a.drop.split(",") if t])["ok"] else 1)
    s = mutation_check(src, (a.out or ROOT / "runs" / "mutation").resolve())
    sys.exit(0 if s["killed"] == s["injected"] else 1)


if __name__ == "__main__":
    main()
