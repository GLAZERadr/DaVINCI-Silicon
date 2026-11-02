import type { Metadata } from "next";
import Landing, { type LandingData } from "@/components/Landing";
import { board, runList } from "@/lib/evidence";

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
  return <Landing data={data} />;
}
