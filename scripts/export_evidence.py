"""Export a committed, self-contained evidence bundle for the Evidence Board.

For each named live run, copies the run and its most recent replay that was
checked against the current pinned suite and sweep (so today's gates are shown
next to what happened live), plus the mutation check, the weak-test demo, the
coverage-gap check, the requirement and interface files, a verification plan
(with scenario counts where taken) per run and for the reference RTL, and a ledger summary. Absolute paths are
rewritten relative to the repo; no secrets are read. Ends with MANIFEST.sha256.

usage: python scripts/export_evidence.py live01 live02-m1 live03-pdf [--out evidence]
"""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verify"))
import plan  # noqa: E402
RUNS = ROOT / "runs"
LIVE = {"meta", "baseten"}
ATTEMPT_FILES = ["prompt.json", "response.md", "sync_fifo.v", "sim/verdict.json", "sweep/sweep.json"]


def scrub(text: str) -> str:
    return text.replace(str(ROOT) + "/", "").replace(str(ROOT), ".")


def copy_text(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(scrub(src.read_text()))


def latest_replay(source: str, suite: str, sweep: str) -> str | None:
    best = None
    for d in RUNS.glob(f"{source}-replay*"):
        f = d / "run.json"
        if not f.exists():
            continue
        r = json.loads(f.read_text())
        if r.get("replayed_from") == source and r.get("suite_sha256") == suite and r.get("sweep_sha256") == sweep:
            if best is None or r["started"] > best[0]:
                best = (r["started"], d.name)
    return best[1] if best else None


def export_run(run_id: str, out: Path) -> dict:
    src, dst = RUNS / run_id, out / "runs" / run_id
    for name in ("run.json", "calls.jsonl", "events.jsonl"):
        if (src / name).exists():
            copy_text(src / name, dst / name)
    r = json.loads((src / "run.json").read_text())
    if (src / "coverage" / "coverage.json").exists():
        copy_text(src / "coverage" / "coverage.json", dst / "coverage" / "coverage.json")
    for a in r["attempts"]:
        for f in ATTEMPT_FILES:
            p = src / f"attempt_{a['n']}" / f
            if p.exists():
                copy_text(p, dst / f"attempt_{a['n']}" / f)
    return r


def summary(r: dict) -> dict:
    return {k: r.get(k) for k in ("run_id", "status", "started", "providers", "seed_bug", "replayed_from",
                                  "attempts_total", "attempts_to_green", "time_to_green_s", "cost_usd",
                                  "suite_sha256", "sweep_sha256")} | {"from_extraction": bool(r.get("extraction"))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("live", nargs="+", help="live run ids to export")
    ap.add_argument("--out", type=Path, default=ROOT / "evidence")
    a = ap.parse_args()
    out = a.out.resolve()
    entries = [json.loads(l) for l in (RUNS / "_ledger.jsonl").read_text().splitlines() if l.strip()]
    live = [e for e in entries if e["provider"] in LIVE]
    # A live run is one the ledger shows a live provider actually answering
    # (tokens returned); a test double that only claims a live provider is not.
    for run_id in a.live:
        if not (RUNS / run_id / "run.json").exists():
            raise SystemExit(f"no run {run_id}")
        if not any(e.get("run_id") == run_id and e.get("status") == "ok" and (e.get("tokens_out") or 0) > 0
                   for e in live):
            raise SystemExit(f"{run_id}: no answered live model call in the ledger; refusing to export it as live")
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    suite = (ROOT / "verify" / "suite.sha256").read_text().strip()
    sweep = (ROOT / "verify" / "sweep.sha256").read_text().strip()

    index = {"pinned_suite_sha256": suite, "pinned_sweep_sha256": sweep, "runs": []}
    for run_id in a.live:
        r = export_run(run_id, out)
        entry = {"live": summary(r), "replay": None}
        rep = latest_replay(run_id, suite, sweep)
        if rep:
            entry["replay"] = summary(export_run(rep, out))
        if r.get("extraction"):
            xid = r["extraction"]["extraction_id"]
            for name in ("approved.json", "interface_spec.md"):
                p = RUNS / "_extract" / xid / name
                if p.exists():
                    copy_text(p, out / "extractions" / xid / name)
        index["runs"].append(entry)
        print(f"{run_id}: {r['status']} · current-gates replay: {rep or 'none'}")

    for name, src in (("mutation.json", RUNS / "mutation" / "mutation.json"),
                      ("weak_demo.json", RUNS / "weak_demo" / "weak_demo.json"),
                      ("gaps.json", RUNS / "coverage_gap" / "gaps.json"),
                      ("requirements.json", ROOT / "spec" / "requirements.json"),
                      ("interface.json", ROOT / "spec" / "interface.json"),
                      ("mutants.json", ROOT / "verify" / "mutants.json")):
        copy_text(src, out / name)

    # Verification plans, built from the same stored files (deterministic).
    exported_ids = [x["run_id"] for e in index["runs"] for x in (e["live"], e["replay"]) if x]
    for run_id in exported_ids:
        p = plan.plan_for(RUNS / run_id)
        plan.write(json.loads(scrub(json.dumps(p))), out / "runs" / run_id)
    if (RUNS / "reference" / "verdict.json").exists():
        (out / "reference").mkdir()
        if (RUNS / "reference" / "coverage" / "coverage.json").exists():
            copy_text(RUNS / "reference" / "coverage" / "coverage.json", out / "reference" / "coverage" / "coverage.json")
        plan.write(json.loads(scrub(json.dumps(plan.plan_for(RUNS / "reference", reference=True)))), out / "reference")
        index["reference_plan"] = True
    else:
        print("no runs/reference/verdict.json: run `make plan-ref` to include the reference plan")
        index["reference_plan"] = False

    exported = {e["live"]["run_id"] for e in index["runs"]}
    index["ledger"] = {
        "label": "measured",
        "live_calls_total": len(live),
        "live_calls_ok": sum(e.get("status") == "ok" for e in live),
        "live_spend_usd_total": round(sum(float(e.get("cost_usd") or 0) for e in live), 6),
        "exported_run_calls": [{k: e.get(k) for k in ("ts", "run_id", "step", "provider", "model", "status",
                                                      "tokens_in", "tokens_out", "cost_usd", "seconds")}
                               for e in live if e.get("run_id") in exported],
    }
    (out / "index.json").write_text(json.dumps(index, indent=2))

    lines = []
    for f in sorted(p for p in out.rglob("*") if p.is_file()):
        lines.append(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.relative_to(out).as_posix()}")
    (out / "MANIFEST.sha256").write_text("\n".join(lines) + "\n")
    print(f"wrote {len(lines)} files to {out.relative_to(ROOT)} (live spend to date ${index['ledger']['live_spend_usd_total']})")


if __name__ == "__main__":
    main()
