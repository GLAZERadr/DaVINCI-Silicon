// Build-time reader for the committed evidence/ bundle. Every number the board
// shows comes from these files; nothing is computed from model text.
import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { type Json, type Requirement, type Run, toRun } from "./run";

export * from "./run";

const ROOT = path.resolve(process.cwd(), "..", "evidence");

function read(rel: string): Json | null {
  const f = path.join(ROOT, rel);
  return fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, "utf8")) : null;
}

function loadRun(id: string): Run {
  const r = read(`runs/${id}/run.json`);
  if (!r) throw new Error(`evidence missing run ${id}`);
  const text = (rel: string) => {
    const f = path.join(ROOT, rel);
    return fs.existsSync(f) ? fs.readFileSync(f, "utf8") : null;
  };
  return toRun(r, {
    verdict: (n) => read(`runs/${id}/attempt_${n}/sim/verdict.json`),
    rtl: (n) => text(`runs/${id}/attempt_${n}/sync_fifo.v`),
    prompt: (n) => read(`runs/${id}/attempt_${n}/prompt.json`) as Json[] | null,
    recheck: (n) => read(`runs/${id}/attempt_${n}/g1_recheck.json`),
  });
}

export function run(id: string): Run {
  return loadRun(id);
}

export type Mutant = { id: string; req: string; desc: string; result: string; killed_by: string[] };

export type Board = {
  live: Run;
  replay: Run | null; // same recorded model output, re-checked under today's gates
  requirements: Requirement[];
  mutation: { killed: number; injected: number; label: string; matchesPin: boolean; mutants: Mutant[] };
  weakDemo: Json | null;
  pinnedSuite: string;
  pinnedSweep: string;
  ledger: { liveCallsTotal: number; liveCallsOk: number; liveSpendUsd: number };
  planId: string | null; // run whose verification plan is linked (the replay when there is one)
  referencePlan: boolean;
  scenarios: Json | null; // scenario counts from the linked plan (already checked against pins there)
  signoff: Json[] | null; // sign-off lines from the linked plan (met / not met / not measured)
  triage: Json | null; // test credibility (verify/triage.py)
  breakdown: { approved: Json; check: Json | null; model?: string } | null; // S1, when the run used one
  gaps: Json | null; // coverage-gap check (verify/gaps.py), only when measured on the pinned suite
  area: Area | null; // S2: Yosys generic cell counts (verify/area.py), when stored
  formal: { run: Json | null; reference: Json | null }; // S5/S9 formal checks (verify/formal.py), when stored
  physical: Physical | null; // S6/S10 summaries (verify/sta.py, verify/layout.py), only when stored
};

// S6 pre-layout (sta/sta.json) and S10 post-layout (layout/summary.json): reference RTL vs this run's final RTL.
export type Physical = { runId: string; staRef: Json | null; staFinal: Json | null; layoutRef: Json | null; layoutFinal: Json | null };

function physical(id: string, replayId?: string): Physical | null {
  const pick = (f: string) => read(`runs/${id}/${f}`) ?? (replayId ? read(`runs/${replayId}/${f}`) : null);
  const p = { runId: id, staRef: read("reference/sta/sta.json"), staFinal: pick("sta/sta.json"),
              layoutRef: read("reference/layout/summary.json"), layoutFinal: pick("layout/summary.json") };
  return p.staRef || p.staFinal || p.layoutRef || p.layoutFinal ? p : null;
}

export type RunSummary = { id: string; status: string; seedBug: string | null; fromExtraction: boolean };

export function index() {
  const idx = read("index.json");
  if (!idx) throw new Error("evidence/index.json missing: run `make evidence`");
  return idx;
}

export function runList(): RunSummary[] {
  return index().runs.map((e: Json) => ({
    id: e.live.run_id,
    status: (e.replay ?? e.live).status,
    seedBug: e.live.seed_bug,
    fromExtraction: e.live.from_extraction,
  }));
}

