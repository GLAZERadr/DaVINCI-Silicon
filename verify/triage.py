"""Test credibility for failure triage: "is it the design or the test?"

For every frozen test, from stored files only (no simulation, no model call):
  - does it pass on the hand-written reference RTL, and with which suite hash
    (runs/reference/verdict.json from `make plan-ref`);
  - which planted bugs it kills (runs/mutation/mutation.json), and which only
    it catches among the directed tests (runs/coverage_gap/gaps.json);
  - which situations it drives, counted per test from the reference RTL's
    per-cycle trace (runs/reference/trace/trace.json) with the same scenario
    definitions as verify/coverage.py;
  - when the test code last changed (git), so a run is only judged against
    the test code it actually ran.

A test is "validated" when it passes on the reference RTL under the pinned
suite and kills at least one planted bug: a failure then points to the design
under test. Anything else is "not yet validated · check the test before the
design". Measured, not AI text. The result is the same for every run that ran
this test code, so one file serves the whole bundle.

usage: python verify/triage.py [--out runs/triage.json]
"""
import argparse
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEST_FILES = ["tests/test_sync_fifo.py", "tests/golden_model.py"]

_spec = importlib.util.spec_from_file_location("davinci_coverage", ROOT / "verify" / "coverage.py")
cov = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cov)


def load(rel: str):
    p = ROOT / rel
    return json.loads(p.read_text()) if p.exists() else None


def scenario_hits(test: dict) -> dict:
    """Scenario counts for one test, sampled like verify/coverage.py: inputs as
    the DUT saw them at the edge, flags as they stood just before it (the
    previous cycle's outputs)."""
    counts = {k: 0 for k in cov.SCENARIOS}
    prev = {f: 0 for f in ("full", "empty", "almost_full", "overflow", "underflow")}
    for c in test["cycles"]:
        v = {**{k: bool(c["in"].get(k)) for k in ("rst", "wr_en", "rd_en")}, **{k: bool(x) for k, x in prev.items()}}
        for k, (_, hit) in cov.SCENARIOS.items():
            counts[k] += bool(hit(v))
        prev = {f: c["out"].get(f) or 0 for f in prev}
    return {k: n for k, n in counts.items() if n}


def flags_seen(test: dict) -> dict:
    """Output flags the test saw high just after an edge (what it compares)."""
    seen = {}
    for c in test["cycles"]:
        for f in ("full", "empty", "almost_full", "overflow", "underflow"):
            if c["out"].get(f):
                seen[f] = seen.get(f, 0) + 1
    return seen


def git_last_change() -> str | None:
    p = subprocess.run(["git", "log", "-1", "--format=%cI", "--", *TEST_FILES], cwd=ROOT, capture_output=True, text=True)
    return p.stdout.strip() or None


def build() -> dict:
    pinned = (ROOT / "verify" / "suite.sha256").read_text().strip()
    ref = load("runs/reference/verdict.json")
    mutation = load("runs/mutation/mutation.json")
    gaps = load("runs/coverage_gap/gaps.json")
    trace = load("runs/reference/trace/trace.json")
    ref_ok = bool(ref) and ref.get("suite_sha256") == pinned
    mut_ok = bool(mutation) and mutation.get("suite_sha256") == pinned
    gaps_ok = bool(gaps) and gaps.get("suite_sha256") == pinned
    ref_tests = {t["name"]: t["passed"] for t in (ref or {}).get("tests", [])} if ref_ok else {}
    per_test_trace = {t["name"]: t for t in (trace or {}).get("tests", [])}

    tests = {}
    for name in sorted(ref_tests or {t for m in (mutation or {}).get("mutants", []) for t in m.get("killed_by", [])}):
        kills = sorted(m["id"] for m in (mutation or {}).get("mutants", []) if mut_ok and name in m.get("killed_by", []))
        alone = sorted(m["id"] for m in (gaps or {}).get("mutants", []) if gaps_ok and m.get("directed_killers") == [name])
        t = per_test_trace.get(name)
        passes = ref_tests.get(name)
        tests[name] = {
            "passes_on_reference": passes,
            "kills": kills,
            "only_directed_killer_of": alone,
            "scenarios": scenario_hits(t) if t else None,
            "flags_seen": flags_seen(t) if t else None,
            "scenarios_partial": bool(t and t.get("truncated")),
            "validated": bool(passes) and bool(kills),
        }
    return {
        "label": "measured",
        "generator": "verify/triage.py",
        "pinned_suite_sha256": pinned,
        "reference": {"rtl_sha256": (ref or {}).get("rtl_sha256"), "suite_sha256": (ref or {}).get("suite_sha256"),
                      "simulator": (ref or {}).get("simulator"), "suite_matches_pin": ref_ok},
        "mutation_suite_matches_pin": mut_ok,
        "test_code": {"files": {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in TEST_FILES},
                      "last_changed": git_last_change()},
        "rule": "validated = passes on the reference RTL under the pinned suite and kills at least one planted bug",
        "tests": tests,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "runs" / "triage.json")
    a = ap.parse_args()
    t = build()
    a.out.write_text(json.dumps(t, indent=2) + "\n")
    v = [n for n, x in t["tests"].items() if x["validated"]]
    print(f"{len(v)}/{len(t['tests'])} tests validated; reference suite matches pin: {t['reference']['suite_matches_pin']}")


if __name__ == "__main__":
    main()
