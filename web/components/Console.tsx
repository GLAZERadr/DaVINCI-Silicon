"use client";

import { useEffect, useMemo, useState } from "react";
import FifoView from "./FifoView";
import Waveform, { pickTest } from "./Waveform";
import { apiBase } from "@/lib/api";
import { type Attempt, type Requirement, type Run, type Trace, status } from "@/lib/run";

const RANDOM = "test_random_regression";

export type ConsoleRun = { label: string; run: Run };

const short = (sha?: string | null, n = 12) => (sha ? sha.replace(/^sha256:/, "").slice(0, n) : "n/a");

function Pill({ s }: { s: string }) {
  const st = status(s);
  return <span className={`pill ${st.tone}`}>{st.mark} {st.word}</span>;
}

// The verdict an attempt stands on: a no-progress attempt repeats an earlier design.
function simulated(run: Run, a: Attempt): Attempt {
  return a.sameAs ? run.attempts.find((x) => x.n === a.sameAs) ?? a : a;
}

// A changed line whose code is the same once comments and whitespace are removed.
const norm = (l: string) => l.slice(1).replace(/\/\/.*$/, "").replace(/\s+/g, "");

function hideNoise(text: string): { text: string; hidden: number } {
  const lines = text.replace(/\n$/, "").split("\n");
  const keep = lines.map(() => true);
  let start = 0;
  const flush = (end: number) => {
    const del = new Map<string, number[]>();
    for (let i = start; i < end; i++) {
      if (lines[i].startsWith("-") && !lines[i].startsWith("---")) {
        const k = norm(lines[i]);
        if (!k) keep[i] = false; else del.set(k, [...(del.get(k) ?? []), i]);
      }
    }
    for (let i = start; i < end; i++) {
      if (lines[i].startsWith("+") && !lines[i].startsWith("+++")) {
        const k = norm(lines[i]);
        const match = del.get(k);
        if (!k) keep[i] = false;
        else if (match?.length) { keep[i] = false; keep[match.shift()!] = false; }
      }
    }
  };
  lines.forEach((l, i) => { if (l.startsWith("@@")) { flush(i); start = i; } });
  flush(lines.length);
  return { text: lines.filter((_, i) => keep[i]).join("\n"), hidden: keep.filter((k) => !k).length };
}

function Code({ text, diff }: { text: string; diff?: boolean }) {
  const lines = text.replace(/\n$/, "").split("\n");
  return (
    <pre className="c-code" tabIndex={0}>
      {lines.map((line, i) => {
        const cls = !diff ? undefined
          : line.startsWith("@@") ? "diff-hunk"
          : line.startsWith("+") && !line.startsWith("+++") ? "diff-add"
          : line.startsWith("-") && !line.startsWith("---") ? "diff-del" : undefined;
        return (
          <span key={i} className={`c-line ${cls ?? ""}`}>
            <span className="c-ln" aria-hidden="true">{i + 1}</span>
            <span>{line || " "}</span>
            {"\n"}
          </span>
        );
      })}
    </pre>
  );
}

function Tabs<T extends string>({ tabs, value, onChange, label }:
  { tabs: { key: T; label: string; disabled?: boolean }[]; value: T; onChange: (v: T) => void; label: string }) {
  return (
    <div className="c-tabs" role="tablist" aria-label={label}>
      {tabs.map((t) => (
        <button key={t.key} type="button" role="tab" aria-selected={value === t.key} disabled={t.disabled}
          className="c-tab" onClick={() => onChange(t.key)}>{t.label}</button>
      ))}
    </div>
  );
}

// Open on the first failing attempt when a later one changed the outcome; else the last.
function startAttempt(run: Run): number {
  if (!run.attempts.length) return 0;
  const firstFail = run.attempts.find((a) => a.status !== "pass");
  return firstFail && run.attempts.length > 1 ? firstFail.n : run.attempts[run.attempts.length - 1].n;
}

// Where an attempt's trace lives: the static export, or the API for runs on the server.
function traceUrl(source: "static" | "api", runId: string, n: number) {
  return source === "static" ? `/traces/${runId}__${n}.json`
    : `${apiBase()}/runs/${encodeURIComponent(runId)}/attempts/${n}/trace/trace.json`;
}

