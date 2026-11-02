// Run data model shared by the static pages (read from evidence/ at build time)
// and the live pages (read from the API in the browser). No file-system access.
export type Json = Record<string, any>;

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
  compileOutput?: string;
  measuredError?: string;
  sameAs?: number; // no_progress: same design as this attempt
  finishReason?: string;
  rtl?: string;
  prompt?: Json[]; // messages sent to the model
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
  handoff?: Json;
  notVerifiable?: string[];
};

export type AttemptFiles = {
  verdict: (n: number) => Json | null;
  rtl?: (n: number) => string | null;
  prompt?: (n: number) => Json[] | null;
};

// run.json (+ per-attempt files) → Run.
export function toRun(r: Json, files: AttemptFiles): Run {
  const attempts: Attempt[] = r.attempts.map((a: Json) => {
    const v = files.verdict(a.n);
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
      compileOutput: a.measured_compile?.output,
      measuredError: a.measured?.error,
      sameAs: a.measured?.same_as_attempt,
      finishReason: a.finish_reason,
      rtl: files.rtl?.(a.n) ?? undefined,
      prompt: files.prompt?.(a.n) ?? undefined,
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
    handoff: r.handoff,
    notVerifiable: r.not_verifiable,
  };
}

export type Requirement = { id: string; text: string; tests: string[] };

// "Icarus Verilog version 13.0 (stable) (v13_0)" → "Icarus 13.0".
export const simShort = (v?: string | null) =>
  v ? v.replace(/^Icarus Verilog version ([\d.]+).*$/, "Icarus $1") : "n/a";

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

// Per-cycle simulation trace (verify/trace.py). `exp` is the golden model; the rest is measured.
export type TraceCycle = {
  k: number;
  t_ns: number;
  in: Record<string, number | null>;
  out: Record<string, number | null>;
  exp: Record<string, number>;
  mismatch: string[];
  ptr?: { wr_ptr?: number | null; rd_ptr?: number | null };
};
export type TraceTest = { name: string; passed: boolean; message: string; cycles_total: number; first_mismatch: number | null; truncated: boolean; cycles: TraceCycle[] };
export type Trace = { label: string; status: string; suite_sha256: string; simulator: string; params: { WIDTH: number; DEPTH: number; AF_THRESH: number }; tests: TraceTest[] };
