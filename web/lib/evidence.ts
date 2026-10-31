// Build-time reader for the committed evidence/ bundle. Every number the board
// shows comes from these files; nothing is computed from model text.
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(process.cwd(), "..", "evidence");

type Json = Record<string, any>;

function read(rel: string): Json | null {
  const f = path.join(ROOT, rel);
  return fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, "utf8")) : null;
}

export type TestResult = { name: string; passed: boolean; message: string };

export type Attempt = {
  n: number;
  source: "model" | "seeded";
  status: string;
  model?: string;
  tokensIn?: number;
  tokensOut?: number;
  costUsd?: number;
  modelSeconds?: number;
  seeded?: { mutant: string; req: string; desc: string };
  passed?: number;
  total?: number;
  tests: TestResult[]; // per-test results from the attempt's verdict.json
  simulator?: string;
  suiteSha?: string;
  rejection?: string;
  diagnosis?: string; // AI interpretation, never a verdict
  diff?: string;
  compileOk?: boolean;
  sweep?: { status: string; sets: { params: Json; status: string; passed: number; total: number }[] };
};

export type Run = {
  id: string;
  status: string;
  started: string;
  providers: { generate: string; repair: string };
  seedBug: string | null;
  replayedFrom: string | null;
  attemptsTotal: number;
  attemptsToGreen: number | null;
  timeToGreenS: number | null;
  costUsd: number;
  tokens: { in: number; out: number };
  suiteSha: string;
  sweepSha?: string;
  sandbox?: { backend: string; image_id: string | null };
  extraction?: Json;
  replayCheck?: { reproduced: boolean; attempts: Json[] };
  attempts: Attempt[];
};

function loadRun(id: string): Run {
  const r = read(`runs/${id}/run.json`);
  if (!r) throw new Error(`evidence missing run ${id}`);
  const attempts: Attempt[] = r.attempts.map((a: Json) => {
    const v = read(`runs/${id}/attempt_${a.n}/sim/verdict.json`);
    return {
      n: a.n,
      source: a.source,
      status: a.status,
      model: a.model,
      tokensIn: a.tokens_in,
      tokensOut: a.tokens_out,
      costUsd: a.cost_usd,
      modelSeconds: a.model_seconds,
      seeded: a.seeded,
      passed: a.measured?.passed,
      total: a.measured?.total,
      tests: (v?.tests ?? []) as TestResult[],
      simulator: a.measured?.simulator,
      suiteSha: a.measured?.suite_sha256,
      rejection: a.measured?.rejection,
      diagnosis: a.ai_interpretation?.diagnosis,
      diff: a.diff_vs_prev,
      compileOk: a.measured_compile?.ok,
      sweep: a.sweep,
    };
  });
  return {
    id: r.run_id,
    status: r.status,
    started: r.started,
    providers: r.providers,
    seedBug: r.seed_bug,
    replayedFrom: r.replayed_from,
    attemptsTotal: r.attempts_total,
    attemptsToGreen: r.attempts_to_green,
    timeToGreenS: r.time_to_green_s,
    costUsd: r.cost_usd,
    tokens: r.tokens,
    suiteSha: r.suite_sha256,
    sweepSha: r.sweep_sha256,
    sandbox: r.sandbox,
    extraction: r.extraction,
    replayCheck: r.replay_check,
    attempts,
  };
}

export type Requirement = { id: string; text: string; tests: string[] };
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
    pinnedSuite: idx.pinned_suite_sha256,
    pinnedSweep: idx.pinned_sweep_sha256,
    ledger: {
      liveCallsTotal: idx.ledger.live_calls_total,
      liveCallsOk: idx.ledger.live_calls_ok,
      liveSpendUsd: idx.ledger.live_spend_usd_total,
    },
  };
}

// Status words and symbols. Colour is never the only signal.
export const STATUS: Record<string, { word: string; mark: string; tone: "pass" | "fail" | "neutral" }> = {
  pass: { word: "Pass", mark: "✓", tone: "pass" },
  fail: { word: "Fail", mark: "✕", tone: "fail" },
  escaped: { word: "Escaped", mark: "✕", tone: "fail" },
  needs_engineer: { word: "Needs engineer", mark: "✕", tone: "fail" },
  no_progress: { word: "No progress", mark: "✕", tone: "fail" },
  aborted: { word: "Aborted", mark: "○", tone: "neutral" },
  not_verifiable: { word: "Not verifiable", mark: "○", tone: "neutral" },
  rejected: { word: "Rejected", mark: "✕", tone: "fail" },
  truncated: { word: "Truncated", mark: "○", tone: "neutral" },
  compile_error: { word: "Compile error", mark: "✕", tone: "fail" },
  timeout: { word: "Timeout", mark: "✕", tone: "fail" },
  sim_error: { word: "Simulator error", mark: "✕", tone: "fail" },
};

export const status = (s: string) => STATUS[s] ?? { word: s, mark: "○", tone: "neutral" as const };
