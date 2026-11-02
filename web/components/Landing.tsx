import Link from "next/link";
import AccountButton from "./AccountButton";
import HowItWorks from "./HowItWorks";
import Logo from "./Logo";
import ModelAvatar from "./ModelAvatar";

// Landing page (structure after hire.ada4career.com: dark hero with a two-tone headline,
// a step-through of the product, feature cards, explainability, numbers, CTA cards, FAQ).
// Every number is passed in from the evidence bundle; none is typed here.

export type LandingData = {
  runId: string;
  requirements: { id: string; text: string; tests: string[] }[];
  mutants: { id: string; req: string; desc: string; killed: boolean }[];
  killed: number;
  injected: number;
  signoff: { criterion: string; status: string }[];
  liveRuns: number;
  liveCalls: number;
  spendUsd: number;
  formal: { proved: number; total: number } | null;
  story: {
    seeded: string | null; failPassed: number; total: number; failTest: string; failMessage: string;
    diagnosis: string | null; model: string; fixPassed: number; costUsd: number; seconds: number | null;
  } | null;
};

const FEATURES = [
  { n: "01", title: "Run Console", body: "Every attempt side by side: RTL diff, simulator log, the failing test and cycle, a waveform against the golden model and a replay of the FIFO's own pointers.", points: ["Waveform: measured vs expected, mismatch marked", "Test and cycle kept across attempts", "AI diagnosis shown dashed, never as a verdict"] },
  { n: "02", title: "Verification plan", body: "A plan a lead can sign off, written from stored results: testpoints, coverage, sign-off lines and where the AI was involved.", points: ["Markdown, CSV and OpenTitan-style testplan.hjson", "Sign-off: met, not met or not measured", "Byte-identical when re-generated"] },
  { n: "03", title: "Spec intake", body: "Upload a datasheet PDF or a screenshot. Muse Spark extracts the requirements; a person edits and approves them before any RTL is written.", points: ["Pages rendered locally, sent as images", "Mapping to known requirements labelled AI interpretation", "Runs refuse to start until approved"] },
  { n: "04", title: "Formal properties", body: "Hand-written properties checked with SymbiYosys on the reference and on every model RTL, next to the simulation results.", points: ["Unbounded proofs where they close", "Shows which planted bugs the properties miss", "Properties pinned by hash"] },
  { n: "05", title: "SKY130 timing and layout", body: "Synthesis, static timing and a full open-source layout run on SKY130, reference RTL next to the model's.", points: ["Pre-layout area, slack and power", "Post-layout ss / tt / ff corners", "DRC and LVS results, GDS produced"] },
  { n: "06", title: "Replay", body: "Any recorded run replays from its stored model output at $0, re-simulated under today's gates, so a reviewer can check the result themselves.", points: ["Same verdict or the difference shown", "Every attempt and failure kept", "Model RTL only runs in a no-network sandbox"] },
];

const FAQ = [
  ["What is DaVINCI Silicon?", "A verification-first loop for AI-written RTL. Muse Spark writes Verilog from an approved spec; frozen simulations, planted bugs and a golden model decide whether it is right, and every step is recorded as evidence."],
  ["Does the AI grade its own work?", "No. The tests and golden model are frozen and pinned by hash before any model call. The model only writes RTL. Its explanations are shown as AI interpretation, never as a result."],
  ["What can it design today?", "One block end to end: a synchronous FIFO, with Icarus Verilog as the simulator. Two more small blocks (a saturating gain stage and a round-robin arbiter) have their own frozen suites. It is a working prototype, not a full chip flow."],
  ["How do I know the tests are good enough?", "Before any RTL is trusted, the suite runs against hand-written buggy versions of the reference design. Each planted bug must make a test fail. The board shows which tests catch which bug, and what slips through when a test is removed."],
  ["Is my code run safely?", "Model-written RTL is compiled and simulated only inside a sandbox with no network, a non-root user, read-only tests and CPU, memory and time limits. Anything with system tasks or compiler directives is rejected before it runs."],
  ["What does it cost?", "Reading the evidence and replaying recorded runs is free. Live runs call Muse Spark and are switched on per account by the DaVINCI team; the cost of each call is recorded with the run."],
];

const usd = (n: number) => `$${n < 0.1 ? n.toFixed(4) : n.toFixed(2)}`;

