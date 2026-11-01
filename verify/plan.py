"""Verification Plan export in the shape a verification lead expects (ChipVerify
Vplan sections, OpenTitan testpoint fields and staged sign-off), scaled to one
block, plus the two things DaVINCI adds: mutation evidence and AI provenance.

Sections: 1 header · 2 scope · 3 methodology · 4 testpoints (one per
requirement: id, name, milestone, desc = goal · stimulus · check, tests,
result, mutants, scenario hits) · 5 coverage summary (functional, mutation,
code = not measured) · 6 sign-off status · 7 AI provenance.

Built only from stored files (run.json, requirements, mutants, the mutation
check, the weak-test demo, coverage-gap and scenario counts, the frozen test
file's docstrings). Nothing is re-simulated, no model is called and no
generation time is written, so the same inputs give byte-identical output.
Missing data is written as "not measured", never guessed.

usage: python verify/plan.py runs/<id>                    # writes verification_plan.{md,json,csv} + testplan.hjson into the run
       python verify/plan.py --reference runs/reference   # reference RTL: verdict.json (+ sweep/sweep.json) from make plan-ref
"""
import argparse
import ast
import csv
import hashlib
import io
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RANDOM = "test_random_regression"
MEASURED = "measured"
NOT_MEASURED = "not measured"

# Testpoint names (OpenTitan style, lower_snake_case) and milestones:
# V1 = reset and basic flags, V2 = corner cases (full + read/write, wrap, overflow/underflow).
TESTPOINTS = {
    "REQ-01": ("reset_state", "V1"),
    "REQ-02": ("fifo_order_wraparound", "V2"),
    "REQ-03": ("full_empty_flags", "V1"),
    "REQ-04": ("overflow_write_when_full", "V2"),
    "REQ-05": ("underflow_read_when_empty", "V2"),
    "REQ-06": ("read_write_when_full", "V2"),
    "REQ-07": ("read_write_when_empty", "V2"),
    "REQ-08": ("almost_full_threshold", "V1"),
    "REQ-09": ("count_tracks_occupancy", "V1"),
    "REQ-10": ("no_overflow_read_write_when_full", "V2"),
}
# Scenario counters (verify/coverage.py) that exercise each requirement.
SCENARIOS_FOR = {
    "REQ-01": ["reset"], "REQ-02": ["write_pointer_wrap"], "REQ-03": ["full", "empty"],
    "REQ-04": ["write_when_full", "overflow_pulse"], "REQ-05": ["read_when_empty", "underflow_pulse"],
    "REQ-06": ["rw_when_full"], "REQ-07": ["rw_when_empty"], "REQ-08": ["almost_full"], "REQ-09": [],
    "REQ-10": ["rw_when_full"],
}
CHECK = "every output compared with the cycle-accurate golden model on every clock (scoreboard)"
OUT_OF_SCOPE = ["timing, synthesis, area and power", "clock-domain crossing (single clock by design)",
                "formal proof", "gate-level simulation", "code coverage (Icarus Verilog has no built-in code coverage)"]


def test_facts(src: str) -> tuple[dict, str | None]:
    """Docstrings of the frozen tests (the stimulus each one applies) and the
    random regression's recorded seed, read from the test file's source."""
    docs = {}
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.AsyncFunctionDef) and node.name.startswith("test_"):
            first = (ast.get_docstring(node) or "").split("\n")[0]
            docs[node.name] = re.sub(r"^REQ-[^:]*:\s*", "", first).rstrip(".")
    m = re.search(r"random\.Random\((\d+)\)", src)
    return docs, m.group(1) if m else None


