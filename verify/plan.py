"""Verification Plan export: one document per run that traces every requirement
to the frozen tests that check it, the mutants those tests kill, and what the
simulator measured at the first and final attempt.

Built only from stored files (run.json, requirements, mutants, the mutation
check and the weak-test demo). Nothing is re-simulated, no model is called and
no generation time is written, so the same inputs give byte-identical output.

usage: python verify/plan.py runs/<id>                    # writes verification_plan.{md,json} into the run
       python verify/plan.py --reference runs/reference   # reference RTL: verdict.json (+ sweep/sweep.json) from make plan-ref
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RANDOM = "test_random_regression"
MEASURED = "measured"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def reference_run(verdict: dict, sweep: dict | None) -> dict:
    """Shape a bare suite verdict (and sweep, if run) like a one-attempt run so
    one builder serves both."""
    failed = [{"name": t["name"], "message": t["message"]} for t in verdict.get("tests", []) if not t["passed"]]
    att = {"n": 1, "source": "reference", "status": verdict["status"], "rtl_sha256": verdict.get("rtl_sha256"),
           "measured": {"label": MEASURED, "status": verdict["status"],
                        "passed": verdict.get("passed", 0), "total": verdict.get("total", 0),
                        "failed": failed, "simulator": verdict.get("simulator")}}
    if sweep:
        att["sweep"] = {"label": MEASURED, "status": sweep["status"]}
    return {"run_id": "reference", "status": verdict["status"], "seed_bug": None, "replayed_from": None,
            "suite_sha256": verdict.get("suite_sha256"), "sweep_sha256": (sweep or {}).get("sweep_sha256"),
            "requirements_sha256": None, "attempts": [att],
            "attempts_total": 1, "attempts_to_green": 1 if verdict["status"] == "pass" else None}


def resolve(run: dict, att: dict) -> dict | None:
    """The simulator result for an attempt, following a no-progress repeat to the
    attempt it repeated. None when the attempt was never simulated."""
    m = att.get("measured") or {}
    if "same_as_attempt" in m:
        same = next(a for a in run["attempts"] if a["n"] == m["same_as_attempt"])
        return resolve(run, same)
    return m if m.get("status") in ("pass", "fail") else None


def not_simulated(att: dict) -> str:
    m = att.get("measured") or {}
    reason = m.get("rejection") or m.get("error") or att.get("error") or att["status"]
    return f"not simulated ({att['status']}: {reason})" if reason != att["status"] else f"not simulated ({reason})"


def test_results(measured: dict | None, all_tests: list[str]) -> dict | None:
    """Per-test pass/fail, or None if the verdict does not cover the whole suite
    (simulator error, timeout)."""
    if measured is None or measured.get("total") != len(all_tests):
        return None
    failed = {f["name"] for f in measured.get("failed", [])}
    return {t: t not in failed for t in all_tests}


def column(run: dict, att: dict | None, tests: list[str], all_tests: list[str]) -> dict:
    """Measured result of a group of tests at one attempt."""
    if att is None:
        return {"attempt": None, "status": "none", "note": "no attempts"}
    m = resolve(run, att)
    res = test_results(m, all_tests)
    if res is None:
        note = not_simulated(att) if m is None else f"incomplete verdict ({m.get('passed')}/{m.get('total')})"
        return {"attempt": att["n"], "status": "not_simulated", "note": note}
    failing = [t for t in tests if not res[t]]
    return {"attempt": att["n"], "status": "fail" if failing else "pass", "failed_tests": failing}


def build(run: dict, reqs: dict, suite_tests: list[str], mutants: list, mutation: dict | None,
          weak: dict | None, requirements_sha256: str, gaps: dict | None = None,
          scenarios: dict | None = None, scenarios_pin: str | None = None) -> dict:
    """suite_tests is the frozen suite's full test list (from spec/requirements.json),
    which a run's own requirements, e.g. an approved extraction, may not cover."""
    all_tests = sorted(suite_tests)
    attempts = run.get("attempts", [])
    first, final = (attempts[0], attempts[-1]) if attempts else (None, None)

    # Mutation evidence describes the suite, so it only belongs next to a run
    # that used the same suite.
    suite = run.get("suite_sha256")
    mut_ok = bool(mutation) and mutation.get("suite_sha256") == suite
    weak_ok = bool(weak) and weak.get("suite_sha256") == suite
    gaps_ok = bool(gaps) and gaps.get("suite_sha256") == suite
    # Scenario counts belong to this run only if they were taken on its final RTL,
    # with the pinned counter and the same suite.
    final_rtl = (attempts[-1] if attempts else {}).get("rtl_sha256")
    sc_ok = (bool(scenarios) and scenarios.get("status") == "ok" and scenarios.get("suite_sha256") == suite
             and scenarios.get("coverage_sha256") == scenarios_pin and scenarios.get("rtl_sha256") == final_rtl)
    by_id = {m["id"]: m for m in (mutation or {}).get("mutants", [])}

    rows = []
    for r in reqs["requirements"]:
        directed = [t for t in r["tests"] if t != RANDOM]
        # Extracted items (EX-nn) reach mutants through the REQ they were mapped to.
        req_id = r.get("maps_to") or r["id"]
        targeting = []
        for m in mutants:
            if m["req"] != req_id:
                continue
            found = by_id.get(m["id"]) if mut_ok else None
            targeting.append({"id": m["id"], "desc": m["desc"],
                              "result": found["result"] if found else "unknown",
                              "killed_by": found.get("killed_by", []) if found else []})
        no_directed = {"status": "random_only" if RANDOM in r["tests"] else "untested"}
        rows.append({"id": r["id"], "text": r["text"], "maps_to": r.get("maps_to"), "directed_tests": directed,
                     "random_regression": RANDOM in r["tests"], "mutants": targeting,
                     "attempt_1": column(run, first, directed, all_tests) if directed else no_directed,
                     "final": column(run, final, directed, all_tests) if directed else no_directed})

    sweep = (final or {}).get("sweep")
    compile_ = (final or {}).get("measured_compile")
    fm = resolve(run, final) if final else None
    plan = {
        "label": MEASURED,
        "title": f"Verification plan · {reqs.get('block', 'design')} · {run['run_id']}",
        "generator": "verify/plan.py",
        "run": {k: run.get(k) for k in ("run_id", "status", "started", "finished", "seed_bug", "replayed_from",
                                        "attempts_total", "attempts_to_green", "cost_usd")},
        "sources": {
            "suite_sha256": suite,
            "sweep_sha256": run.get("sweep_sha256"),
            "requirements_sha256": requirements_sha256,
            "requirements_match_run": run.get("requirements_sha256") in (None, requirements_sha256),
            "mutants_sha256": (mutation or {}).get("mutants_sha256"),
            "mutation_suite_matches": mut_ok,
            "weak_demo_suite_matches": weak_ok,
            "gaps_suite_matches": gaps_ok,
            "coverage_sha256": scenarios_pin if sc_ok else None,
            "simulator": (fm or {}).get("simulator"),
            "final_rtl_sha256": (final or {}).get("rtl_sha256"),
            "block": reqs.get("block"),
            "extraction": ({"extraction_id": reqs["extraction_id"], "approved_by": reqs.get("approved_by"),
                            "approved_at": reqs.get("approved_at")} if reqs.get("extraction_id") else None),
            "params": reqs.get("params"),
        },
        "gates": {
            "G1_static_and_compile": {"status": "pass" if compile_ and compile_.get("ok") else
                                      "fail" if compile_ else "not_recorded"},
            "G2_frozen_suite": ({"status": fm["status"], "passed": fm["passed"], "total": fm["total"]} if fm else
                                {"status": "not_simulated", "note": not_simulated(final) if final else "no attempts"}),
            # The sweep only runs after a visible pass.
            "G3_parameter_sweep": ({"status": sweep["status"]} if sweep else
                                   {"status": "not_recorded"} if fm and fm["status"] == "pass" else
                                   {"status": "not_run", "note": "runs only after G2 passes"}),
        },
        "requirements": rows,
        "random_regression": {"test": RANDOM, "covers": [r["id"] for r in reqs["requirements"] if RANDOM in r["tests"]],
                              "attempt_1": column(run, first, [RANDOM], all_tests),
                              "final": column(run, final, [RANDOM], all_tests)},
        "mutation": ({"killed": mutation["killed"], "injected": mutation["injected"],
                      "survivors": mutation["survivors"], "measured_against": "reference RTL",
                      "ref_rtl_sha256": mutation.get("ref_rtl_sha256")} if mut_ok else None),
        "weak_test_check": ({"tests_dropped": weak["tests_dropped"], "weak": weak["weak"],
                             "restored": weak["restored"]} if weak_ok else None),
        "scenarios": ({"rtl_sha256": scenarios["rtl_sha256"], "cycles": scenarios["cycles"],
                       "counts": scenarios["counts"], "descriptions": scenarios["scenarios"],
                       "zero": scenarios["zero"], "suite_passed": bool(fm) and fm["status"] == "pass"}
                      if sc_ok else None),
        "gaps": ({"summary": gaps["summary"],
                  "mutants": [{k: m[k] for k in ("id", "req", "directed_killers", "killed_by_own_req_tests",
                                                 "fragile", "random_only")} for m in gaps["mutants"]],
                  "drops_with_survivors": [{k: d[k] for k in ("dropped", "killed", "injected", "survivors")}
                                           for d in gaps["drops"] if d["survivors"]],
                  "drops_total": len(gaps["drops"])} if gaps_ok else None),
        "attempts": [{"n": a["n"], "source": a.get("source"), "status": a["status"],
                      "result": (lambda m: f"{m['passed']}/{m['total']}" if m else not_simulated(a))(resolve(run, a))}
                     for a in attempts],
        "not_verifiable": run.get("not_verifiable"),
    }
    return plan


