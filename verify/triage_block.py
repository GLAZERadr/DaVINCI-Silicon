"""Test credibility ("is it the design or the test?") for a registered block
other than the FIFO. Same rule as verify/triage.py, separate output, so the
FIFO triage is unchanged.

From stored files only (no simulation, no model call):
  runs/blocks/<b>/reference/verdict.json   frozen suite on the reference RTL
  runs/blocks/<b>/mutation/mutation.json   planted bugs each test kills
  runs/blocks/<b>/candidate/verdict.json   candidate (unfrozen) tests on the reference RTL
  runs/blocks/<b>/model_demo/model_demo.json  (sat_gain) float vs bit-accurate model counts

validated = passes on the reference RTL under the pinned suite and kills at
least one planted bug. A candidate test that fails on the reference RTL is
flagged: its expected values disagree with a design already known to meet the
spec, so its reference model is suspect. Measured, not AI text.

usage: python verify/triage_block.py <block> [--out runs/blocks/<block>/triage.json]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_block import ROOT, load  # noqa: E402

VALIDATED = "Test validated · failure points to the design under test"
NOT_VALIDATED = "Test not yet validated · check the test before the design"
DISAGREES = "Test not yet validated · disagrees with the reference RTL"


def _load(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


def build(name: str) -> dict:
    block = load(name)
    base = ROOT / "runs" / "blocks" / name
    pinned = (ROOT / block["suite_lock"]).read_text().strip()
    ref = _load(base / "reference" / "verdict.json")
    mutation = _load(base / "mutation" / "mutation.json")
    cand = _load(base / "candidate" / "verdict.json")
    demo = _load(base / "model_demo" / "model_demo.json")
    ref_ok = bool(ref) and ref.get("suite_sha256") == pinned
    mut_ok = bool(mutation) and mutation.get("suite_sha256") == pinned
    ref_tests = {t["name"]: t["passed"] for t in (ref or {}).get("tests", [])} if ref_ok else {}

    tests = {}
    for tname, passes in sorted(ref_tests.items()):
        kills = sorted(m["id"] for m in (mutation or {}).get("mutants", []) if mut_ok and tname in m.get("killed_by", []))
        ok = bool(passes) and bool(kills)
        tests[tname] = {"kind": "frozen", "passes_on_reference": passes, "kills": kills, "validated": ok,
                        "verdict": VALIDATED if ok else NOT_VALIDATED}
    cand_rtl_ok = bool(cand) and bool(ref) and cand.get("rtl_sha256") == ref.get("rtl_sha256")
    for t in (cand or {}).get("tests", []):
        tests[t["name"]] = {
            "kind": "candidate", "reference_model": "float model (blocks/sat_gain/candidate/float_model.py)"
            if name == "sat_gain" else None,
            "passes_on_reference": t["passed"] if cand_rtl_ok else None, "kills": [], "validated": False,
            "verdict": DISAGREES if cand_rtl_ok and not t["passed"] else NOT_VALIDATED,
            "first_failure": t["message"] or None,
        }
    out = {
        "label": "measured",
        "generator": "verify/triage_block.py",
        "block": name,
        "pinned_suite_sha256": pinned,
        "reference": {"rtl_sha256": (ref or {}).get("rtl_sha256"), "suite_sha256": (ref or {}).get("suite_sha256"),
                      "simulator": (ref or {}).get("simulator"), "suite_matches_pin": ref_ok},
        "mutation_suite_matches_pin": mut_ok,
        "candidate_tests": (cand or {}).get("candidate"),
        "rule": "validated = passes on the reference RTL under the pinned suite and kills at least one planted bug; "
                "a candidate test that fails on the reference RTL disagrees with it",
        "tests": tests,
    }
    if demo:
        out["model_demo"] = {k: demo[k] for k in ("label", "vectors", "rtl_sha256")} | {
            "float_model": {k: demo["float_model"].get(k) for k in ("disagree", "vectors", "first_mismatch",
                                                                    "disagreements_by_cause")},
            "bit_accurate_model": {k: demo["bit_accurate_model"][k] for k in ("disagree", "vectors")}}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("block")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    t = build(a.block)
    out = a.out or ROOT / "runs" / "blocks" / a.block / "triage.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(t, indent=2) + "\n")
    for n, x in t["tests"].items():
        print(f"{x['kind']:9} {n:32} {x['verdict']}")


if __name__ == "__main__":
    main()
