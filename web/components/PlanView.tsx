"use client";

import { useState } from "react";
import ModelAvatar from "./ModelAvatar";
import type { Json } from "@/lib/run";

// In-app viewer for verify/plan.py output: the plan in its seven sections, the
// testpoints CSV as a table, and testplan.hjson / JSON as code. Downloads stay secondary.

const MARK: Record<string, [string, string]> = {
  pass: ["✓ Pass", "mark-pass"], fail: ["✕ Fail", "mark-fail"], unverified: ["○ Unverified", "mark-neutral"],
  killed: ["✓ killed", "mark-pass"], SURVIVED: ["✕ survived", "mark-fail"], unknown: ["○ unknown", "mark-neutral"],
  met: ["✓ Met", "mark-pass"], "not met": ["✕ Not met", "mark-fail"], "not measured": ["○ Not measured", "mark-neutral"],
};
const Mk = ({ s }: { s: string }) => { const [w, c] = MARK[s] ?? [`○ ${s}`, "mark-neutral"]; return <span className={c}>{w}</span>; };

function csvRows(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [], cell = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (q) {
      if (ch === '"' && text[i + 1] === '"') { cell += '"'; i++; } else if (ch === '"') q = false; else cell += ch;
    } else if (ch === '"') q = true;
    else if (ch === ",") { row.push(cell); cell = ""; }
    else if (ch === "\n") { row.push(cell); rows.push(row); row = []; cell = ""; }
    else cell += ch;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  return rows;
}

function Code({ text }: { text: string }) {
  return (
    <pre className="c-code plan-code" tabIndex={0}>
      {text.replace(/\n$/, "").split("\n").map((l, i) => (
        <span key={i} className="c-line"><span className="c-ln" aria-hidden="true">{i + 1}</span><span>{l || " "}</span>{"\n"}</span>
      ))}
    </pre>
  );
}

const hits = (h: unknown) => (h && typeof h === "object" ? Object.entries(h as Record<string, number>).map(([k, n]) => `${k} ${n}`).join(", ") : String(h));

