import type { Metadata } from "next";
import Landing, { type LandingData } from "@/components/Landing";
import { board, runList, traceFiles, traceText, type Trace } from "@/lib/evidence";

export const metadata: Metadata = { title: "DaVINCI Silicon · Verified RTL from a spec" };

// Landing page. Every number on it is read from the committed evidence/ bundle at build time.
export default function Home() {
  const runs = runList();
  const featured = runs.find((r) => r.seedBug) ?? runs[0];
  const b = board(featured.id);
  const failing = b.live.attempts.find((a) => a.status !== "pass");
  const fixed = b.live.attempts.find((a) => a.status === "pass");
  const firstFail = failing?.tests.find((t) => !t.passed);
  const data: LandingData = {
    runId: b.live.id,
    requirements: b.requirements.map((r) => ({ id: r.id, text: r.text, tests: r.tests })),
    mutants: b.mutation.mutants.map((m) => ({ id: m.id, req: m.req, desc: m.desc, killed: m.result === "killed" })),
    killed: b.mutation.killed,
    injected: b.mutation.injected,
    signoff: (b.signoff ?? []).map((s) => ({ criterion: String(s.criterion), status: String(s.status) })),
    liveRuns: runs.length,
    liveCalls: b.ledger.liveCallsTotal,
    spendUsd: b.ledger.liveSpendUsd,
    formal: b.formal.run ? { proved: b.formal.run.proved, total: b.formal.run.properties.length } : null,
    story: failing && fixed ? {
      seeded: failing.seeded?.mutant ?? null,
      failPassed: failing.passed ?? 0,
      total: failing.total ?? 0,
      failTest: firstFail?.name ?? "",
      failMessage: (firstFail?.message ?? "").split("\n")[0],
      diagnosis: fixed.diagnosis ?? null,
      model: fixed.model ?? "model",
      fixPassed: fixed.passed ?? 0,
      costUsd: b.live.costUsd,
      seconds: b.live.timeToGreenS,
    } : null,
  };
  // The failing test's waveform from attempt 1, as the Run Console shows it.
  const file = `${b.live.id}__${failing?.n ?? 1}.json`;
  if (traceFiles().includes(file) && firstFail) {
    const tr = JSON.parse(traceText(file)) as Trace;
    data.trace = { ...tr, tests: tr.tests.filter((x) => x.name === firstFail.name) };
  }
  const ph = b.physical;
  if (ph?.staRef && ph.staFinal) {
    const row = (s: typeof ph.staRef) => ({ area: s.synthesis.area_um2, fmax: s.timing.fmax_mhz, mw: s.power.total_w * 1000 });
    data.physical = { ref: row(ph.staRef), run: row(ph.staFinal), drcLvsClean: !!ph.layoutFinal && ["magic_drc_errors", "klayout_drc_errors", "lvs_errors"].every((k) => ph.layoutFinal!.checks?.[k] === 0) };
  }
  return <Landing data={data} />;
}