def slug(text: str) -> str:
    return "_".join(re.findall(r"[a-z0-9]+", text.lower())[:5]) or "item"


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
          scenarios: dict | None = None, scenarios_pin: str | None = None, *,
          spec: dict | None = None, test_docs: dict | None = None, seed: str | None = None,
          pinned_suite: str | None = None) -> dict:
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
    test_docs = test_docs or {}
    rr_final = column(run, final, [RANDOM], all_tests)

    # 4. Testpoints, one per requirement, in OpenTitan field names.
    testpoints = []
    for r, row in zip(reqs["requirements"], rows):
        base = r.get("maps_to") or r["id"]
        name, milestone = TESTPOINTS.get(base, (slug(r["text"]), "—"))
        if r.get("maps_to"):
            name = f"{name}__{r['id'].lower().replace('-', '')}"
        if not r.get("maps_to") and r["id"] not in TESTPOINTS:
            milestone = "—"
        status = row["final"]["status"]
        result = ("unverified" if status == "untested" else rr_final["status"] if status == "random_only"
                  else status if status in ("pass", "fail") else NOT_MEASURED)
        if sc_ok:
            names = SCENARIOS_FOR.get(base)
            hits = ({k: scenarios["counts"].get(k) for k in names} if names
                    else "no scenario defined" if names is not None else NOT_MEASURED)
        else:
            hits = NOT_MEASURED
        stim = "; ".join(f"{t}: {test_docs.get(t, '')}".rstrip(": ") for t in row["directed_tests"])
        testpoints.append({
            "id": r["id"], "name": name, "milestone": milestone,
            "desc": {"goal": r["text"], "stimulus": stim or ("3000-cycle constrained-random regression only"
                                                              if row["random_regression"] else "no test"),
                     "check": CHECK},
            "tests": r["tests"], "result": result,
            "result_attempt_1": row["attempt_1"]["status"],
            "mutants": [{"id": m["id"], "result": m["result"]} for m in row["mutants"]],
            "scenario_hits": hits,
        })

    # 5. Coverage summary.
    if sc_ok:
        hit = [k for k, n in scenarios["counts"].items() if n > 0]
        functional = {"hit": len(hit), "total": len(scenarios["counts"]), "zero": scenarios["zero"],
                      "partial": not (bool(fm) and fm["status"] == "pass")}
    else:
        functional = NOT_MEASURED
    if mut_ok:
        survivors = [{"id": m["id"], "req": m["req"]} for m in mutation["mutants"] if m["result"] == "SURVIVED"]
        mutation_cov = {"killed": mutation["killed"], "injected": mutation["injected"], "survivors": survivors}
    else:
        mutation_cov = NOT_MEASURED
    coverage_summary = {"functional": functional, "mutation": mutation_cov,
                        "code": "not measured (Icarus Verilog has no built-in code coverage)"}

    # 6. Sign-off, DaVINCI-scaled after OpenTitan V2. Each line from real data only.
    def line(cid, label, ok, evidence):
        return {"id": cid, "criterion": label,
                "status": NOT_MEASURED if ok is None else "met" if ok else "not met", "evidence": evidence}
    every_tested = all(tp["result"] != "unverified" for tp in testpoints)
    full_pass = bool(fm) and fm["status"] == "pass" and fm.get("total") == len(all_tests)
    attempts_same_suite = all((a.get("measured") or {}).get("suite_sha256") in (None, suite) for a in attempts)
    signoff = [
        line("tests", "Every requirement has at least one test (no \"unverified\")", every_tested,
             f"{sum(tp['result'] != 'unverified' for tp in testpoints)}/{len(testpoints)} testpoints have tests"),
        line("regression", "Full regression passes (all tests, recorded seed)", full_pass if fm else None,
             (f"{fm['passed']}/{fm['total']} tests at the final attempt, random seed {seed or 'n/a'}" if fm
              else "final attempt not simulated")),
        line("mutation", "Mutation score 100% (no survivors)",
             (mutation["killed"] == mutation["injected"]) if mut_ok else None,
             f"{mutation['killed']}/{mutation['injected']} killed" if mut_ok else "no mutation check for this suite hash"),
        line("scenarios", "All defined scenarios hit at least once", (not scenarios["zero"]) if sc_ok else None,
             (f"{functional['hit']}/{functional['total']} scenarios hit" if sc_ok else "scenario counts not taken for this RTL")),
        line("suite", "Test suite unchanged since approval (suite hash matches)",
             (suite == pinned_suite and attempts_same_suite) if pinned_suite else None,
             ("run suite equals the current pin" if suite == pinned_suite
              else f"run used {str(suite)[:12]}…, current pin {str(pinned_suite)[:12]}… (suite changed after this run)")
             + ("" if attempts_same_suite else "; an attempt ran a different suite")),
    ]

    # 7. AI provenance.
    provenance = {
        "label": "AI interpretation · not verified (diagnoses); attempts, results and cost are measured",
        "providers": run.get("providers"),
        "models": sorted({a["model"] for a in attempts if a.get("model")}),
        "attempts": [{"n": a["n"], "source": a.get("source"), "model": a.get("model"), "status": a["status"],
                      "result": (lambda m: f"{m['passed']}/{m['total']}" if m else not_simulated(a))(resolve(run, a)),
                      "tokens_in": a.get("tokens_in"), "tokens_out": a.get("tokens_out"), "cost_usd": a.get("cost_usd")}
                     for a in attempts],
        "diagnoses": [{"attempt": a["n"], "model": a.get("model"),
                       "text": (a.get("ai_interpretation") or {}).get("diagnosis")}
                      for a in attempts if (a.get("ai_interpretation") or {}).get("diagnosis")],
        "cost_usd": run.get("cost_usd"),
        "tokens": run.get("tokens"),
    }
    plan = {
        "label": MEASURED,
        "title": f"Verification plan · {reqs.get('block', 'design')} · {run['run_id']}",
        "generator": "verify/plan.py",
        "format": "Vplan sections (ChipVerify) · OpenTitan testpoint fields · OpenTitan-style staged sign-off",
        "date": (run.get("started") or "")[:10] or None,
        "spec": spec,
        "random_seed": seed,
        "scope": {"in": f"functional behaviour of {reqs.get('block', 'the block')} per {(spec or {}).get('file') or 'the spec'}",
                  "out": OUT_OF_SCOPE},
        "methodology": [
            "cycle-accurate Python reference model compared on every clock (scoreboard)",
            "directed tests per requirement",
            f"constrained-random regression, 3000 cycles, seed {seed or 'recorded in the test file'}",
            "mutation analysis with hand-written mutants to measure test strength",
            "tests frozen and hash-pinned before RTL generation; the AI may only change RTL",
            "parameter sweep at other WIDTH/DEPTH/AF_THRESH sets, never shown to the model",
        ],
        "testpoints": testpoints,
        "coverage_summary": coverage_summary,
        "signoff": signoff,
        "provenance": provenance,
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


def hits_text(h) -> str:
    if isinstance(h, dict):
        return ", ".join(f"{k} {n}" + (" ✕" if n == 0 else "") for k, n in h.items())
    return str(h)


def markdown(p: dict) -> str:
    src, run, spec = p["sources"], p["run"], p.get("spec") or {}
    out = [f"# {p['title']}", "",
           "Every result below is **measured** from stored simulator output, except the golden model's expected "
           "values (the reference) and the diagnoses in §7, which are labelled *AI interpretation · not verified*. "
           "Anything not measured says so.", "",
           f"Format: {p['format']}.", "",
           "## 1. Header", "", "| | |", "| --- | --- |",
           f"| Block | `{src['block']}` · {', '.join(f'{k}={v}' for k, v in (src['params'] or {}).items())} |",
           f"| Spec | `{spec.get('file') or '—'}` · sha256 `{spec.get('sha256') or '—'}`"
           + ("" if spec.get("matches_run", True) else " · ○ the current file differs from the spec this run recorded") + " |",
           f"| Frozen suite | `{src['suite_sha256'] or '—'}` |",
           f"| Simulator | {src['simulator'] or '—'} |",
           f"| Date | {p.get('date') or '—'} |",
           f"| Run | `{run['run_id']}` · status `{run['status']}` · attempts {run['attempts_total']} |"]
    if run.get("seed_bug"):
        out.append(f"| Seeded bug | {run['seed_bug']} (attempt 1 is the seeded RTL, not model output) |")
    if run.get("replayed_from"):
        out.append(f"| Replay of | `{run['replayed_from']}` |")
    for k, name in (("sweep_sha256", "Parameter sweep"), ("requirements_sha256", "Requirements"),
                    ("mutants_sha256", "Mutant set"), ("final_rtl_sha256", "Final RTL")):
        out.append(f"| {name} | `{src[k]}` |" if src[k] else f"| {name} | — |")
    warnings = []
    if not src["requirements_match_run"]:
        warnings.append("The requirements file differs from the one this run used.")
    if not src["mutation_suite_matches"]:
        warnings.append("The stored mutation check used a different frozen suite; mutant results are shown as unknown.")
    if p.get("not_verifiable"):
        warnings.append("Not verifiable by this suite: " + "; ".join(p["not_verifiable"]))
    if warnings:
        out += ["", *[f"> ○ {w}" for w in warnings]]

    out += ["", "## 2. Scope", "", f"- **In scope:** {p['scope']['in']}.",
            "- **Out of scope:** " + "; ".join(p["scope"]["out"]) + "."]
    out += ["", "## 3. Methodology", "", *[f"- {m}" for m in p["methodology"]]]

    out += ["", "## 4. Testpoints", "",
            "Milestones: **V1** reset and basic flags · **V2** corner cases (full with read/write, wraparound, "
            "overflow/underflow). Result is the final attempt; a different attempt-1 result is noted.", ""]
    ex = src.get("extraction")
    if ex:
        out += [f"Requirements come from approved extraction `{ex['extraction_id']}` (approved by {ex['approved_by']}). "
                "The link from each item to a REQ (`EX-nn → REQ-nn`) was proposed by the model "
                "(AI interpretation · not verified) and approved with the list; test results are measured.", ""]
    out += ["| ID | Name | MS | Goal · stimulus · check | Tests | Result | Mutants | Scenario hits |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for tp, r in zip(p["testpoints"], p["requirements"]):
        rid = f"{tp['id']} → {r['maps_to']}" if r.get("maps_to") else tp["id"]
        d = tp["desc"]
        res = MARK.get(tp["result"], tp["result"])
        if tp["result_attempt_1"] in ("pass", "fail") and tp["result_attempt_1"] != tp["result"]:
            res += f" (attempt 1: {MARK[tp['result_attempt_1']]})"
        muts = "<br>".join(f"{m['id']} {MARK.get(m['result'], m['result'])}" for m in tp["mutants"]) or "—"
        tests = "<br>".join(f"`{t}`" for t in tp["tests"]) or "—"
        out.append(f"| {rid} | `{tp['name']}` | {tp['milestone']} | **Goal:** {d['goal']}<br>**Stimulus:** {d['stimulus']}"
                   f"<br>**Check:** {d['check']} | {tests} | {res} | {muts} | {hits_text(tp['scenario_hits'])} |")
    rr = p["random_regression"]
    out += ["", f"`{rr['test']}` (3000 random cycles, seed {p.get('random_seed') or 'n/a'}) covers "
            f"{', '.join(rr['covers'])}; a test shared by several requirements marks each of them. "
            f"Attempt 1: {cell(rr['attempt_1'])} · final: {cell(rr['final'])}."]

    cs = p["coverage_summary"]
    out += ["", "## 5. Coverage summary", ""]
    f = cs["functional"]
    if isinstance(f, dict):
        out.append(f"- **Functional (scenario) coverage:** {f['hit']}/{f['total']} scenarios hit; at 0 hits: "
                   f"{', '.join(f['zero']) or 'none'}" + (" (partial: the suite did not pass on this RTL)" if f["partial"] else ""))
    else:
        out.append(f"- **Functional (scenario) coverage:** {NOT_MEASURED}")
    m = cs["mutation"]
    if isinstance(m, dict):
        surv = ", ".join(f"{x['id']} ({x['req']})" for x in m["survivors"]) or "none"
        out.append(f"- **Mutation score:** {m['killed']}/{m['injected']} killed; survivors: {surv} "
                   "(hand-written mutants in the reference RTL; describes the suite, not this RTL)")
    else:
        out.append(f"- **Mutation score:** {NOT_MEASURED}")
    out.append(f"- **Code coverage:** {cs['code']}.")
    sc = p["scenarios"]
    if sc:
        out += ["", f"### 5.1 Scenario counts (final RTL, {sc['cycles']} cycles, `verify/coverage.py`)", "",
                "| Scenario | Count |", "| --- | --- |"]
        for k, n in sc["counts"].items():
            out.append(f"| {sc['descriptions'][k]} | {n}{'  ○ never reached' if n == 0 else ''} |")
    w = p["weak_test_check"]
    if w:
        dropped = ", ".join(f"`{t}`" for t in w["tests_dropped"])
        out += ["", "### 5.2 Weak-test check", "",
                f"With {dropped} left out, {w['weak']['killed']}/{w['weak']['injected']} killed "
                f"(survivors: {', '.join(w['weak']['survivors']) or 'none'}); restored suite "
                f"{w['restored']['killed']}/{w['restored']['injected']}."]
    gp = p["gaps"]
    if gp:
        sm = gp["summary"]
        out += ["", "### 5.3 Test-plan gaps (mutation analysis with tests left out)", "",
                f"- Mutants caught by only one directed test: {', '.join(sm['fragile']) or 'none'}",
                f"- Mutants caught only by the random regression: {', '.join(sm['random_only']) or 'none'}",
                f"- Requirements no mutant targets: {', '.join(sm['requirements_without_mutant']) or 'none'}",
                f"- {gp['drops_total']} suites re-simulated with tests left out; prediction from the full run's killers "
                f"{'matched every one' if sm['all_predictions_match'] else 'did NOT match'}."]
        for d in gp["drops_with_survivors"]:
            left = ", ".join(f"`{t}`" for t in d["dropped"])
            out.append(f"- Without {left}: {d['killed']}/{d['injected']} killed, ✕ {', '.join(d['survivors'])} survive")

    out += ["", "## 6. Sign-off status", "",
            "DaVINCI-scaled, modelled on OpenTitan's V2 checklist. Each line is met / not met from stored data, "
            "or not measured.", "", "| Criterion | Status | Evidence |", "| --- | --- | --- |"]
    sign = {"met": "✓ met", "not met": "✕ not met", NOT_MEASURED: "○ not measured"}
    for item in p["signoff"]:
        out.append(f"| {item['criterion']} | {sign[item['status']]} | {item['evidence']} |")
    g = p["gates"]
    out += ["", "Run gates at the final attempt: "
            f"**G1** static checks + `iverilog -g2001 -Wall` {cell(g['G1_static_and_compile'])} · "
            f"**G2** frozen suite {cell(g['G2_frozen_suite'])} · "
            f"**G3** parameter sweep (never shown to the model) {cell(g['G3_parameter_sweep'])}."]

    pv = p["provenance"]
    prov = pv.get("providers") or {}
    tokens = pv.get("tokens")
    tok_total = f" · {tokens['in']:,} in / {tokens['out']:,} out tokens" if tokens else ""
    out += ["", "## 7. AI provenance", "",
            f"Model(s): {', '.join(pv['models']) or 'none (no model call)'} · providers: generate "
            f"`{prov.get('generate', '—')}`, repair `{prov.get('repair', '—')}` · total cost "
            f"${(pv.get('cost_usd') or 0):.4f}{tok_total} (measured, from the ledger).",
            "", "| # | Source | Model | Status | Frozen suite | Tokens in/out | Cost |",
            "| --- | --- | --- | --- | --- | --- | --- |"]
    for a in pv["attempts"]:
        tok = f"{a['tokens_in']:,}/{a['tokens_out']:,}" if a.get("tokens_in") is not None else "—"
        cost = f"${a['cost_usd']:.4f}" if a.get("cost_usd") is not None else "—"
        out.append(f"| {a['n']} | {a['source']} | {a['model'] or '—'} | {a['status']} | {a['result']} | {tok} | {cost} |")
    if pv["diagnoses"]:
        out += ["", "Diagnoses (*AI interpretation · not verified*):", ""]
        for d in pv["diagnoses"]:
            out += [f"> **Attempt {d['attempt']} · {d['model']}:** {d['text']}", ">"]
        out.pop()
    return "\n".join(out) + "\n"


CSV_FIELDS = ["id", "name", "milestone", "goal", "stimulus", "check", "tests", "result", "result_attempt_1",
              "mutants", "scenario_hits"]


def testpoints_csv(p: dict) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_FIELDS, lineterminator="\n")
    w.writeheader()
    for tp in p["testpoints"]:
        w.writerow({"id": tp["id"], "name": tp["name"], "milestone": tp["milestone"], **tp["desc"],
                    "tests": " ".join(tp["tests"]), "result": tp["result"], "result_attempt_1": tp["result_attempt_1"],
                    "mutants": " ".join(f"{m['id']}:{m['result']}" for m in tp["mutants"]),
                    "scenario_hits": hits_text(tp["scenario_hits"])})
    return buf.getvalue()


def testplan_hjson(p: dict) -> str:
    """OpenTitan-like testplan: testpoints (name, milestone, desc, tests) and the
    scenario counters as covergroups. Strings are JSON-quoted, which Hjson accepts."""
    def q(v):
        return json.dumps(v, ensure_ascii=False)
    out = [f"// {p['title']}", "// Generated by verify/plan.py from stored files; results are in verification_plan.json.",
           "{", f"  name: {q(p['sources']['block'])}", "  testpoints: ["]
    for tp in p["testpoints"]:
        d = tp["desc"]
        desc = f"{tp['id']}. Goal: {d['goal']} Stimulus: {d['stimulus']}. Check: {d['check']}."
        out += ["    {", f"      name: {q(tp['name'])}", f"      milestone: {q(tp['milestone'])}",
                f"      desc: {q(desc)}", f"      tests: [{', '.join(q(t) for t in tp['tests'])}]", "    }"]
    out += ["  ]", "  covergroups: ["]
    sc = p["scenarios"]
    if sc:
        for k, text in sc["descriptions"].items():
            out += ["    {", f"      name: {q(k + '_cg')}",
                    f"      desc: {q(text + ' (scenario counter from the simulator waveform, verify/coverage.py)')}", "    }"]
    out += ["  ]", "}"]
    return "\n".join(out) + "\n"


def suite_tests(canonical: dict) -> list[str]:
    return sorted({t for r in canonical["requirements"] for t in r["tests"]})


def write(plan: dict, out_dir: Path):
    (out_dir / "verification_plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    (out_dir / "verification_plan.md").write_text(markdown(plan))
    (out_dir / "verification_plan.csv").write_text(testpoints_csv(plan))
    (out_dir / "testplan.hjson").write_text(testplan_hjson(plan))


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
    spec_path = ROOT / (run.get("spec_file") or "spec/fifo_spec.md")
    if not spec_path.exists():
        spec_path = ROOT / "spec" / "fifo_spec.md"
    spec_sha = sha256(spec_path.read_bytes())
    spec = {"file": spec_path.relative_to(ROOT).as_posix() if spec_path.is_relative_to(ROOT) else spec_path.name,
            "sha256": run.get("spec_sha256") or spec_sha, "matches_run": run.get("spec_sha256") in (None, spec_sha)}
    docs, seed = test_facts((ROOT / "tests" / "test_sync_fifo.py").read_text())
    return build(run, json.loads(raw), suite_tests(canonical),
                 json.loads((ROOT / "verify" / "mutants.json").read_text()),
                 load(ROOT / "runs" / "mutation" / "mutation.json"),
                 load(ROOT / "runs" / "weak_demo" / "weak_demo.json"), sha256(raw),
                 load(ROOT / "runs" / "coverage_gap" / "gaps.json"),
                 load(run_dir / "coverage" / "coverage.json"),
                 (ROOT / "verify" / "coverage.sha256").read_text().strip(),
                 spec=spec, test_docs=docs, seed=seed,
                 pinned_suite=(ROOT / "verify" / "suite.sha256").read_text().strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--reference", action="store_true", help="run_dir holds make plan-ref's verdict.json")
    a = ap.parse_args()
    write(plan_for(a.run_dir, a.reference), a.run_dir)
    print(f"wrote {a.run_dir}/verification_plan.md, .json, .csv and testplan.hjson")


if __name__ == "__main__":
    main()