export default function Console({ runs, requirements, traceSource = "static" }:
  { runs: ConsoleRun[]; requirements: Requirement[]; traceSource?: "static" | "api" }) {
  const [which, setWhich] = useState(0);
  const run = runs[which].run;
  const [sel, setSel] = useState(startAttempt(run));
  const [quiet, setQuiet] = useState(true);
  const [editor, setEditor] = useState<"wave" | "fifo" | "diff" | "rtl" | "prompt">("wave");
  const [trace, setTrace] = useState<{ key: string; data: Trace | null } | null>(null);
  const [wTest, setWTest] = useState("");
  const [wCycle, setWCycle] = useState(1);
  const [panel, setPanel] = useState<"sim" | "compile" | "sweep">("sim");

  const a = run.attempts.find((x) => x.n === sel) ?? run.attempts[run.attempts.length - 1];
  const sim = a ? simulated(run, a) : undefined;
  const results = useMemo(() => new Map((sim?.tests ?? []).map((t) => [t.name, t])), [sim]);

  // Load the trace of the design this attempt stands on (no-progress repeats share it).
  const traceKey = sim ? `${run.id}/${sim.n}` : "";
  useEffect(() => {
    if (!sim || !sim.tests.length) { setTrace(null); return; }
    let live = true;
    fetch(traceUrl(traceSource, run.id, sim.n))
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null)
      .then((d: Trace | null) => {
        if (!live) return;
        setTrace({ key: traceKey, data: d && d.status === "ok" ? d : null });
        if (d && d.status === "ok") {
          const t = pickTest(d);
          setWTest(t);
          setWCycle(d.tests.find((x) => x.name === t)?.first_mismatch ?? 1);
        }
      });
    return () => { live = false; };
  }, [traceKey, traceSource, run.id, sim]);
  const tr = trace?.key === traceKey ? trace.data : null;
  const pickWTest = (t: string) => { setWTest(t); setWCycle(tr?.tests.find((x) => x.name === t)?.first_mismatch ?? 1); };
  const editorTabs = [
    { key: "wave" as const, label: "Waveform", disabled: !tr },
    { key: "fifo" as const, label: "FIFO replay", disabled: !tr },
    { key: "diff" as const, label: a?.n === 1 ? "Diff (none on attempt 1)" : "Diff vs previous", disabled: !a?.diff },
    { key: "rtl" as const, label: "sync_fifo.v", disabled: !a?.rtl },
    { key: "prompt" as const, label: "Prompt", disabled: !a?.prompt },
  ];
  const shownEditor = editorTabs.find((t) => t.key === editor && !t.disabled)?.key ?? editorTabs.find((t) => !t.disabled)?.key;
  const st = status(run.status);
  const next = a ? run.attempts.find((x) => x.n === a.n + 1) : undefined;
  const failing = (sim?.tests ?? []).filter((t) => !t.passed);
  const ordered = [...failing, ...(sim?.tests ?? []).filter((t) => t.passed)];
  const shownDiff = a?.diff ? (quiet ? hideNoise(a.diff) : { text: a.diff, hidden: 0 }) : null;

  function pickRun(i: number) {
    setWhich(i);
    const r = runs[i].run;
    setSel(startAttempt(r));
  }

  return (
    <div className="console">
      <aside className="c-side" aria-label="Run, attempts and requirements">
        {runs.length > 1 && (
          <div className="c-section">
            <p className="label">View</p>
            <div className="c-switch" role="radiogroup" aria-label="Which run">
              {runs.map((r, i) => (
                <button key={r.run.id} type="button" role="radio" aria-checked={i === which}
                  className="c-switch-btn" onClick={() => pickRun(i)}>{r.label}</button>
              ))}
            </div>
          </div>
        )}
        <div className="c-section">
          <p className="label">Attempts · every one counted</p>
          <ol className="c-attempts">
            {run.attempts.map((x) => (
              <li key={x.n}>
                <button type="button" className="c-attempt" aria-current={x.n === a?.n ? "true" : undefined} onClick={() => setSel(x.n)}>
                  <span className="mono">#{x.n}</span>
                  <span className="c-attempt-src">{x.source === "seeded" ? `seeded ${x.seeded?.mutant ?? ""}` : x.source}</span>
                  <Pill s={x.status} />
                </button>
              </li>
            ))}
            {run.attempts.length === 0 && <li className="mark-neutral">○ No attempts{run.notVerifiable ? ": not verifiable by this suite" : ""}</li>}
          </ol>
        </div>
        <div className="c-section c-tree">
          <p className="label">Requirements → tests (attempt {a?.n ?? "–"})</p>
          <ul>
            {requirements.map((r) => {
              const directed = r.tests.filter((t) => t !== RANDOM);
              const marks = directed.map((t) => results.get(t));
              const ok = directed.length === 0 || marks.some((m) => !m) ? null : marks.every((m) => m!.passed);
              return (
                <li key={r.id}>
                  <details>
                    <summary>
                      <span className={ok === null ? "mark-neutral" : ok ? "mark-pass" : "mark-fail"} aria-label={ok === null ? "not run" : ok ? "pass" : "fail"}>
                        {ok === null ? "○" : ok ? "✓" : "✕"}
                      </span>
                      <span className="mono c-req">{r.id}</span>
                      <span className="c-req-text">{r.text}</span>
                    </summary>
                    <ul className="c-tests">
                      {(directed.length ? directed : ["(no directed test)"]).map((t) => {
                        const m = results.get(t);
                        return (
                          <li key={t} className="mono">
                            <span className={!m ? "mark-neutral" : m.passed ? "mark-pass" : "mark-fail"}>{!m ? "○" : m.passed ? "✓" : "✕"}</span> {t}
                          </li>
                        );
                      })}
                    </ul>
                  </details>
                </li>
              );
            })}
          </ul>
        </div>
      </aside>

      <section className="c-editor" aria-label="RTL">
        <Tabs label="Editor" tabs={editorTabs} value={shownEditor ?? "diff"} onChange={setEditor} />
        <div className="c-scroll">
          {!a ? <p className="c-empty">No attempt to show.</p>
            : shownEditor === "wave" && tr ? <Waveform trace={tr} test={wTest} cycle={wCycle} onTest={pickWTest} onCycle={setWCycle} />
            : shownEditor === "fifo" && tr ? <FifoView trace={tr} test={wTest} cycle={wCycle} onTest={pickWTest} onCycle={setWCycle} />
            : shownEditor === "diff" && shownDiff ? (
              <>
                <div className="c-diffbar">
                  <label className="choice">
                    <input type="checkbox" checked={quiet} onChange={(e) => setQuiet(e.target.checked)} />
                    <span>Hide comment and whitespace changes{quiet && shownDiff.hidden ? ` (${shownDiff.hidden} lines hidden)` : ""}</span>
                  </label>
                </div>
                <Code text={shownDiff.text} diff />
              </>
            )
            : shownEditor === "rtl" && a.rtl ? <Code text={a.rtl} />
            : shownEditor === "prompt" && a.prompt ? (
              <div className="c-prompt">
                {a.prompt.map((m, i) => (
                  <div key={i}>
                    <p className="label">{m.role} message · sent to the model</p>
                    <pre className="c-code c-wrap">{String(m.content)}</pre>
                  </div>
                ))}
              </div>
            )
            : <p className="c-empty">{a.source === "seeded" ? "Attempt 1 is the reference RTL with a seeded bug; no model call, no prompt." : "Not recorded for this attempt."}</p>}
        </div>
      </section>

      <section className="c-panel" aria-label="Simulator output">
        <Tabs label="Output" value={panel} onChange={setPanel} tabs={[
          { key: "sim", label: `Simulator${sim?.total ? ` · ${sim.passed}/${sim.total}${failing.length ? ` · ${failing.length} failing` : ""}` : ""}` },
          { key: "compile", label: "Compile (G1)" },
          { key: "sweep", label: "Parameter sweep (G3)" },
        ]} />
        <div className="c-scroll c-out">
          {panel === "sim" && (
            !a ? null
            : a.rejection ? <p><span className="mark-fail">✕ Rejected before simulation:</span> <span className="mono">{a.rejection}</span></p>
            : sim && sim.tests.length ? (
              <>
                {a.sameAs ? <p className="mark-neutral">○ Same design as attempt {a.sameAs}; not simulated again. Showing attempt {a.sameAs}.</p> : null}
                <p className="label">Measured · {sim.simulator ?? "simulator"} · suite at run time {short(sim.suiteSha, 10)}</p>
                <ul className="c-results">
                  {ordered.map((t) => (
                    <li key={t.name}>
                      <span className={t.passed ? "mark-pass" : "mark-fail"}>{t.passed ? "✓ PASS" : "✕ FAIL"}</span>{" "}
                      <span className="mono">{t.name}</span>
                      {t.message ? <pre className="c-msg">{t.message}</pre> : null}
                    </li>
                  ))}
                </ul>
              </>
            )
            : <p className="mark-neutral">○ Not simulated{a.measuredError ? `: ${a.measuredError}` : ` (${status(a.status).word.toLowerCase()})`}.</p>
          )}
          {panel === "compile" && (
            a?.compileOk === undefined ? <p className="mark-neutral">○ No compile check recorded for this attempt.</p>
            : <>
              <p>{a.compileOk ? <span className="mark-pass">✓ Compiles as Verilog-2001</span> : <span className="mark-fail">✕ Does not compile</span>} <span className="mono">iverilog -g2001 -Wall</span></p>
              <pre className="c-msg">{a.compileOutput || "(no compiler output)"}</pre>
            </>
          )}
          {panel === "sweep" && (
            !a?.sweep ? <p className="mark-neutral">○ Not run: the sweep runs only after the frozen suite passes.</p>
            : <ul className="c-results">
              {a.sweep.sets.map((s, i) => (
                <li key={i}>
                  <span className={s.status === "pass" ? "mark-pass" : "mark-fail"}>{s.status === "pass" ? "✓ PASS" : "✕ FAIL"}</span>{" "}
                  <span className="mono">{Object.entries(s.params).map(([k, v]) => `${k}=${v}`).join(" ")}</span> · {s.passed}/{s.total}
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <aside className="c-right" aria-label="Diagnosis and attempt details">
        {next?.diagnosis && a?.status !== "pass" ? (
          <div className="ai">
            <p className="label">AI interpretation · not verified · diagnosis of this failure (sent with attempt {next.n})</p>
            <p>{next.diagnosis}</p>
          </div>
        ) : null}
        {a?.diagnosis ? (
          <div className="ai">
            <p className="label">AI interpretation · not verified · diagnosis that produced this attempt</p>
            <p>{a.diagnosis}</p>
          </div>
        ) : !(next?.diagnosis && a?.status !== "pass") ? (
          <div className="ai">
            <p className="label">AI interpretation · not verified</p>
            <p>{a?.source === "seeded" ? "No model text: this attempt is the seeded bug." : a?.n === 1 ? "First generation: the model answers with RTL only, no diagnosis." : "No diagnosis recorded."}</p>
          </div>
        ) : null}
        <div className={`measured ${sim?.total ? (sim.passed === sim.total ? "pass" : "fail") : ""}`}>
          <p className="label">Measured</p>
          <p>{a?.rejection ? `Rejected: ${a.rejection}` : sim?.total ? `${sim.passed}/${sim.total} frozen tests` : "Not simulated"}
            {a?.sweep ? ` · sweep ${a.sweep.status}` : ""}</p>
        </div>
        <dl className="facts c-facts">
          <dt>Source</dt><dd>{a?.source === "seeded" ? `reference RTL + ${a.seeded?.mutant} (${a.seeded?.desc})` : a?.source ?? "–"}</dd>
          {a?.model ? <><dt>Model</dt><dd>{a.model}</dd></> : null}
          {a?.tokensIn !== undefined ? <><dt>Tokens</dt><dd>{a.tokensIn.toLocaleString()} in / {(a.tokensOut ?? 0).toLocaleString()} out</dd></> : null}
          {a?.costUsd !== undefined ? <><dt>Cost</dt><dd>${a.costUsd.toFixed(4)}</dd></> : null}
          {a?.finishReason ? <><dt>Finish</dt><dd>{a.finishReason}</dd></> : null}
          <dt>Status</dt><dd>{a ? <Pill s={a.status} /> : "–"}</dd>
        </dl>
        {run.handoff ? (
          <div className="measured fail">
            <p className="label">Handed to an engineer</p>
            <p>Repairs exhausted. Still failing: <span className="mono">{(run.handoff.failing_tests ?? []).join(", ") || "n/a"}</span>; last simulated attempt {run.handoff.last_simulated_attempt ?? "n/a"}.</p>
          </div>
        ) : null}
      </aside>

      <footer className="c-status" aria-label="Run status">
        <span className={`c-status-run ${st.tone}`}>{st.mark} {st.word}</span>
        <span className="mono">{run.id}</span>
        <span>attempt {a?.n ?? "–"}/{run.attemptsTotal}</span>
        <span>{run.providers.generate}{run.providers.repair !== run.providers.generate ? ` → ${run.providers.repair}` : ""}</span>
        <span>${run.costUsd.toFixed(4)} · {run.tokens.in.toLocaleString()}/{run.tokens.out.toLocaleString()} tok</span>
        {run.sandbox ? <span>sandbox {run.sandbox.backend}</span> : null}
        <span className="mono">suite at run time {short(run.suiteSha, 10)}</span>
        {run.replayCheck ? <span>{run.replayCheck.reproduced ? "✓ replay reproduced" : "✕ replay differs"}</span> : null}
      </footer>
    </div>
  );
}