export function board(id: string): Board {
  const idx = index();
  const entry = idx.runs.find((e: Json) => e.live.run_id === id);
  if (!entry) throw new Error(`run ${id} is not in the evidence bundle`);
  const m = read("mutation.json")!;
  const planId = [entry.replay?.run_id, id].find((r) => r && fs.existsSync(path.join(ROOT, "runs", r, "verification_plan.md"))) ?? null;
  return {
    live: loadRun(id),
    replay: entry.replay ? loadRun(entry.replay.run_id) : null,
    requirements: read("requirements.json")!.requirements,
    mutation: {
      killed: m.killed,
      injected: m.injected,
      label: m.label,
      matchesPin: m.suite_sha256 === idx.pinned_suite_sha256,
      mutants: m.mutants,
    },
    weakDemo: read("weak_demo.json"),
    gaps: (() => { const g = read("gaps.json"); return g && g.suite_sha256 === idx.pinned_suite_sha256 ? g : null; })(),
    referencePlan: fs.existsSync(path.join(ROOT, "reference", "verification_plan.md")),
    planId,
    scenarios: planId ? read(`runs/${planId}/verification_plan.json`)?.scenarios ?? null : null,
    signoff: planId ? read(`runs/${planId}/verification_plan.json`)?.signoff ?? null : null,
    triage: read("triage.json"),
    area: area([entry.replay?.run_id, id]),
    breakdown: (() => {
      const approved = read(`runs/${id}/breakdown.json`);
      if (!approved) return null;
      const check = read(`runs/${entry.replay?.run_id ?? id}/breakdown_check.json`) ?? read(`runs/${id}/breakdown_check.json`);
      return { approved, check, model: read(`runs/${id}/run.json`)?.attempts?.find((a: Json) => a.model)?.model };
    })(),
    formal: {
      run: read(`runs/${id}/formal/formal.json`) ?? (entry.replay ? read(`runs/${entry.replay.run_id}/formal/formal.json`) : null),
      reference: read("reference/formal/formal.json"),
    },
    physical: physical(id, entry.replay?.run_id),
    pinnedSuite: idx.pinned_suite_sha256,
    pinnedSweep: idx.pinned_sweep_sha256,
    ledger: {
      liveCallsTotal: idx.ledger.live_calls_total,
      liveCallsOk: idx.ledger.live_calls_ok,
      liveSpendUsd: idx.ledger.live_spend_usd_total,
    },
  };
}

// The requirements a run was generated against: its approved extraction, or the default list.
export function requirementsFor(r: Run): Requirement[] {
  const xid = r.extraction?.extraction_id;
  const approved = xid ? read(`extractions/${xid}/approved.json`) : null;
  return (approved ?? read("requirements.json")!).requirements;
}

export function mutants(): { id: string; req: string; desc: string }[] {
  return (read("mutants.json") as unknown as Json[]).map((m) => ({ id: m.id, req: m.req, desc: m.desc }));
}

export function triage(): Json | null {
  return read("triage.json");
}

export function defaultRequirements(): Requirement[] {
  return read("requirements.json")!.requirements;
}

// The live run and its current-gates replay, for the Run Console.
export function consoleRuns(id: string): { label: string; run: Run }[] {
  const entry = index().runs.find((e: Json) => e.live.run_id === id);
  if (!entry) throw new Error(`run ${id} is not in the evidence bundle`);
  const out = [{ label: "Original live run", run: loadRun(id) }];
  if (entry.replay) out.push({ label: "Re-checked today (replay)", run: loadRun(entry.replay.run_id) });
  return out;
}

// Per-cycle traces (verify/trace.py), served as /traces/<run>__<attempt>.json.
export function traceFiles(): string[] {
  const idx = index();
  const ids: string[] = idx.runs.flatMap((e: Json) => [e.live.run_id, e.replay?.run_id].filter(Boolean));
  return ids.flatMap((id) => {
    const dir = path.join(ROOT, "runs", id);
    return fs.existsSync(dir) ? fs.readdirSync(dir).filter((d) => /^attempt_\d+$/.test(d))
      .filter((d) => fs.existsSync(path.join(dir, d, "trace", "trace.json")))
      .map((d) => `${id}__${d.slice(8)}.json`) : [];
  });
}

