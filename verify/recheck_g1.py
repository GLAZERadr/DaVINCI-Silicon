"""Re-check stored attempts that G1 rejected for their port list.

A G1 parser bug (fixed in aefeca1) read the arguments of a Verilog function
as module ports, so a design with a helper function was rejected as having an
"extra" port. This script runs today's G1 on the RTL of every stored attempt
rejected for its port list and, when it now passes, simulates it in the
sandbox. The result goes to attempt_<n>/g1_recheck.json next to the attempt;
run.json and the original rejection are never changed.

usage: python verify/recheck_g1.py [--no-sim]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent import pipeline as p  # noqa: E402

FIX_COMMIT = "aefeca1"
CAUSE = "function argument read as a module port"


def head() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                          cwd=ROOT).stdout.strip() or "unknown"


def recheck(run_dir: Path, a: dict, block: str, simulate: bool) -> dict:
    adir = run_dir / f"attempt_{a['n']}"
    resp = adir / "response.md"
    rtl = p.extract(resp.read_text(), block)[0] if resp.exists() else None
    reason = p.validate(rtl, block) if rtl else "no stored response to re-check"
    out = {
        "label": "measured",
        "check": "G1 pre-simulation check, agent/pipeline.py validate()",
        "original_rejection": a["measured"]["rejection"],
        "checked_with_commit": head(),
        "rtl_sha256": p.sha256(rtl.encode()) if rtl else None,
        "g1_now": "pass" if reason is None else "rejected",
    }
    if reason is None:
        out["note"] = (f"rejected by G1 parser bug ({CAUSE}), fixed {FIX_COMMIT}; "
                       "RTL passes G1 on re-check")
    else:
        out["note"] = f"still rejected by today's G1: {reason}"
        out["g1_now_reason"] = reason
    if reason is None and simulate:
        work = adir / "g1_recheck"
        rtl_path = work / f"{block}.v"
        rtl_path.parent.mkdir(parents=True, exist_ok=True)
        rtl_path.write_text(rtl)
        v = p.simulate(rtl_path, work / "sim", "docker")  # model-written RTL: sandbox only
        out["simulated"] = {"sandbox": "docker", "status": v.get("status"), "passed": v.get("passed"),
                            "total": v.get("total"), "suite_sha256": v.get("suite_sha256"),
                            "simulator": v.get("simulator"),
                            "suite_matches_pin": v.get("suite_sha256") == p.SUITE_LOCK.read_text().strip()}
        out["note"] += f"; frozen suite on re-check: {v.get('passed')}/{v.get('total')} ({v.get('status')})"
    (adir / "g1_recheck.json").write_text(json.dumps(out, indent=2) + "\n")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--no-sim", action="store_true", help="only re-run G1, do not simulate")
    a = ap.parse_args()
    found = 0
    for rj in sorted((ROOT / "runs").glob("*/run.json")):
        try:
            r = json.loads(rj.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        for att in r.get("attempts", []):
            rej = (att.get("measured") or {}).get("rejection") or ""
            if att.get("status") == "rejected" and rej.startswith("port list does not match"):
                found += 1
                res = recheck(rj.parent, att, r.get("block") or "sync_fifo", not a.no_sim)
                print(f"{rj.parent.name} attempt {att['n']}: {res['note']}")
    print(f"{found} attempt(s) rejected for their port list")


if __name__ == "__main__":
    main()
