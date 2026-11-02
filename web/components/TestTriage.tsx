import type { Json } from "@/lib/run";

// Measured credibility of a failing test: is the failure in the design or in the test?
// Built by verify/triage.py from stored files; never AI text.
export default function TestTriage({ test, triage, runStarted }: { test: string; triage: Json | null; runStarted?: string }) {
  const t = triage?.tests?.[test];
  const changed = triage?.test_code?.last_changed as string | undefined;
  const stale = !!(t && changed && runStarted && new Date(runStarted) < new Date(changed));
  if (!t || stale || !t.validated) {
    const why = !t ? "this test has not been run on a reference RTL"
      : stale ? "the test code changed after this run"
      : !t.passes_on_reference ? "it does not pass on the reference RTL" : "it catches none of the planted bugs";
    return (
      <p className="triage triage-no">
        <span className="tag-measured">measured</span>{" "}
        <span className="mark-neutral">○ Test not yet validated · check the test before the design</span>
        <span className="triage-ev"> ({why})</span>
      </p>
    );
  }
  const sc = Object.entries((t.scenarios ?? {}) as Record<string, number>).filter(([k]) => k !== "reset");
  const seen = Object.entries((t.flags_seen ?? {}) as Record<string, number>);
  return (
    <p className="triage triage-ok">
      <span className="tag-measured">measured</span>{" "}
      <span className="mark-pass">✓ Test validated · failure points to the design under test</span>
      <span className="triage-ev">
        {" "}Passes on the hand-written reference RTL (suite <span className="mono">{String(triage!.reference.suite_sha256).slice(0, 10)}</span>)
        · catches planted bugs <span className="mono">{t.kills.join(", ")}</span>
        {t.only_directed_killer_of.length ? <> (the only directed test that catches <span className="mono">{t.only_directed_killer_of.join(", ")}</span>)</> : null}
        {sc.length ? <> · drives {sc.map(([k, n]) => `${k} ×${n}`).join(", ")}</> : null}
        {seen.length ? <> · checks {seen.map(([k, n]) => `${k}=1 ×${n}`).join(", ")}</> : null}
        {t.scenarios_partial ? " (window of a long test)" : ""}.
      </span>
    </p>
  );
}
