// Build-time reader for the committed evidence/ bundle. Every number the board
// shows comes from these files; nothing is computed from model text.
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
  gaps: Json | null; // coverage-gap check (verify/gaps.py), only when measured on the pinned suite
};

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

export function defaultRequirements(): Requirement[] {
  return read("requirements.json")!.requirements;
}

// The live run and its current-gates replay, for the Run Console.
export function consoleRuns(id: string): { label: string; run: Run }[] {
  const entry = index().runs.find((e: Json) => e.live.run_id === id);
  if (!entry) throw new Error(`run ${id} is not in the evidence bundle`);
  const out = [{ label: "Live run", run: loadRun(id) }];
  if (entry.replay) out.push({ label: "Replay · today's gates", run: loadRun(entry.replay.run_id) });
  return out;
}

// Verification plans (made by verify/plan.py at export), served as /plans/<id>.md and .json.
function planDir(id: string) {
  return id === "reference" ? path.join(ROOT, "reference") : path.join(ROOT, "runs", id);
}

export function planFiles(): string[] {
  const idx = index();
  const ids = ["reference", ...idx.runs.flatMap((e: Json) => [e.live.run_id, e.replay?.run_id].filter(Boolean))];
  return ids.filter((id) => fs.existsSync(path.join(planDir(id), "verification_plan.md")))
    .flatMap((id) => [`${id}.md`, `${id}.json`]);
}

export function planText(file: string): string {
  if (!planFiles().includes(file)) throw new Error(`no plan ${file}`);
  const id = file.replace(/\.(md|json)$/, "");
  return fs.readFileSync(path.join(planDir(id), `verification_plan.${file.endsWith(".md") ? "md" : "json"}`), "utf8");
}