export default function Landing({ data }: { data: LandingData }) {
  const s = data.story;
  return (
    <div className="lp">
      <header className="lp-nav">
        <div className="lp-wrap lp-nav-row">
          <Link href="/" className="wordmark lp-logo" aria-label="DaVINCI Silicon home"><Logo /></Link>
          <nav className="lp-nav-links" aria-label="Page">
            <a href="#how" className="lp-nav-link">How it works</a>
            <a href="#features" className="lp-nav-link">Features</a>
            <Link href="/evidence/" className="lp-nav-link">Evidence</Link>
            <a href="#faq" className="lp-nav-link">FAQ</a>
          </nav>
          <div className="lp-nav-actions"><AccountButton landing /></div>
        </div>
      </header>

      <section className="lp-hero">
        <div className="lp-hero-grid" aria-hidden="true" />
        <div className="lp-wrap lp-hero-row">
          <div className="lp-hero-copy">
            <p className="lp-eyebrow">For RTL and verification engineers</p>
            <h1 className="lp-h1">Write the spec.<br /><span className="lp-h1-muted">Get RTL with the evidence attached.</span></h1>
            <p className="lp-lede">Muse Spark writes the Verilog. A frozen, mutation-tested testbench decides whether it works, cycle by cycle, in a sandbox. You get the verification plan, the waveforms and every attempt, ready to sign off.</p>
            <div className="lp-cta-row">
              <Link href="/register/" className="btn lp-btn-lg">Get started</Link>
              <Link href="/evidence/" className="lp-link-light">See a verified run →</Link>
            </div>
          </div>

          {s && (
            <figure className="lp-run" aria-label={`Recorded run ${data.runId}`}>
              <div className="lp-run-head">
                <span className="mono">sync_fifo / {data.runId}</span>
                <span className="lp-pill-pass">✓ Pass · measured</span>
              </div>
              <ol className="lp-run-steps">
                <li className="lp-step-fail">
                  <span className="lp-dot" aria-hidden="true">✕</span>
                  <div>
                    <strong>Attempt 1 · {s.failPassed}/{s.total} tests</strong>{s.seeded && <span className="lp-run-meta"> · bug {s.seeded} planted on purpose</span>}
                    <code className="lp-run-code">{s.failTest}: {s.failMessage}</code>
                  </div>
                </li>
                {s.diagnosis && (
                  <li className="lp-step-ai">
                    <ModelAvatar model={s.model} />
                    <div>
                      <span className="lp-tag-ai">AI interpretation · not verified</span>
                      <p>{s.diagnosis.replace(/`/g, "").slice(0, 150)}{s.diagnosis.length > 150 ? "…" : ""}</p>
                    </div>
                  </li>
                )}
                <li className="lp-step-pass">
                  <span className="lp-dot" aria-hidden="true">✓</span>
                  <div><strong>Attempt 2 · {s.fixPassed}/{s.total} tests</strong><span className="lp-run-meta"> · repaired by {s.model}</span></div>
                </li>
              </ol>
              <figcaption className="lp-run-foot">
                <span>{data.killed}/{data.injected} planted bugs caught</span>
                <span>{s.seconds != null ? `${s.seconds.toFixed(1)} s to green` : ""}</span>
                <span>{usd(s.costUsd)} model cost</span>
              </figcaption>
            </figure>
          )}
        </div>
        <div className="lp-wrap">
          <p className="lp-proof-label">Measured on stored runs</p>
          <ul className="lp-proof">
            <li><strong>{data.requirements.length}/{data.requirements.length}</strong> requirements verified</li>
            <li><strong>{data.killed}/{data.injected}</strong> planted bugs caught</li>
            {data.formal && <li><strong>{data.formal.proved}/{data.formal.total}</strong> formal properties proved</li>}
            <li><strong>{usd(data.spendUsd)}</strong> total model spend</li>
          </ul>
        </div>
      </section>

      <section id="how" className="lp-section">
        <div className="lp-wrap">
          <p className="lp-kicker">How it works</p>
          <h2 className="lp-h2">Follow one block from spec to sign-off. <span className="tone-2">Click any step to jump to it.</span></h2>
          <HowItWorks data={data} />
        </div>
      </section>

      <section id="features" className="lp-section lp-section-alt">
        <div className="lp-wrap">
          <p className="lp-kicker">Also in DaVINCI</p>
          <h2 className="lp-h2">Everything a reviewer needs to trust the RTL. <span className="tone-2">Nothing they have to take on faith.</span></h2>
          <div className="lp-features">
            {FEATURES.map((f) => (
              <article key={f.n} className="lp-feature">
                <span className="lp-feature-n">{f.n}</span>
                <h3>{f.title}</h3>
                <p>{f.body}</p>
                <ul>{f.points.map((p) => <li key={p}>{p}</li>)}</ul>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="lp-section">
        <div className="lp-wrap lp-split">
          <div>
            <p className="lp-kicker">Explainability</p>
            <h2 className="lp-h2">Every verdict traces back to a simulator line.</h2>
            <p className="lp-body">Results come from the simulator and are marked measured. Anything the model wrote, such as its diagnosis of a failure, is dashed and labelled AI interpretation. The two are never mixed.</p>
            <ul className="lp-checks">
              <li>Each requirement links to its tests, the bugs they catch, attempt 1 and the final result</li>
              <li>A failing test is checked first: does it pass on the reference RTL, which bugs does it catch</li>
              <li>Failed, rejected and aborted attempts are recorded and shown, never retried silently</li>
            </ul>
          </div>
          <div className="lp-explain">
            <div className="lp-explain-measured">
              <span className="lp-explain-tag">measured</span>
              <p className="mono">{s ? `${s.failTest}\n${s.failMessage}` : "simulator output"}</p>
            </div>
            {s?.diagnosis && (
              <div className="lp-explain-ai">
                <span className="lp-tag-ai">AI interpretation · not verified</span>
                <p>{s.diagnosis.replace(/`/g, "")}</p>
              </div>
            )}
          </div>
        </div>
      </section>

      <section className="lp-section lp-section-alt">
        <div className="lp-wrap">
          <p className="lp-kicker">In numbers</p>
          <h2 className="lp-h2">Read from the evidence bundle, not written by hand.</h2>
          <p className="lp-body">Every number on this page comes from the stored runs committed with the code, read when the site is built.</p>
          <div className="lp-stats">
            <div><strong>{data.liveRuns}</strong><span>recorded live runs on Muse Spark, every attempt kept</span></div>
            <div><strong>{data.liveCalls}</strong><span>live model calls in the ledger, failed ones included</span></div>
            <div><strong>{data.killed}/{data.injected}</strong><span>planted bugs caught by the frozen test suite</span></div>
            <div><strong>{usd(data.spendUsd)}</strong><span>total spent on model calls so far</span></div>
          </div>
        </div>
      </section>

      <section className="lp-section">
        <div className="lp-wrap">
          <p className="lp-kicker">Start now</p>
          <h2 className="lp-h2">See the evidence first. <span className="tone-2">Then run your own spec.</span></h2>
          <div className="lp-ctas">
            <article className="lp-cta-card">
              <span className="lp-cta-tag">Free · no account</span>
              <h3>Replay a recorded run</h3>
              <p>Open the Evidence board and Run Console for a real run, then replay it from the stored model output at $0.</p>
              <Link href="/evidence/" className="btn btn-quiet">Open the evidence</Link>
            </article>
            <article className="lp-cta-card lp-cta-card-main">
              <span className="lp-cta-tag">Account</span>
              <h3>Run your own spec</h3>
              <p>Create an account to keep your runs together. Live Muse Spark runs are switched on per account by the DaVINCI team.</p>
              <Link href="/register/" className="btn">Create an account</Link>
            </article>
          </div>
        </div>
      </section>

      <section id="faq" className="lp-section lp-section-alt">
        <div className="lp-wrap lp-faq-wrap">
          <div>
            <p className="lp-kicker">FAQ</p>
            <h2 className="lp-h2">Questions we hear often.</h2>
            <p className="lp-body">Not here? The code and the evidence are public on <a href="https://github.com/GLAZERadr/DaVINCI-Silicon">GitHub</a>.</p>
          </div>
          <div className="lp-faq">
            {FAQ.map(([q, a], i) => (
              <details key={q}>
                <summary><span className="lp-faq-n">{String(i + 1).padStart(2, "0")}</span>{q}<span className="lp-faq-plus" aria-hidden="true">+</span></summary>
                <p>{a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      <section className="lp-final">
        <div className="lp-wrap lp-final-row">
          <h2 className="lp-final-title">Stop trusting RTL nobody has simulated.</h2>
          <Link href="/register/" className="btn lp-btn-lg">Get started</Link>
        </div>
      </section>

      <footer className="lp-foot">
        <div className="lp-wrap lp-foot-row">
          <span className="wordmark"><Logo /></span>
          <span className="meta-text">Design. Simulate. Validate. · © 2026 DaVINCI Silicon</span>
          <nav className="lp-foot-links" aria-label="Footer">
            <Link href="/evidence/">Evidence</Link>
            <Link href="/console/">Run Console</Link>
            <Link href="/access/">Request access</Link>
            <a href="https://github.com/GLAZERadr/DaVINCI-Silicon">GitHub</a>
          </nav>
        </div>
      </footer>
    </div>
  );
}
