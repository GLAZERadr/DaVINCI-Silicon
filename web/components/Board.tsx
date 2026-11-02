import Link from "next/link";
import BreakdownView from "./BreakdownView";
import FormalPanel from "./FormalPanel";
import ModelAvatar from "./ModelAvatar";
import TestTriage from "./TestTriage";
import AreaBox from "./AreaBox";
import PhysicalPanel from "./PhysicalPanel";
import SiteHeader from "./SiteHeader";
import ReplayButton from "./ReplayButton";
import { type Attempt, type Board as BoardData, type RunSummary, simShort, status } from "@/lib/evidence";

const RANDOM = "test_random_regression";

// Model text keeps its `code` spans; it is still shown as text, never as markup.
function Prose({ text }: { text: string }) {
  return <>{text.split(/(`[^`]+`)/).map((part, i) =>
    part.startsWith("`") && part.endsWith("`") ? <code key={i}>{part.slice(1, -1)}</code> : part)}</>;
}

const short = (sha?: string | null, n = 12) => (sha ? sha.replace(/^sha256:/, "").slice(0, n) : "n/a");
const day = (iso: string) => iso.slice(0, 10);

function testsPassed(a: Attempt | undefined, tests: string[]): boolean | null {
  if (!a || a.tests.length === 0) return null;
  const results = tests.map((t) => a.tests.find((x) => x.name === t));
  if (results.some((r) => !r)) return null;
  return results.every((r) => r!.passed);
}

function Mark({ ok }: { ok: boolean | null }) {
  if (ok === null) return <span className="mark-neutral">○ Not run</span>;
  return ok ? <span className="mark-pass">✓ Pass</span> : <span className="mark-fail">✕ Fail</span>;
}

function Diff({ text }: { text: string }) {
  return (
    <pre className="code">
      {text.split("\n").map((line, i) => (
        <span key={i} className={line.startsWith("+") && !line.startsWith("+++") ? "diff-add"
          : line.startsWith("-") && !line.startsWith("---") ? "diff-del" : undefined}>
          {line + "\n"}
        </span>
      ))}
    </pre>
  );
}

export default function Board({ data, runs }: { data: BoardData; runs: RunSummary[] }) {
  const { live, replay, requirements, mutation, weakDemo } = data;
  const shown = replay ?? live; // today's gates, on the same recorded model output
  const last = shown.attempts[shown.attempts.length - 1];
  const lastSim = [...shown.attempts].reverse().find((a) => a.tests.length > 0);
  const first = live.attempts[0];
  const runStatus = status(shown.status);

  // The random regression covers every requirement, so each row is judged on
  // its directed tests and the regression gets its own row.
  const directed = (tests: string[]) => tests.filter((t) => t !== RANDOM);
  const rows = requirements.map((r) => ({
    ...r,
    mutants: mutation.mutants.filter((m) => m.req === r.id),
    first: testsPassed(first, directed(r.tests)),
    final: testsPassed(lastSim, directed(r.tests)),
  }));
  const randomFirst = testsPassed(first, [RANDOM]);
  const randomFinal = testsPassed(lastSim, [RANDOM]);
  const verified = randomFinal ? rows.filter((r) => r.final === true).length : 0;
  const repair = live.attempts.find((a) => a.n > 1 && a.diagnosis);
  const model = live.attempts.find((a) => a.source === "model")?.model ?? "n/a";
  const failedFirst = first?.tests.filter((t) => !t.passed).map((t) => t.name) ?? [];

  const seeded = live.seedBug ? live.attempts.find((a) => a.source === "seeded") : undefined;
  const repairs = live.attemptsToGreen ? live.attemptsToGreen - 1 : null;
  const tests = mutation.matchesPin ? ` · the tests catch ${mutation.killed} of ${mutation.injected} planted bugs` : "";
  const title = shown.status === "pass" ? `${verified} of ${requirements.length} requirements verified${tests}.`
    : shown.status === "escaped" ? "Visible tests passed; the parameter sweep failed."
    : `${runStatus.word}.`;
  const stats = `${live.timeToGreenS != null ? ` · ${live.timeToGreenS.toFixed(1)} s` : ""} · $${live.costUsd.toFixed(3)}`;
  const subtitle = live.seedBug
    ? `Seeded bug ${live.seedBug} caught by the frozen tests and repaired by Muse Spark${repairs != null ? ` in ${repairs} attempt${repairs === 1 ? "" : "s"}` : ""}${stats}.`
    : live.attempts.length === 1 && shown.status === "pass" ? `Muse Spark wrote the RTL; it passed on the first attempt${stats}.`
    : `Muse Spark wrote the RTL; the frozen tests decided${stats}.`;
  const checks = [
    { id: "G1", name: "Static checks + Verilog-2001 compile", desc: "no $, no directives, no initial/# delays, ports match; iverilog -g2001 -Wall", ok: last?.compileOk ?? null },
    { id: "G2", name: "Frozen suite", desc: lastSim ? `${lastSim.passed}/${lastSim.total} tests, golden model compared every cycle` : "not run", ok: lastSim ? lastSim.passed === lastSim.total : null },
    ...(last?.sweep?.sets ?? []).map((sw, k) => ({ id: k === 0 ? "G3" : "", name: `Parameter sweep · WIDTH ${sw.params.WIDTH} DEPTH ${sw.params.DEPTH} AF ${sw.params.AF_THRESH}`, desc: "never shown to the model", ok: sw.status === "pass" })),
    ...(last?.sweep ? [] : [{ id: "G3", name: "Parameter sweep", desc: "runs only after the frozen suite passes", ok: null }]),
  ];
  const failing = checks.filter((c) => c.ok === false).length;
  const pending = checks.filter((c) => c.ok === null).length;

  return (
    <>
      <SiteHeader active="evidence" crumbs={[{ label: live.id }]} />

      <div className="repo">
        <main className="repo-main">
          <section className="title-block" aria-labelledby="verdict">
            <p className="eyebrow">Verification plan · {day(live.started)}{live.extraction ? " · from a PDF spec" : ""}</p>
            <h1 id="verdict" className="display-title">
              {title} <span className="tone-2">{subtitle}</span>
            </h1>
            <div className="title-meta">
              <span className={`state ${runStatus.tone}`}>{runStatus.mark} {runStatus.word} · measured</span>
              {data.planId && <Link className="btn btn-quiet btn-sm" href={`/runs/${live.id}/plan/`}>Open verification plan</Link>}
              <span className="title-actions">
                <Link className="btn btn-quiet btn-sm" href={`/runs/${live.id}/console/`}>Open in Run Console</Link>
                <ReplayButton runId={live.id} />
              </span>
            </div>
          </section>

          <h2 className="group-title">Can the tests be trusted?</h2>
          <section className="box" aria-labelledby="suite">
            <div className="box-header"><h2 id="suite">Suite self-check</h2><span className="meta-text">measured against the reference RTL; about the tests, not this run</span></div>
            <ul className="checks">
              <li>
                <span className={mutation.matchesPin && mutation.killed === mutation.injected ? "mark-pass" : "mark-neutral"} aria-hidden="true">{mutation.matchesPin && mutation.killed === mutation.injected ? "✓" : "○"}</span>
                <span className="mono check-id">MUT</span>
                <span className="check-name">Planted bugs caught <span className="meta-text">hand-written mutants in the reference RTL</span></span>
                <span className="mark-pass">{mutation.matchesPin ? `${mutation.killed}/${mutation.injected}` : "n/a"}</span>
              </li>
              {weakDemo && (
                <li>
                  <span className="mark-pass" aria-hidden="true">✓</span>
                  <span className="mono check-id">WEAK</span>
                  <span className="check-name">Catches its own weak test <span className="meta-text">without <span className="mono">{weakDemo.tests_dropped.join(", ")}</span>, {weakDemo.weak.survivors.join(", ")} survive ({weakDemo.weak.killed}/{weakDemo.weak.injected}); the full suite kills them</span></span>
                  <span className="mark-pass">{weakDemo.restored.killed}/{weakDemo.restored.injected}</span>
                </li>
              )}
            </ul>
          </section>

        {data.scenarios && (
          <section className="box" aria-labelledby="scenarios">
            <div className="box-header">
              <h2 id="scenarios">Scenario coverage</h2>
              <span className="meta-text">{Object.values(data.scenarios.counts as Record<string, number>).filter((n) => n > 0).length}/{Object.keys(data.scenarios.counts).length} situations reached · {data.scenarios.cycles.toLocaleString()} cycles · measured on the final RTL</span>
            </div>
            <ul className="chips">
              {Object.entries(data.scenarios.counts as Record<string, number>).map(([k, n]) => (
                <li key={k} className={n > 0 ? "" : "zero"} title={data.scenarios!.descriptions[k]}>
                  <span className={n > 0 ? "mark-pass" : "mark-fail"} aria-hidden="true">{n > 0 ? "✓" : "✕"}</span>
                  <span>{data.scenarios!.descriptions[k]}</span>
                  <strong>{n > 0 ? n : "never"}</strong>
                </li>
              ))}
            </ul>
            {!data.scenarios.suite_passed && <p className="box-lede">The suite did not pass on this RTL, so the counts are partial.</p>}
          </section>
        )}

        {data.area && <AreaBox area={data.area} />}

        {data.gaps && (
          <section className="box" aria-labelledby="gaps">
            <div className="box-header"><h2 id="gaps">Plan gaps</h2></div>
            <p className="box-lede">
              Where the test plan is thin, measured against the reference RTL: the mutation check re-simulated
              with each test left out ({data.gaps.drops.length} suites), and with each directed test left out
              together with the random regression.
              {data.gaps.summary.all_predictions_match
                ? " Every result matched the prediction from the full run's killers, so the tests do not depend on each other."
                : " Some results did not match the prediction from the full run's killers."}
            </p>
            <ul className="gates gaps box-pad">
              <li>
                <span className="gate">One</span>
                <span>Mutants caught by only one directed test</span>
                <span className="mono">{data.gaps.summary.fragile.join(", ") || "none"}</span>
              </li>
              <li>
                <span className="gate">Random</span>
                <span>Mutants caught only by the random regression</span>
                <span className="mono">{data.gaps.summary.random_only.join(", ") || "none"}</span>
              </li>
              <li>
                <span className="gate">Untargeted</span>
                <span>Requirements no mutant targets: nothing shows their tests would catch a bug</span>
                <span className="mono">{data.gaps.summary.requirements_without_mutant.join(", ") || "none"}</span>
              </li>
            </ul>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Left out</th><th>Mutants killed</th><th>Survivors</th></tr></thead>
                <tbody>
                  {data.gaps.drops.filter((d: { survivors: string[] }) => d.survivors.length > 0).map((d: { dropped: string[]; killed: number; injected: number; survivors: string[] }) => (
                    <tr key={d.dropped.join("+")}>
                      <td className="mono">{d.dropped.join(" + ")}</td>
                      <td>{d.killed}/{d.injected}</td>
                      <td><span className="mark-fail">✕ {d.survivors.join(", ")} survive</span></td>
                    </tr>
                  ))}
                  <tr>
                    <td>Any single test</td>
                    <td colSpan={2}>{data.gaps.summary.single_drops_with_survivors.length === 0
                      ? <span className="mark-pass">✓ no survivors: the random regression still catches every mutant</span>
                      : <span className="mark-fail">✕ survivors when leaving out {data.gaps.summary.single_drops_with_survivors.join(", ")}</span>}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        )}

        <FormalPanel run={data.formal.run} reference={data.formal.reference} />

          <h2 className="group-title">Verification plan a lead can sign off</h2>
          {data.signoff && (
            <section className="box" aria-labelledby="signoff">
              <div className="box-header">
                <h2 id="signoff">Sign-off status</h2>
                <span className="meta-text">{data.signoff.filter((l) => l.status === "met").length} of {data.signoff.length} met · from stored data · modelled on OpenTitan V2</span>
              </div>
              <ul className="checks checks-noid">
                {data.signoff.map((l) => {
                  const ok = l.status === "met" ? true : l.status === "not met" ? false : null;
                  return (
                    <li key={l.id}>
                      <span className={ok === null ? "mark-neutral" : ok ? "mark-pass" : "mark-fail"} aria-hidden="true">{ok === null ? "○" : ok ? "✓" : "✕"}</span>
                      <span className="check-name">{l.criterion} <span className="meta-text">{l.evidence}</span></span>
                      <span className={ok === null ? "mark-neutral" : ok ? "mark-pass" : "mark-fail"}>{ok === null ? "Not measured" : ok ? "Met" : "Not met"}</span>
                    </li>
                  );
                })}
              </ul>
              <div className="box-footer">
                <span className="btn-row">
                  <Link className="btn btn-sm" href={`/runs/${live.id}/plan/`}>Open verification plan</Link>
                </span>
                <span className="meta-text">Vplan sections · OpenTitan-style testpoints · code coverage not measured · download as <a href={`/plans/${data.planId}.md`} download>.md</a> · <a href={`/plans/${data.planId}.csv`} download>.csv</a> · <a href={`/plans/${data.planId}.hjson`} download>testplan.hjson</a></span>
              </div>
            </section>
          )}

          <section className="box" aria-labelledby="trace">
            <div className="box-header">
              <h2 id="trace">Traceability</h2>
              <span className="meta-text">requirement → frozen tests → planted bugs caught → measured result</span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Requirement</th><th>Tests</th><th>Mutants killed</th><th>Attempt 1</th><th>Final</th></tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id}>
                      <td><span className="mono id">{r.id}</span>{r.text}</td>
                      <td className="mono">{directed(r.tests).join(", ")}</td>
                      <td>{r.mutants.length === 0 ? <span className="mark-neutral">○ none target it</span>
                        : r.mutants.map((m) => (
                          <div key={m.id}>{m.result === "killed" ? <span className="mark-pass">✓</span> : <span className="mark-fail">✕</span>} <span className="mono">{m.id}</span></div>
                        ))}</td>
                      <td>{live.seedBug && r.first === false ? <span className="mark-fail">✕ Fail (seeded)</span> : <Mark ok={r.first} />}</td>
                      <td>{r.final === null ? <span className="pill neutral">○ Unverified</span>
                        : r.final ? <span className="pill pass">✓ Pass</span> : <span className="pill fail">✕ Fail</span>}</td>
                    </tr>
                  ))}
                  <tr>
                    <td><span className="mono id">ALL</span>3000 random cycles against the golden model; covers every requirement</td>
                    <td className="mono">{RANDOM}</td>
                    <td><span className="mark-neutral">○ part of each kill above</span></td>
                    <td>{live.seedBug && randomFirst === false ? <span className="mark-fail">✕ Fail (seeded)</span> : <Mark ok={randomFirst} />}</td>
                    <td>{randomFinal === null ? <span className="pill neutral">○ Unverified</span>
                      : randomFinal ? <span className="pill pass">✓ Pass</span> : <span className="pill fail">✕ Fail</span>}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          {data.breakdown && (
            <section className="box" aria-labelledby="breakdown">
              <div className="box-header">
                <h2 id="breakdown">Design breakdown before RTL</h2>
                <span className="meta-text">proposed by the model, approved by {data.breakdown.approved.approved_by}, passed into the RTL prompt</span>
              </div>
              <div className="box-pad">
                <BreakdownView breakdown={data.breakdown.approved.breakdown} model={data.breakdown.model}
                  approvedBy={data.breakdown.approved.approved_by} check={data.breakdown.check} />
              </div>
            </section>
          )}

          <h2 className="group-title">Where and why it failed</h2>
          <section className="box" aria-labelledby="timeline">
            <div className="box-header">
              <h2 id="timeline">Run timeline</h2>
              <span className="meta-text">every attempt counted · AI text kept apart from measured results</span>
            </div>
            <ol className="timeline-pr">
              {live.attempts.map((a) => {
                const ok = a.total ? a.passed === a.total : null;
                const failed = a.tests.filter((t) => !t.passed).map((t) => t.name);
                return (
                  <li key={a.n}>
                    {a.diagnosis && (
                      <div className="tl-comment">
                        <div className="tl-comment-head">
                          <ModelAvatar model={a.model} size={26} />
                          <strong>{a.model ?? "model"}</strong>
                          <span className="tag-ai">AI interpretation · not verified</span>
                          <span className="meta-text">diagnosis sent with attempt {a.n}</span>
                        </div>
                        <p><Prose text={a.diagnosis} /></p>
                      </div>
                    )}
                    <div className="tl-event">
                      <span className={`tl-dot ${ok === null ? "neutral" : ok ? "pass" : "fail"}`} aria-hidden="true">{ok === null ? "○" : ok ? "✓" : "✕"}</span>
                      <div>
                        <p className="tl-title">
                          <strong>Attempt {a.n}</strong>{" "}
                          <span className="meta-text">{a.source === "seeded" ? `reference RTL with seeded bug ${a.seeded?.mutant} (${a.seeded?.desc})` : `RTL written by ${a.model ?? "the model"}`}</span>
                        </p>
                        <p className="tl-measured">
                          <span className="tag-measured">measured</span>{" "}
                          <span className={ok === null ? "mark-neutral" : ok ? "mark-pass" : "mark-fail"}>{a.total ? `${ok ? "✓" : "✕"} ${a.passed}/${a.total} frozen tests` : `○ ${status(a.status).word}`}</span>
                          {failed.length > 0 && <> · failing <span className="mono">{failed.join(", ")}</span></>}
                          {a.rejection && <> · rejected before simulation by G1: <span className="mono">{a.rejection}</span></>}
                        </p>
                        {failed.map((f) => (
                          <div key={f} className="tl-triage"><span className="mono">{f}</span><TestTriage test={f} triage={data.triage} runStarted={live.started} /></div>
                        ))}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ol>
            <div className="box-footer">
              {repair?.diff ? (
                <details className="disclosure">
                  <summary>Show RTL diff, attempt {repair.n - 1} → {repair.n}</summary>
                  <Diff text={repair.diff} />
                </details>
              ) : <span className="meta-text">{seeded ? "" : "The first attempt passed, so no repair or diagnosis was requested."}</span>}
              <span className="meta-text">Test files unchanged on every attempt: run-time suite <span className="mono">{short(live.suiteSha, 10)}</span>{live.attempts.every((a) => !a.suiteSha || a.suiteSha === live.suiteSha) ? "" : " · CHANGED"}</span>
            </div>
          </section>

          <section className="box" aria-labelledby="gates">
            <div className={`box-header checks-head ${failing ? "fail" : pending ? "neutral" : "pass"}`}>
              <h2 id="gates">
                <span aria-hidden="true">{failing ? "✕" : pending ? "○" : "✓"}</span>{" "}
                {failing ? `${failing} check${failing === 1 ? "" : "s"} failing` : pending ? "Some checks not run" : "All checks have passed"}
              </h2>
              <span className="meta-text">gates on the final RTL{replay ? `, re-run today by ${replay.id}` : ""}</span>
            </div>
            <ul className="checks">
              {checks.map((c, k) => (
                <li key={k}>
                  <span className={c.ok === null ? "mark-neutral" : c.ok ? "mark-pass" : "mark-fail"} aria-hidden="true">{c.ok === null ? "○" : c.ok ? "✓" : "✕"}</span>
                  <span className="mono check-id">{c.id}</span>
                  <span className="check-name">{c.name} <span className="meta-text">{c.desc}</span></span>
                  <span className={c.ok === null ? "mark-neutral" : c.ok ? "mark-pass" : "mark-fail"}>{c.ok === null ? "Not run" : c.ok ? "Pass" : "Fail"}</span>
                </li>
              ))}
            </ul>
          </section>

          <PhysicalPanel data={data.physical} />
        </main>

        <aside className="repo-side" aria-label="About this run">
          <section className="side-section">
            <h2>About</h2>
            <p className="side-text">A verification plan with evidence for AI-written RTL: requirements traced to frozen, mutation-tested simulations; every attempt measured.</p>
            <ul className="side-links">
              {data.planId && <li><Link href={`/runs/${live.id}/plan/`}>Verification plan</Link> <span className="meta-text">(view in app)</span></li>}
              {data.referencePlan && <li><Link href="/reference/plan/">Reference RTL plan</Link></li>}
              <li><a href="https://github.com/GLAZERadr/DaVINCI-Silicon/tree/main/evidence">Raw evidence on GitHub</a></li>
            </ul>
            <dl className="side-facts">
              <dt>Model</dt><dd>{model}</dd>
              <dt>Attempts</dt><dd>{live.attemptsTotal}{live.seedBug ? " (1 seeded)" : ""} · cap 4</dd>
              <dt>Time</dt><dd>{live.timeToGreenS != null ? `${live.timeToGreenS.toFixed(1)} s to green` : "–"}</dd>
              <dt>Cost</dt><dd>${live.costUsd.toFixed(3)} · {live.tokens.in.toLocaleString()}/{live.tokens.out.toLocaleString()} tok</dd>
              <dt>Sandbox</dt><dd>{replay?.sandbox?.backend ?? live.sandbox?.backend ?? "–"}</dd>
            </dl>
          </section>

          <section className="side-section">
            <h2>Recorded runs <span className="counter">{runs.length}</span></h2>
            <ul className="side-runs">
              {runs.map((r) => {
                const st = status(r.status);
                return (
                  <li key={r.id}>
                    <Link href={`/runs/${r.id}/`} aria-current={r.id === live.id ? "page" : undefined}>
                      <span className={`run-badge ${st.tone}`} aria-hidden="true">{st.mark}</span>
                      <span className="run-name">{r.id}</span>
                      <span className={`run-state mark-${st.tone}`}>{st.word}</span>
                      <span className="run-desc">{r.seedBug ? "Seeded bug, then repair" : r.fromExtraction ? "From a PDF spec" : "From the written spec"}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </section>

          <section className="side-section" id="reproduce" aria-labelledby="repro">
            <h2 id="repro">Reproduce it</h2>
            <code className="cmd">python -m agent.pipeline --run-id {live.id} --provider replay</code>
            {data.planId && <code className="cmd">make plan RUN={data.planId}</code>}
            <dl className="side-facts">
              <dt>Simulator</dt><dd>
                Original run: {simShort(first?.simulator)}
                {replay ? <> · Replay: {simShort(lastSim?.simulator)} · {replay.replayCheck?.reproduced ? "verdict reproduced" : "verdict differs"}</> : null}
              </dd>
              <dt>Suite pin</dt><dd><code>{short(data.pinnedSuite, 12)}</code>{live.suiteSha && live.suiteSha !== data.pinnedSuite ? <> · live run <code>{short(live.suiteSha, 12)}</code></> : null}</dd>
              <dt>Sweep pin</dt><dd><code>{short(data.pinnedSweep, 12)}</code></dd>
              <dt>Image</dt><dd><code>{replay?.sandbox?.image_id ? short(replay.sandbox.image_id, 12) : "n/a"}</code></dd>
              <dt>Replay</dt><dd>{replay ? <>{replay.replayCheck?.reproduced ? <span className="mark-pass">✓ reproduced</span> : <span className="mark-fail">✕ differs</span>} <span className="mono">{replay.id}</span></> : "none"}</dd>
            </dl>
            <p className="side-text">Replay re-simulates the recorded model output: it shows the pipeline is deterministic, not that the model would answer the same way again.</p>
          </section>
        </aside>
      </div>

      <footer className="site-foot">
        Live model spend to date: ${data.ledger.liveSpendUsd.toFixed(2)} over {data.ledger.liveCallsOk} answered calls ({data.ledger.liveCallsTotal} recorded, including refusals), from <span className="mono">runs/_ledger.jsonl</span>.
        {" "}Limitations: a person writes and approves the requirements and interface (the design breakdown); coverage here is mutation-based (8 hand-written bugs), not line or functional coverage; the default spec states the reference equations; one block, one simulator; no timing or power results; area, where shown, is a generic Yosys cell count, not silicon area. See the README.
      </footer>
    </>
  );
}