export default function PlanView({ plan, csv, hjson, planId }: { plan: Json; csv: string; hjson: string; planId: string }) {
  const [tab, setTab] = useState<"plan" | "csv" | "hjson" | "json">("plan");
  const src = plan.sources, run = plan.run, cs = plan.coverage_summary, pv = plan.provenance;
  const rows = csvRows(csv);
  const files: [string, string][] = [["md", "verification_plan.md"], ["csv", "verification_plan.csv"], ["hjson", "testplan.hjson"], ["json", "verification_plan.json"]];

  return (
    <div className="plan">
      <div className="plan-bar">
        <div className="c-tabs" role="tablist" aria-label="Plan views">
          {([["plan", "Plan"], ["csv", "Testpoints (CSV)"], ["hjson", "testplan.hjson"], ["json", "JSON"]] as const).map(([k, l]) => (
            <button key={k} type="button" role="tab" aria-selected={tab === k} className="c-tab" onClick={() => setTab(k)}>{l}</button>
          ))}
        </div>
        <span className="meta-text plan-dl">Download: {files.map(([ext, f], i) => <span key={ext}>{i ? " · " : ""}<a href={`/plans/${planId}.${ext}`} download={f}>.{ext}</a></span>)}</span>
      </div>

      {tab === "csv" && (
        <section className="box">
          <div className="box-header"><h2>Testpoints</h2><span className="meta-text">verification_plan.csv · one row per requirement · opens in any spreadsheet</span></div>
          <div className="table-wrap">
            <table>
              <thead><tr>{rows[0]?.map((h) => <th key={h}>{h}</th>)}</tr></thead>
              <tbody>{rows.slice(1).map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className={j === 0 || j === 1 ? "mono" : undefined}>{c}</td>)}</tr>)}</tbody>
            </table>
          </div>
        </section>
      )}
      {tab === "hjson" && (
        <section className="box">
          <div className="box-header"><h2>testplan.hjson</h2><span className="meta-text">OpenTitan-style testplan: testpoints (name, milestone, desc, tests) and covergroups</span></div>
          <Code text={hjson} />
        </section>
      )}
      {tab === "json" && (
        <section className="box">
          <div className="box-header"><h2>verification_plan.json</h2><span className="meta-text">everything above, machine-readable</span></div>
          <Code text={JSON.stringify(plan, null, 2)} />
        </section>
      )}

      {tab === "plan" && (
        <>
          <p className="lede">Every result is <strong>measured</strong> from stored simulator output, except the golden model&apos;s expected values and the diagnoses in §7, which are labelled <em>AI interpretation · not verified</em>. Anything not measured says so. Format: {plan.format}.</p>

          <section className="box">
            <div className="box-header"><h2>1. Header</h2></div>
            <dl className="side-facts plan-facts">
              <dt>Block</dt><dd><span className="mono">{src.block}</span> · {Object.entries(src.params ?? {}).map(([k, v]) => `${k}=${v}`).join(", ")}</dd>
              <dt>Spec</dt><dd><span className="mono">{plan.spec?.file}</span> · <span className="mono">{String(plan.spec?.sha256).slice(0, 16)}…</span></dd>
              <dt>Suite</dt><dd className="mono">{src.suite_sha256}</dd>
              <dt>Simulator</dt><dd>{src.simulator ?? "—"}</dd>
              <dt>Date</dt><dd>{plan.date ?? "—"}</dd>
              <dt>Run</dt><dd><span className="mono">{run.run_id}</span> · {run.status} · {run.attempts_total} attempts{run.seed_bug ? ` · seeded ${run.seed_bug}` : ""}{run.replayed_from ? ` · replay of ${run.replayed_from}` : ""}</dd>
              <dt>Final RTL</dt><dd className="mono">{src.final_rtl_sha256 ?? "—"}</dd>
            </dl>
          </section>

          <section className="grid-2">
            <div className="box">
              <div className="box-header"><h2>2. Scope</h2></div>
              <div className="box-pad"><p className="plan-p"><strong>In scope:</strong> {plan.scope.in}.</p>
                <p className="plan-p"><strong>Out of scope:</strong> {plan.scope.out.join("; ")}.</p></div>
            </div>
            <div className="box">
              <div className="box-header"><h2>3. Methodology</h2></div>
              <ul className="plan-list">{plan.methodology.map((m: string) => <li key={m}>{m}</li>)}</ul>
            </div>
          </section>

          <section className="box">
            <div className="box-header"><h2>4. Testpoints</h2><span className="meta-text">V1 reset and basic flags · V2 corner cases · result = final attempt</span></div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>ID</th><th>Name</th><th>MS</th><th>Goal · stimulus · check</th><th>Tests</th><th>Result</th><th>Mutants</th><th>Scenario hits</th></tr></thead>
                <tbody>
                  {plan.testpoints.map((tp: Json) => (
                    <tr key={tp.id}>
                      <td className="mono">{tp.id}</td>
                      <td className="mono">{tp.name}</td>
                      <td>{tp.milestone}</td>
                      <td><div><strong>Goal:</strong> {tp.desc.goal}</div><div className="meta-text"><strong>Stimulus:</strong> {tp.desc.stimulus}</div></td>
                      <td className="mono">{tp.tests.join(", ") || "—"}</td>
                      <td><Mk s={tp.result} />{tp.result_attempt_1 !== tp.result && ["pass", "fail"].includes(tp.result_attempt_1) ? <div className="meta-text">attempt 1: {tp.result_attempt_1}</div> : null}</td>
                      <td>{tp.mutants.length ? tp.mutants.map((m: Json) => <div key={m.id}><span className="mono">{m.id}</span> <Mk s={m.result} /></div>) : "—"}</td>
                      <td className="meta-text">{hits(tp.scenario_hits)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="box-lede">Check for every testpoint: {plan.testpoints[0]?.desc.check}.</p>
          </section>

          <section className="box">
            <div className="box-header"><h2>5. Coverage summary</h2></div>
            <ul className="checks checks-noid">
              <li><span aria-hidden="true">{typeof cs.functional === "object" ? "✓" : "○"}</span>
                <span className="check-name">Functional (scenario) coverage <span className="meta-text">{typeof cs.functional === "object" ? `${cs.functional.hit}/${cs.functional.total} scenarios hit; at 0 hits: ${cs.functional.zero.join(", ") || "none"}` : cs.functional}</span></span>
                <span>{typeof cs.functional === "object" ? `${cs.functional.hit}/${cs.functional.total}` : "—"}</span></li>
              <li><span aria-hidden="true">{typeof cs.mutation === "object" ? "✓" : "○"}</span>
                <span className="check-name">Mutation score <span className="meta-text">{typeof cs.mutation === "object" ? `survivors: ${cs.mutation.survivors.map((x: Json) => `${x.id} (${x.req})`).join(", ") || "none"} · hand-written mutants in the reference RTL; describes the suite` : cs.mutation}</span></span>
                <span>{typeof cs.mutation === "object" ? `${cs.mutation.killed}/${cs.mutation.injected}` : "—"}</span></li>
              <li><span className="mark-neutral" aria-hidden="true">○</span>
                <span className="check-name">Code coverage <span className="meta-text">{cs.code}</span></span><span className="mark-neutral">Not measured</span></li>
            </ul>
          </section>

          <section className="box">
            <div className="box-header"><h2>6. Sign-off status</h2><span className="meta-text">modelled on OpenTitan V2 · from stored data</span></div>
            <ul className="checks checks-noid">
              {plan.signoff.map((l: Json) => (
                <li key={l.id}>
                  <span aria-hidden="true" className={l.status === "met" ? "mark-pass" : l.status === "not met" ? "mark-fail" : "mark-neutral"}>{l.status === "met" ? "✓" : l.status === "not met" ? "✕" : "○"}</span>
                  <span className="check-name">{l.criterion} <span className="meta-text">{l.evidence}</span></span>
                  <Mk s={l.status} />
                </li>
              ))}
            </ul>
          </section>

          <section className="box">
            <div className="box-header"><h2>7. AI provenance</h2><span className="meta-text">attempts, results and cost measured · diagnoses AI interpretation</span></div>
            <p className="box-lede">Model(s): {pv.models.join(", ") || "none (no model call)"} · generate <span className="mono">{pv.providers?.generate}</span>, repair <span className="mono">{pv.providers?.repair}</span> · total ${Number(pv.cost_usd ?? 0).toFixed(4)}{pv.tokens ? ` · ${pv.tokens.in.toLocaleString()} in / ${pv.tokens.out.toLocaleString()} out tokens` : ""}</p>
            <div className="table-wrap">
              <table>
                <thead><tr><th>#</th><th>Source</th><th>Model</th><th>Status</th><th>Frozen suite</th><th>Tokens</th><th>Cost</th></tr></thead>
                <tbody>{pv.attempts.map((a: Json) => (
                  <tr key={a.n}><td>{a.n}</td><td>{a.source}</td><td className="mono">{a.model ?? "—"}</td><td>{a.status}</td><td>{a.result}</td>
                    <td>{a.tokens_in != null ? `${a.tokens_in.toLocaleString()}/${a.tokens_out.toLocaleString()}` : "—"}</td>
                    <td>{a.cost_usd != null ? `$${a.cost_usd.toFixed(4)}` : "—"}</td></tr>
                ))}</tbody>
              </table>
            </div>
            {pv.diagnoses.length > 0 && (
              <div className="box-pad">
                {pv.diagnoses.map((d: Json) => (
                  <div key={d.attempt} className="tl-comment plan-diag">
                    <div className="tl-comment-head"><ModelAvatar model={d.model} /><strong>{d.model}</strong><span className="tag-ai">AI interpretation · not verified</span><span className="meta-text">attempt {d.attempt}</span></div>
                    <p>{d.text}</p>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