export function traceText(file: string): string {
  const m = file.match(/^(.+)__(\d+)\.json$/);
  if (!m || !traceFiles().includes(file)) throw new Error(`no trace ${file}`);
  return fs.readFileSync(path.join(ROOT, "runs", m[1], `attempt_${m[2]}`, "trace", "trace.json"), "utf8");
}

// Verification plans (made by verify/plan.py at export), served as /plans/<id>.md and .json.
function planDir(id: string) {
  return id === "reference" ? path.join(ROOT, "reference") : path.join(ROOT, "runs", id);
}

// Plan outputs per run: <id>.md, .json, .csv (testpoints) and .hjson (OpenTitan-style testplan).
const PLAN_FILE: Record<string, string> = { md: "verification_plan.md", json: "verification_plan.json",
                                           csv: "verification_plan.csv", hjson: "testplan.hjson" };

// Everything the in-app plan viewer needs for a run (its linked plan) or for the reference RTL.
export function planBundle(id: string): { planId: string; plan: Json; csv: string; hjson: string } | null {
  let planId = id;
  if (id !== "reference") {
    const entry = index().runs.find((e: Json) => e.live.run_id === id);
    planId = [entry?.replay?.run_id, id].find((r) => r && fs.existsSync(path.join(planDir(r), PLAN_FILE.json))) ?? "";
  }
  const dir = planDir(planId);
  if (!planId || !fs.existsSync(path.join(dir, PLAN_FILE.json))) return null;
  const text = (f: string) => (fs.existsSync(path.join(dir, f)) ? fs.readFileSync(path.join(dir, f), "utf8") : "");
  return { planId, plan: JSON.parse(text(PLAN_FILE.json)), csv: text(PLAN_FILE.csv), hjson: text(PLAN_FILE.hjson) };
}

export function planFiles(): string[] {
  const idx = index();
  const ids = ["reference", ...idx.runs.flatMap((e: Json) => [e.live.run_id, e.replay?.run_id].filter(Boolean))];
  return ids.flatMap((id) => Object.entries(PLAN_FILE)
    .filter(([, f]) => fs.existsSync(path.join(planDir(id), f))).map(([ext]) => `${id}.${ext}`));
}

export function planText(file: string): string {
  if (!planFiles().includes(file)) throw new Error(`no plan ${file}`);
  const m = file.match(/^(.+)\.(md|json|csv|hjson)$/)!;
  return fs.readFileSync(path.join(planDir(m[1]), PLAN_FILE[m[2]]), "utf8");
}

// S2: generic Yosys cell / flip-flop counts (verify/area.py) for a run's final simulated RTL
// and the reference RTL. Shown only when the stored area.json is ok and its RTL hash matches
// the RTL in the bundle.
export type AreaCount = { cells: number; flops: number; yosys: string; kind: string; timing: string; power: string };
export type Area = { runId: string; final: AreaCount; reference: AreaCount | null };

function areaOk(a: Json | null): AreaCount | null {
  return a && a.status === "ok" && typeof a.cells === "number" && typeof a.flops === "number"
    ? { cells: a.cells, flops: a.flops, yosys: a.yosys, kind: a.kind, timing: a.timing, power: a.power }
    : null;
}

export function area(ids: (string | null | undefined)[]): Area | null {
  for (const id of ids) {
    if (!id) continue;
    const a = read(`runs/${id}/area/area.json`);
    const r = read(`runs/${id}/run.json`);
    const count = areaOk(a);
    if (!count || !r) continue;
    const last = [...r.attempts].reverse().find((x: Json) => ["pass", "fail"].includes(x.measured?.status));
    const f = last && path.join(ROOT, "runs", id, `attempt_${last.n}`, "sync_fifo.v");
    if (!f || !fs.existsSync(f)) continue;
    if (createHash("sha256").update(fs.readFileSync(f)).digest("hex") !== a!.rtl_sha256) continue;
    return { runId: id, final: count, reference: areaOk(read("reference/area/area.json")) };
  }
  return null;
}