MARK = {"pass": "✓ Pass", "fail": "✕ Fail", "killed": "✓ killed", "survived": "✕ survived",
        "not_simulated": "○ Not simulated", "untested": "○ No test", "not_recorded": "○ Not recorded", "not_run": "○ Not run", "random_only": "○ Random only", "unknown": "○ Unknown", "none": "○ None"}


def cell(c: dict) -> str:
    s = MARK.get(c["status"], c["status"])
    if "passed" in c:
        s += f" {c['passed']}/{c['total']}"
    if c.get("failed_tests"):
        s += " (" + ", ".join(f"`{t}`" for t in c["failed_tests"]) + ")"
    if c.get("note"):
        s += f" · {c['note']}"
    return s


def markdown(p: dict) -> str:
    src, run = p["sources"], p["run"]
    out = [f"# {p['title']}", "",
           "Every result below is **measured** (simulator output from stored files). "
           "No AI interpretation appears in this plan.", "",
           "## Sources", "", "| | |", "| --- | --- |",
           f"| Run | `{run['run_id']}` · status `{run['status']}` · attempts {run['attempts_total']} |"]
    if run.get("seed_bug"):
        out.append(f"| Seeded bug | {run['seed_bug']} (attempt 1 is the seeded RTL, not model output) |")
    if run.get("replayed_from"):
        out.append(f"| Replay of | `{run['replayed_from']}` |")
    for k, name in (("suite_sha256", "Frozen suite"), ("sweep_sha256", "Parameter sweep"),
                    ("requirements_sha256", "Requirements"), ("mutants_sha256", "Mutant set"),
                    ("final_rtl_sha256", "Final RTL")):
        out.append(f"| {name} | `{src[k]}` |" if src[k] else f"| {name} | — |")
    out.append(f"| Simulator | {src['simulator'] or '—'} |")
    out.append(f"| Parameters | {', '.join(f'{k}={v}' for k, v in (src['params'] or {}).items())} |")
    warnings = []
    if not src["requirements_match_run"]:
        warnings.append("The requirements file differs from the one this run used.")
    if not src["mutation_suite_matches"]:
        warnings.append("The stored mutation check used a different frozen suite; mutant results are shown as unknown.")
    if not src["weak_demo_suite_matches"]:
        warnings.append("The stored weak-test check used a different frozen suite; it is left out.")
    if p.get("not_verifiable"):
        warnings.append("Not verifiable by this suite: " + "; ".join(p["not_verifiable"]))
    if warnings:
        out += ["", *[f"> ○ {w}" for w in warnings]]

    g = p["gates"]
    out += ["", "## Gates at the final attempt", "",
            f"- **G1** static checks + `iverilog -g2001 -Wall`: {cell(g['G1_static_and_compile'])}",
            f"- **G2** frozen suite: {cell(g['G2_frozen_suite'])}",
            f"- **G3** parameter sweep (never shown to the model): {cell(g['G3_parameter_sweep'])}",
            "", "## Requirements → tests → mutants → result", "",
            "| Req | Requirement | Directed tests | Mutants targeting it | Attempt 1 | Final |",
            "| --- | --- | --- | --- | --- | --- |"]
    ex = src.get("extraction")
    if ex:
        out[-2:-2] = [f"Requirements come from approved extraction `{ex['extraction_id']}` "
                      f"(approved by {ex['approved_by']}). The *Maps to* link from each item to a REQ was "
                      "proposed by the model (AI interpretation · not verified) and approved with the list; "
                      "the test results are measured.", ""]
    for r in p["requirements"]:
        tests = "<br>".join(f"`{t}`" for t in r["directed_tests"]) or "—"
        muts = "<br>".join(f"{m['id']} {MARK.get(m['result'], m['result'])}" for m in r["mutants"]) or "—"
        rid = f"{r['id']} → {r['maps_to']}" if r.get("maps_to") else r["id"]
        out.append(f"| {rid} | {r['text']} | {tests} | {muts} | {cell(r['attempt_1'])} | {cell(r['final'])} |")
    untested = [r["id"] for r in p["requirements"] if r["attempt_1"]["status"] == "untested"]
    if untested:
        out += ["", f"○ {len(untested)} item(s) have no test in the frozen suite: {', '.join(untested)}."]
    rr = p["random_regression"]
    out += ["", "Results are per test: a test shared by two requirements marks both rows.",
            "", f"`{rr['test']}` runs 3000 random cycles against the golden model and covers "
            f"{', '.join(rr['covers'])}. It is reported once here rather than in every row.", "",
            f"- Attempt 1: {cell(rr['attempt_1'])}", f"- Final: {cell(rr['final'])}"]

    out += ["", "## Mutation check (qualifies the suite, measured against the reference RTL)", ""]
    m = p["mutation"]
    if m:
        out.append(f"{m['killed']}/{m['injected']} hand-written mutants killed"
                   + (f"; survivors: {', '.join(m['survivors'])}." if m["survivors"] else "."))
    else:
        out.append("○ No mutation check for this suite hash.")
    w = p["weak_test_check"]
    if w:
        out += ["", f"Weak-test check: with {', '.join(f'`{t}`' for t in w['tests_dropped'])} left out, "
                f"{w['weak']['killed']}/{w['weak']['injected']} killed (survivors: {', '.join(w['weak']['survivors']) or 'none'}); "
                f"restored suite {w['restored']['killed']}/{w['restored']['injected']}."]

    out += ["", "## Scenario coverage (final RTL)", ""]
    sc = p["scenarios"]
    if sc:
        out += [f"How often the frozen suite drove the final RTL into each situation, counted at every rising "
                f"clock edge over {sc['cycles']} cycles from a waveform of the same tests (`verify/coverage.py`, "
                "flags as the design reported them)."]
        if not sc["suite_passed"]:
            out += ["", "> ○ The suite did not pass on this RTL, and a failing test stops at its first mismatch, "
                    "so these counts are partial."]
        out += ["", "| Scenario | Count |", "| --- | --- |"]
        for k, n in sc["counts"].items():
            out.append(f"| {sc['descriptions'][k]} | {n}{'  ○ never reached' if n == 0 else ''} |")
        out += ["", f"Never reached: {', '.join(sc['zero']) or 'none'}."]
    else:
        out.append("○ Not counted for this RTL (`make coverage RUN=<id>`, or `make coverage-ref`).")

    out += ["", "## Plan gaps (measured against the reference RTL)", ""]
    gp = p["gaps"]
    if gp:
        sm = gp["summary"]
        out += [f"- Mutants caught by only one directed test: {', '.join(sm['fragile']) or 'none'}",
                f"- Mutants caught only by the random regression: {', '.join(sm['random_only']) or 'none'}",
                f"- Requirements no mutant targets (nothing shows their tests would catch a bug): "
                f"{', '.join(sm['requirements_without_mutant']) or 'none'}",
                f"- Re-simulated with tests left out: {gp['drops_total']} suites; "
                f"prediction from the full run's killers {'matched every one' if sm['all_predictions_match'] else 'did NOT match'}.",
                "", "| Mutant | Targets | Directed tests that kill it | Killed by its own requirement's tests |",
                "| --- | --- | --- | --- |"]
        for m in gp["mutants"]:
            flag = " ○ only one" if m["fragile"] else " ○ none (random only)" if m["random_only"] else ""
            own = ", ".join(f"`{t}`" for t in m["killed_by_own_req_tests"]) or "✕ no"
            out.append(f"| {m['id']} | {m['req']} | {', '.join(f'`{t}`' for t in m['directed_killers']) or '—'}{flag} | {own} |")
        out += ["", "Suites that let a mutant survive:", "", "| Left out | Killed | Survivors |", "| --- | --- | --- |"]
        for d in gp["drops_with_survivors"]:
            out.append(f"| {', '.join(f'`{t}`' for t in d['dropped'])} | {d['killed']}/{d['injected']} | ✕ {', '.join(d['survivors'])} |")
        if not gp["drops_with_survivors"]:
            out.append("| — | — | none |")
    else:
        out.append("○ No coverage-gap check for this suite hash (`make gaps`).")

    out += ["", "## Every attempt", "", "| # | Source | Status | Frozen suite |", "| --- | --- | --- | --- |"]
    for a in p["attempts"]:
        out.append(f"| {a['n']} | {a['source']} | {a['status']} | {a['result']} |")
    return "\n".join(out) + "\n"


