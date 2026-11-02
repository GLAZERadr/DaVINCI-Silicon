"use client";

import { useState } from "react";
import type { LandingData } from "./Landing";

// Landing "How it works": five steps, each with a panel drawn from the stored run.
const STEPS = [
  { key: "spec", label: "Spec", title: "Describe the block the way you would to a colleague.", sub: "Write the spec, or upload a datasheet PDF or screenshot. Muse Spark lists the requirements it found; you edit and approve them." },
  { key: "reqs", label: "Requirements", title: "Each requirement gets tests before any RTL exists.", sub: "The approved list maps every requirement to directed tests and a 3,000-cycle random regression against a golden model." },
  { key: "trust", label: "Trusted tests", title: "The tests have to catch planted bugs first.", sub: "Hand-written buggy versions of the reference design run against the frozen suite. If a bug slips through, the suite is not trusted yet." },
  { key: "loop", label: "Generate and repair", title: "Muse Spark writes the RTL. The simulator decides.", sub: "Each attempt is compiled and simulated in a sandbox. On a failure the model sees the failing test and cycle, and gets at most three repairs." },
  { key: "evidence", label: "Evidence", title: "A verification plan a lead can sign off.", sub: "Traceability, coverage, sign-off lines and every attempt, exported as Markdown, CSV and an OpenTitan-style testplan. Replays reproduce it for $0." },
] as const;

export default function HowItWorks({ data }: { data: LandingData }) {
  const [i, setI] = useState(0);
  const step = STEPS[i];
  const s = data.story;
  return (
    <div className="lp-how">
      <ol className="lp-how-tabs" role="tablist" aria-label="Steps">
        {STEPS.map((st, n) => (
          <li key={st.key}>
            <button type="button" role="tab" aria-selected={n === i} aria-controls="lp-how-panel" onClick={() => setI(n)}>
              <span className="lp-how-n">{String(n + 1).padStart(2, "0")}</span>{st.label}
            </button>
          </li>
        ))}
      </ol>
      <div id="lp-how-panel" className="lp-how-panel" role="tabpanel" aria-live="polite">
        <p className="lp-how-count">{String(i + 1).padStart(2, "0")} / {String(STEPS.length).padStart(2, "0")}</p>
        <h3 className="lp-how-title">{step.title} <span className="tone-2">{step.sub}</span></h3>
        <div className="lp-mock">
          {step.key === "spec" && (
            <>
              <div className="lp-mock-head"><span>Approved requirements · sync_fifo</span><span className="lp-mock-pass">✓ approved</span></div>
              <ul className="lp-mock-list">
                {data.requirements.slice(0, 4).map((r) => <li key={r.id}><span className="mono">{r.id}</span>{r.text}</li>)}
              </ul>
            </>
          )}
          {step.key === "reqs" && (
            <>
              <div className="lp-mock-head"><span>Requirements → tests</span><span className="meta-text">{data.requirements.length} requirements</span></div>
              <table className="lp-mock-table">
                <tbody>{data.requirements.slice(0, 6).map((r) => (
                  <tr key={r.id}><td className="mono">{r.id}</td><td>{r.text}</td><td className="mono">{r.tests.filter((t) => t !== "test_random_regression").join(", ") || "random regression"}</td></tr>
                ))}</tbody>
              </table>
            </>
          )}
          {step.key === "trust" && (
            <>
              <div className="lp-mock-head"><span>Planted bugs vs frozen suite</span><span className="lp-mock-pass">✓ {data.killed}/{data.injected} caught</span></div>
              <ul className="lp-mock-list">
                {data.mutants.map((m) => (
                  <li key={m.id}><span className="mono">{m.id}</span>{m.desc}<span className={m.killed ? "lp-mock-pass" : "lp-mock-fail"}>{m.killed ? "✓ caught" : "✕ survived"}</span></li>
                ))}
              </ul>
            </>
          )}
          {step.key === "loop" && s && (
            <>
              <div className="lp-mock-head"><span>Run {data.runId}</span><span className="meta-text">{s.model}</span></div>
              <ul className="lp-mock-list">
                <li><span className="lp-mock-fail">✕</span>Attempt 1 · {s.failPassed}/{s.total} · <span className="mono">{s.failTest}</span></li>
                <li className="lp-mock-ai"><span className="lp-tag-ai">AI interpretation · not verified</span>{(s.diagnosis ?? "").replace(/`/g, "").slice(0, 120)}…</li>
                <li><span className="lp-mock-pass">✓</span>Attempt 2 · {s.fixPassed}/{s.total} · all tests pass</li>
              </ul>
            </>
          )}
          {step.key === "evidence" && (
            <>
              <div className="lp-mock-head"><span>Verification plan · sign-off</span><span className={data.signoff.every((l) => l.status === "met") ? "lp-mock-pass" : "meta-text"}>{data.signoff.filter((l) => l.status === "met").length}/{data.signoff.length} met</span></div>
              <ul className="lp-mock-list">
                {data.signoff.map((l) => (
                  <li key={l.criterion}><span className={l.status === "met" ? "lp-mock-pass" : l.status === "not met" ? "lp-mock-fail" : "meta-text"}>{l.status === "met" ? "✓" : l.status === "not met" ? "✕" : "○"}</span>{l.criterion}</li>
                ))}
              </ul>
            </>
          )}
        </div>
        <div className="lp-how-nav">
          <button type="button" className="btn btn-quiet btn-sm" disabled={i === 0} onClick={() => setI(i - 1)}>← Previous</button>
          <button type="button" className="btn btn-sm" disabled={i === STEPS.length - 1} onClick={() => setI(i + 1)}>Next step →</button>
        </div>
      </div>
    </div>
  );
}
