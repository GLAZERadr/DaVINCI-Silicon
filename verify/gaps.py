"""Coverage-gap check: where the verification plan is thin, not where the RTL fails.

Against the reference RTL and the 8 hand-written mutants it measures:
  - every mutant's killers in the full suite, and which mutants only one
    directed test (or only the random regression) catches;
  - requirements no mutant targets, so nothing shows their tests would catch a bug;
  - the mutation check re-simulated with each test left out, and with each
    directed test left out together with the random regression (the directed
    suite alone). Survivors are the gaps.

Each drop is also predicted from the full run's killers (a mutant survives
when every test that killed it was dropped); prediction and simulation must
agree, which also checks that the tests do not depend on each other.

The reference RTL and mutants are hand-written, not model output, so this runs
locally like `make mutate`.

usage: python verify/gaps.py rtl/sync_fifo.v [--out runs/coverage_gap]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mutate import mutation_check, provenance  # noqa: E402
from run_suite import ROOT, all_tests  # noqa: E402

RANDOM = "test_random_regression"
LABEL = "measured: mutation check with tests left out, against the reference RTL"


def gaps(src: str, out: Path) -> dict:
    reqs = json.loads((ROOT / "spec" / "requirements.json").read_text())["requirements"]
    tests = all_tests()
    directed = [t for t in tests if t != RANDOM]

    print("== full suite")
    full = mutation_check(src, out / "full", label="full     ")
    killers = {m["id"]: set(m["killed_by"]) for m in full["mutants"] if m["result"] != "not_applicable"}

    mutants = []
    for m in full["mutants"]:
        if m["result"] == "not_applicable":
            continue
        d = sorted(set(m["killed_by"]) - {RANDOM})
        own = [t for r in reqs if r["id"] == m["req"] for t in r["tests"] if t != RANDOM]
        mutants.append({"id": m["id"], "req": m["req"], "desc": m["desc"], "result": m["result"],
                        "killed_by": m["killed_by"], "directed_killers": d,
                        "killed_by_own_req_tests": sorted(set(d) & set(own)),
                        "fragile": len(d) == 1, "random_only": not d and RANDOM in m["killed_by"]})

    targeted = {m["req"] for m in mutants}
    requirements = [{"id": r["id"], "directed_tests": [t for t in r["tests"] if t != RANDOM],
                     "mutants": [m["id"] for m in mutants if m["req"] == r["id"]],
                     "no_mutant": r["id"] not in targeted} for r in reqs]

    drops = [[t] for t in tests] + [[t, RANDOM] for t in directed]
    rows = []
    for drop in drops:
        name = "+".join(drop)
        print(f"== without {', '.join(drop)}")
        s = mutation_check(src, out / name, drop=drop, label=f"{name[:24]:24} ")
        predicted = sorted(mid for mid, k in killers.items() if k <= set(drop))
        rows.append({"dropped": drop, "killed": s["killed"], "injected": s["injected"],
                     "survivors": s["survivors"], "predicted_survivors": predicted,
                     "prediction_matches": sorted(s["survivors"]) == predicted})

    report = {**provenance(src), "label": LABEL, "full": {"killed": full["killed"], "injected": full["injected"],
                                                        "survivors": full["survivors"]},
              "mutants": mutants, "requirements": requirements, "drops": rows,
              "summary": {
                  "fragile": [m["id"] for m in mutants if m["fragile"]],
                  "random_only": [m["id"] for m in mutants if m["random_only"]],
                  "requirements_without_mutant": [r["id"] for r in requirements if r["no_mutant"]],
                  "single_drops_with_survivors": [r["dropped"][0] for r in rows
                                                  if len(r["dropped"]) == 1 and r["survivors"]],
                  "directed_only_drops_with_survivors": [r["dropped"][0] for r in rows
                                                         if len(r["dropped"]) == 2 and r["survivors"]],
                  "all_predictions_match": all(r["prediction_matches"] for r in rows),
              }}
    (out / "gaps.json").write_text(json.dumps(report, indent=2))
    s = report["summary"]
    print(f"fragile (one directed killer): {s['fragile']} · random only: {s['random_only']} · "
          f"no mutant: {s['requirements_without_mutant']} · predictions match: {s['all_predictions_match']}")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rtl", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "runs" / "coverage_gap")
    a = ap.parse_args()
    r = gaps(a.rtl.read_text(), a.out.resolve())
    sys.exit(0 if r["summary"]["all_predictions_match"] else 1)


if __name__ == "__main__":
    main()