def suite_tests(canonical: dict) -> list[str]:
    return sorted({t for r in canonical["requirements"] for t in r["tests"]})


def write(plan: dict, out_dir: Path):
    (out_dir / "verification_plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    (out_dir / "verification_plan.md").write_text(markdown(plan))


def plan_for(run_dir: Path, reference: bool = False) -> dict:
    """Build the plan for a stored run (or, with reference, make plan-ref's output)."""
    if reference:
        verdict = load(run_dir / "verdict.json")
        if verdict is None:
            raise SystemExit(f"no verdict.json in {run_dir}; run `make plan-ref` first")
        run = reference_run(verdict, load(run_dir / "sweep" / "sweep.json"))
        req_path = ROOT / "spec" / "requirements.json"
    else:
        run = load(run_dir / "run.json")
        if run is None:
            raise SystemExit(f"no run.json in {run_dir}")
        req_path = ROOT / (run.get("requirements_file") or "spec/requirements.json")
        if not req_path.exists():  # e.g. a scratch requirements file since deleted; the hash check flags it
            req_path = ROOT / "spec" / "requirements.json"
    raw = req_path.read_bytes()
    canonical = json.loads((ROOT / "spec" / "requirements.json").read_text())
    return build(run, json.loads(raw), suite_tests(canonical),
                 json.loads((ROOT / "verify" / "mutants.json").read_text()),
                 load(ROOT / "runs" / "mutation" / "mutation.json"),
                 load(ROOT / "runs" / "weak_demo" / "weak_demo.json"), sha256(raw),
                 load(ROOT / "runs" / "coverage_gap" / "gaps.json"),
                 load(run_dir / "coverage" / "coverage.json"),
                 (ROOT / "verify" / "coverage.sha256").read_text().strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--reference", action="store_true", help="run_dir holds make plan-ref's verdict.json")
    a = ap.parse_args()
    write(plan_for(a.run_dir, a.reference), a.run_dir)
    print(f"wrote {a.run_dir}/verification_plan.md and .json")


if __name__ == "__main__":
    main()
