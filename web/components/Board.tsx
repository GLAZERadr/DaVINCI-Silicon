import Link from "next/link";
import ReplayButton from "./ReplayButton";
import { type Attempt, type Board as BoardData, type RunSummary, status } from "@/lib/evidence";

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

function Pill({ s }: { s: string }) {
  const st = status(s);
  return <span className={`pill ${st.tone}`}>{st.mark} {st.word}</span>;
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

  const headline = shown.status === "pass" ? `${verified} OF ${requirements.length} REQUIREMENTS VERIFIED`
    : shown.status === "escaped" ? "VISIBLE TESTS PASSED · PARAMETER SWEEP FAILED"
    : `${runStatus.word.toUpperCase()}`;

  return (
    <>
      <header className="header">
        <div className="header-row">
          <Link href="/" className="wordmark">DAVINCI</Link>
          <nav className="runs-nav" aria-label="Recorded runs">
            {runs.map((r) => (
              <Link key={r.id} href={`/runs/${r.id}/`} aria-current={r.id === live.id ? "page" : undefined}>
                {r.id}
              </Link>
            ))}
          </nav>
          <div style={{ display: "flex", gap: 8, alignItems: "flex-start", flexWrap: "wrap" }}>
            <a className="btn btn-quiet" href="https://github.com/GLAZERadr/DaVINCI-Silicon/tree/main/evidence">Raw evidence</a>
            <ReplayButton runId={live.id} />
          </div>
        </div>
        <div className="rule" aria-hidden="true"><span /><span /><span /></div>
      </header>

      <main className="board">
        <section className="hero" aria-labelledby="verdict">
          <div>
            <p className="kicker">sync_fifo · {live.id} · {day(live.started)}</p>
            <h1 id="verdict" className="display">{headline}</h1>
            <p className="sub">
              {live.seedBug
                ? `Attempt 1 is the reference RTL with seeded bug ${live.seedBug}; Muse Spark repaired it from the simulator's measured failures. `
                : "Muse Spark wrote the RTL from the spec. "}
              {live.extraction
                ? `Requirements came from an image/PDF extraction (${live.extraction.extraction_id}), approved before generation. `
                : ""}
              {replay
                ? `The same recorded model output was re-checked under today's gates (Verilog-2001 compile, port check, parameter sweep) by replay ${replay.id}.`
                : "No replay under today's gates is in this bundle."}
            </p>
          </div>
          <span className={`verdict display ${runStatus.tone}`}>{runStatus.mark} {runStatus.word.toUpperCase()} · MEASURED</span>
        </section>

        <section className="grid-4" aria-label="Key figures">
          <div className="tile">
            <p className="label">Suite mutation score</p>
            <p className="value display">{mutation.matchesPin ? `${mutation.killed}/${mutation.injected}` : "n/a"}</p>
            <p className="note">{mutation.matchesPin
              ? "hand-written bugs in the reference RTL caught by the frozen tests; describes the suite, not this RTL"
              : "measured against a different suite than the pinned one; not shown"}</p>
          </div>
          <div className="tile">
            <p className="label">Attempts to green</p>
            <p className="value display">{live.attemptsToGreen ?? "n/a"}</p>
            <p className="note">{live.seedBug ? "attempt 1 is the seeded bug; " : ""}cap is 4 (1 + 3 repairs); every attempt counted</p>
          </div>
          <div className="tile">
            <p className="label">Time to green</p>
            <p className="value display">{live.timeToGreenS != null ? `${live.timeToGreenS.toFixed(1)} s` : "n/a"}</p>
            <p className="note">live run, start to all frozen tests passing</p>
          </div>
          <div className="tile">
            <p className="label">Model cost</p>
            <p className="value display">${live.costUsd.toFixed(3)}</p>
            <p className="note">{live.tokens.in.toLocaleString()} in / {live.tokens.out.toLocaleString()} out tokens, from the ledger</p>
          </div>
        </section>

        <section className="card" aria-labelledby="trace">
          <p id="trace" className="label">Traceability</p>
          <p className="lede">Each requirement, the frozen tests that check it, the seeded bugs those tests catch, and what the simulator measured.</p>
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

        <section className="grid-2">
          <div className="card" aria-labelledby="why">
            <p id="why" className="label" style={{ marginBottom: 16 }}>What changed and why</p>
            {repair ? (
              <div className="ai">
                <p className="label">AI interpretation · not verified</p>
                <p><Prose text={repair.diagnosis!} /></p>
              </div>
            ) : (
              <div className="ai">
                <p className="label">AI interpretation · not verified</p>
                <p>None. The first attempt passed, so no repair or diagnosis was requested.</p>
              </div>
            )}
            <div className={`measured ${runStatus.tone === "neutral" ? "" : runStatus.tone}`}>
              <p className="label">Measured</p>
              <p>
                {live.attempts.map((a, i) => (
                  <span key={a.n}>
                    {i > 0 && " → "}
                    Attempt {a.n}{a.source === "seeded" ? " (seeded)" : ""}: {a.total ? `${a.passed}/${a.total} tests` : status(a.status).word}
                  </span>
                ))}
                {failedFirst.length > 0 && <>. Attempt 1 failed <span className="mono">{failedFirst.join(", ")}</span></>}
                . Test files unchanged: suite hash {live.attempts.every((a) => !a.suiteSha || a.suiteSha === live.suiteSha) ? "matched on every attempt" : "CHANGED"}.
              </p>
            </div>
            {repair?.diff && (
              <details>
                <summary>RTL diff, attempt {repair.n - 1} → {repair.n}</summary>
                <Diff text={repair.diff} />
              </details>
            )}
          </div>

          <div className="card" aria-labelledby="gates">
            <p id="gates" className="label" style={{ marginBottom: 16 }}>Gates on the final RTL{replay ? " (today)" : ""}</p>
            <ul className="gates">
              <li><span className="gate mono">G1</span><span>Static checks and Verilog-2001 compile (<span className="mono">iverilog -g2001 -Wall</span>)</span>
                <Mark ok={last?.compileOk ?? null} /></li>
              <li><span className="gate mono">G2</span><span>Frozen suite, golden model compared every cycle, default parameters</span>
                <span className={lastSim && lastSim.passed === lastSim.total ? "mark-pass" : "mark-fail"}>{lastSim ? `${lastSim.passed === lastSim.total ? "✓" : "✕"} ${lastSim.passed}/${lastSim.total}` : "○ Not run"}</span></li>
              {(last?.sweep?.sets ?? []).map((s, i) => (
                <li key={i}><span className="gate mono">{i === 0 ? "G3" : ""}</span>
                  <span>Parameter sweep, WIDTH {s.params.WIDTH} · DEPTH {s.params.DEPTH} · AF_THRESH {s.params.AF_THRESH} (not shown to the model)</span>
                  <Mark ok={s.status === "pass"} /></li>
              ))}
              {!last?.sweep && <li><span className="gate mono">G3</span><span>Parameter sweep</span><Mark ok={null} /></li>}
            </ul>
            {weakDemo && (
              <div className="measured" style={{ marginTop: 20 }}>
                <p className="label">Measured · the suite catches its own weak test</p>
                <p>With <span className="mono">{weakDemo.tests_dropped.join(", ")}</span> left out, mutants <span className="mono">{weakDemo.weak.survivors.join(", ")}</span> survive ({weakDemo.weak.killed}/{weakDemo.weak.injected}). The full frozen suite kills them ({weakDemo.restored.killed}/{weakDemo.restored.injected}).</p>
              </div>
            )}
          </div>
        </section>

        <section className="card" id="reproduce" aria-labelledby="repro">
          <p id="repro" className="label" style={{ marginBottom: 16 }}>Reproduce it</p>
          <dl className="facts">
            <dt>Model</dt><dd>{model} (live, {day(live.started)})</dd>
            <dt>Simulator</dt><dd>{lastSim?.simulator ?? first?.simulator ?? "n/a"}, cocotb 2.1.0</dd>
            <dt>Container</dt><dd><code>{replay?.sandbox?.image_id ? `davinci-sim ${short(replay.sandbox.image_id, 19)}` : "n/a"}</code></dd>
            <dt>Frozen suite</dt><dd><code>sha256 {short(data.pinnedSuite, 16)}…</code></dd>
            <dt>Sweep</dt><dd><code>sha256 {short(data.pinnedSweep, 16)}…</code></dd>
            <dt>Recorded replay</dt>
            <dd>{replay ? <>{replay.id}: <Pill s={replay.status} />{" "}{replay.replayCheck?.reproduced ? "reproduced the live run attempt for attempt" : "did not reproduce the live run"}</> : "none"}</dd>
            <dt>Command</dt><dd><code className="cmd">python -m agent.pipeline --run-id {live.id} --provider replay</code></dd>
          </dl>
          <p className="foot" style={{ marginTop: 16, marginBottom: 0 }}>
            Replay re-simulates the recorded model output; it shows the pipeline and simulator are deterministic, not that the model would answer the same way again.
          </p>
        </section>

        <footer className="foot">
          Live model spend to date: ${data.ledger.liveSpendUsd.toFixed(2)} over {data.ledger.liveCallsOk} answered calls ({data.ledger.liveCallsTotal} recorded, including refusals), from <span className="mono">runs/_ledger.jsonl</span>.
          {" "}Limitations: the default spec states the reference equations; one block, one simulator; no synthesis, timing or power results. See the README.
        </footer>
      </main>
    </>
  );
}
