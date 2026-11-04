import Link from "next/link";
import AccountButton from "./AccountButton";
import Logo from "./Logo";
import ProductDemo from "./ProductDemo";
import type { Trace } from "@/lib/run";

// Landing page. Light and restrained, like the tool itself: the hero visual is the real
// Run Console waveform of a recorded run, and every number is passed in from the
// evidence bundle (app/page.tsx), never typed here.

type Phys = { area: number; fmax: number; mw: number };
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
  trace?: Trace;
  physical?: { ref: Phys; run: Phys; drcLvsClean: boolean };
};

// Official logos from each project's own repository (web/public/logos/SOURCES.md); tools
// that publish no logo are set as text. These are tools DaVINCI runs on, not partners.
const TOOLS: { name: string; logo?: string; h?: number; avatar?: boolean; text?: string }[] = [
  { name: "Muse Spark 1.3 (Meta)", logo: "/brand/muse-avatar.png", avatar: true, text: "Muse Spark" },
  { name: "Icarus Verilog", text: "Icarus Verilog" },
  { name: "cocotb", logo: "/logos/cocotb.svg", h: 26 },
  { name: "YosysHQ: Yosys and SymbiYosys", logo: "/logos/yosyshq.png", h: 22 },
  { name: "OpenSTA", text: "OpenSTA" },
  { name: "LibreLane (OpenLane 2 flow)", logo: "/logos/librelane.svg", h: 26 },
  { name: "SkyWater SKY130 PDK", logo: "/logos/skywater.png", h: 30 },
];

const STEPS = [
  ["Spec", "Write the spec or upload a datasheet. A person approves the requirement list before any RTL exists."],
  ["Tests", "Each requirement maps to directed tests and a 3,000-cycle random regression against a golden model."],
  ["Self-check", "Planted bugs must make the frozen suite fail. If one slips through, the suite is not ready."],
  ["Generate", "The model writes Verilog. It is compiled and simulated in a sandbox, with at most three repairs."],
  ["Evidence", "Every attempt, waveform and gap goes into a verification plan a lead can sign off."],
];

const FAQ = [
  ["What is DaVINCI Silicon?", "A verification-first loop for AI-written RTL. Muse Spark writes Verilog from an approved spec; frozen simulations, planted bugs and a golden model decide whether it is right, and every step is kept as evidence."],
  ["Does the AI grade its own work?", "No. The tests and the golden model are frozen and pinned by hash before any model call. The model only writes RTL. Its explanations are labelled AI interpretation and never count as a result."],
  ["What can it design today?", "One block end to end: a synchronous FIFO, simulated with Icarus Verilog. Two more small blocks, a saturating gain stage and a round-robin arbiter, have their own frozen suites. It is a working prototype, not a full chip flow."],
  ["How do I know the tests are good enough?", "Before any RTL is trusted, the suite runs against hand-written buggy versions of the reference design, and every planted bug must make a test fail. The evidence shows which test catches which bug, and what slips through when a test is removed."],
  ["Is generated code run safely?", "Model-written RTL is compiled and simulated only in a sandbox with no network, a non-root user, read-only tests and CPU, memory and time limits. Code with system tasks or compiler directives is rejected before it runs."],
  ["What does it cost?", "Reading the evidence and the recorded runs is free and needs no account. Live runs call Muse Spark and are switched on per account by the DaVINCI team; the cost of every call is recorded with the run."],
];

const usd = (n: number) => `$${n < 0.1 ? n.toFixed(4) : n.toFixed(2)}`;

export default function Landing({ data }: { data: LandingData }) {
  const s = data.story;
  const met = data.signoff.filter((l) => l.status === "met").length;
  return (
    <div className="lp">
      <header className="lp-nav">
        <div className="lp-wrap lp-nav-row">
          <Link href="/" className="wordmark" aria-label="DaVINCI Silicon home"><Logo /></Link>
          <nav className="lp-nav-links" aria-label="Page">
            <a href="#how">How it works</a>
            <a href="#trust">Evidence</a>
            <a href="#faq">FAQ</a>
            <a href="https://github.com/GLAZERadr/DaVINCI-Silicon">GitHub</a>
          </nav>
          <div className="lp-nav-actions"><AccountButton landing /></div>
        </div>
      </header>

      <main>
        <section className="lp-hero">
          <div className="lp-wrap">
            <p className="lp-eyebrow">For RTL and verification engineers</p>
            <h1 className="lp-h1">Prove the tests first. <span className="tone-2">Then let the model write the RTL.</span></h1>
            <p className="lp-lede">DaVINCI checks a frozen testbench against planted bugs, then simulates model-written Verilog against it, cycle by cycle, in a sandbox. You get every attempt, the waveform of each failure and a verification plan a lead can sign off. Today: one block, a synchronous FIFO.</p>
            <div className="lp-cta-row">
              <Link href="/register/" className="btn lp-btn">Get started</Link>
              <Link href="/evidence/" className="btn btn-quiet lp-btn">See a recorded run</Link>
            </div>
          </div>
          {data.trace && s && <div className="lp-wrap lp-hero-demo"><ProductDemo data={data} /></div>}
        </section>

        <section className="lp-tools" aria-label="Tools DaVINCI runs on">
          <div className="lp-wrap lp-tools-row">
            <span className="lp-tools-label">Runs on</span>
            <ul>{TOOLS.map((t) => (
              <li key={t.name} title={t.name}>
                {t.logo && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={t.logo} alt={t.text ? "" : t.name} height={t.avatar ? 26 : t.h} className={t.avatar ? "lp-tool-avatar" : "lp-tool-logo"} />
                )}
                {t.text && <span className="lp-tool-text">{t.text}</span>}
              </li>
            ))}</ul>
          </div>
        </section>

        <section id="how" className="lp-section">
          <div className="lp-wrap">
            <h2 className="lp-h2">One block, from spec to sign-off.</h2>
            <ol className="lp-steps">
              {STEPS.map(([title, body], i) => (
                <li key={title}><span className="lp-step-n">{String(i + 1).padStart(2, "0")}</span><h3>{title}</h3><p>{body}</p></li>
              ))}
            </ol>
          </div>
        </section>

        <section id="trust" className="lp-section lp-section-line">
          <div className="lp-wrap lp-rows">
            <div className="lp-row">
              <div className="lp-row-copy">
                <p className="lp-eyebrow">Trust the tests first</p>
                <h3 className="lp-h3">Planted bugs prove the suite catches failures.</h3>
                <p className="lp-p">Before any generated RTL counts, the frozen suite runs against hand-written buggy copies of the reference design. A bug that slips through means the tests are not ready, whatever the model writes.</p>
              </div>
              <div className="box lp-row-visual">
                <div className="box-header"><h2>Planted bugs vs frozen suite</h2><span className="mark-pass">✓ {data.killed}/{data.injected} caught</span></div>
                <ul className="checks checks-noid">
                  {data.mutants.map((m) => (
                    <li key={m.id}><span aria-hidden="true" className={m.killed ? "mark-pass" : "mark-fail"}>{m.killed ? "✓" : "✕"}</span>
                      <span className="check-name"><span className="mono lp-id">{m.id}</span> {m.desc}</span>
                      <span className="meta-text mono">{m.req}</span></li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="lp-row lp-row-flip">
              <div className="lp-row-copy">
                <p className="lp-eyebrow">Sign-off, not a chat log</p>
                <h3 className="lp-h3">A verification plan a lead can sign.</h3>
                <p className="lp-p">Each run exports a plan written only from stored results: testpoints per requirement, coverage, sign-off criteria and where the model was involved. Markdown, CSV and an OpenTitan-style testplan.</p>
              </div>
              <div className="box lp-row-visual">
                <div className="box-header"><h2>Functional sign-off</h2><span className={met === data.signoff.length ? "mark-pass" : "meta-text"}>{met}/{data.signoff.length} met · timing separate</span></div>
                <ul className="checks checks-noid">
                  {data.signoff.map((l) => (
                    <li key={l.criterion}><span aria-hidden="true" className={l.status === "met" ? "mark-pass" : l.status === "not met" ? "mark-fail" : "mark-neutral"}>{l.status === "met" ? "✓" : l.status === "not met" ? "✕" : "○"}</span>
                      <span className="check-name">{l.criterion}</span>
                      <span className={l.status === "met" ? "mark-pass" : "mark-neutral"}>{l.status === "met" ? "Met" : l.status}</span></li>
                  ))}
                </ul>
              </div>
            </div>

            {s?.diagnosis && (
              <div className="lp-row">
                <div className="lp-row-copy">
                  <p className="lp-eyebrow">Measured or interpreted</p>
                  <h3 className="lp-h3">The simulator decides. The model explains.</h3>
                  <p className="lp-p">Results come from the simulator and are marked measured. What the model writes, such as its diagnosis of a failure, is dashed and labelled AI interpretation. The two are never mixed, and every failed or rejected attempt stays on record.</p>
                </div>
                <div className="lp-row-visual lp-mi">
                  <div className="box">
                    <div className="box-header"><h2>Simulator · attempt 1</h2><span className="tag-measured">measured</span></div>
                    <pre className="lp-pre">{s.failTest}{"\n"}{s.failMessage}</pre>
                  </div>
                  <div className="lp-ai">
                    <span className="tag-ai">AI interpretation · not verified</span>
                    <p>{s.diagnosis.replace(/`/g, "")}</p>
                  </div>
                </div>
              </div>
            )}

            {data.physical && (
              <div className="lp-row lp-row-flip">
                <div className="lp-row-copy">
                  <p className="lp-eyebrow">Beyond simulation</p>
                  <h3 className="lp-h3">Formal checks and SKY130 numbers, next to the reference.</h3>
                  <p className="lp-p">The same RTL goes through SymbiYosys properties, synthesis and static timing on SKY130, and a full open-source layout run. The model&apos;s design is always shown against the hand-written reference.</p>
                </div>
                <div className="box lp-row-visual">
                  <div className="box-header"><h2>SKY130 pre-layout · 100 MHz · run {data.runId}</h2><span className="tag-measured">measured</span></div>
                  <div className="table-wrap">
                    <table>
                      <thead><tr><th></th><th>Reference RTL</th><th>Model RTL</th></tr></thead>
                      <tbody>
                        <tr><td>Cell area</td><td>{data.physical.ref.area.toFixed(1)} µm²</td><td>{data.physical.run.area.toFixed(1)} µm²</td></tr>
                        <tr><td>Max frequency (est.)</td><td>{data.physical.ref.fmax.toFixed(1)} MHz</td><td>{data.physical.run.fmax.toFixed(1)} MHz</td></tr>
                        <tr><td>Power (default activity)</td><td>{data.physical.ref.mw.toFixed(3)} mW</td><td>{data.physical.run.mw.toFixed(3)} mW</td></tr>
                        {data.formal && <tr><td>Formal properties</td><td colSpan={2}><span className="mark-pass">✓ {data.formal.proved}/{data.formal.total} proved</span></td></tr>}
                        {data.physical.drcLvsClean && <tr><td>Layout DRC / LVS</td><td colSpan={2}><span className="mark-pass">✓ clean</span></td></tr>}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>

        <section className="lp-facts" aria-label="Measured so far">
          <div className="lp-wrap">
            <p>So far, read from stored runs: <strong>{data.liveRuns}</strong> live runs · <strong>{data.liveCalls}</strong> model calls, failures included · <strong>{data.killed}/{data.injected}</strong> planted bugs caught · <strong>{usd(data.spendUsd)}</strong> total model spend.</p>
          </div>
        </section>

        <section id="faq" className="lp-section lp-section-line">
          <div className="lp-wrap lp-faq-wrap">
            <div>
              <h2 className="lp-h2">Questions</h2>
              <p className="lp-p">The code and the evidence are public on <a href="https://github.com/GLAZERadr/DaVINCI-Silicon">GitHub</a>.</p>
            </div>
            <div className="lp-faq">
              {FAQ.map(([q, a]) => (
                <details key={q}>
                  <summary>{q}<span className="lp-faq-icon" aria-hidden="true" /></summary>
                  <p>{a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section className="lp-section lp-section-line lp-end">
          <div className="lp-wrap">
            <h2 className="lp-h2">Open the recorded runs.</h2>
            <p className="lp-p">No account needed: read the evidence, step through the waveforms and open the verification plans. The code and every stored run are on GitHub.</p>
            <div className="lp-cta-row">
              <Link href="/evidence/" className="btn lp-btn">Open the evidence</Link>
              <a href="https://github.com/GLAZERadr/DaVINCI-Silicon" className="btn btn-quiet lp-btn">View on GitHub</a>
            </div>
          </div>
        </section>
      </main>

      <footer className="lp-foot">
        <div className="lp-wrap lp-foot-row">
          <span className="wordmark"><Logo /></span>
          <span className="meta-text">© 2026 DaVINCI Silicon</span>
          <nav className="lp-foot-links" aria-label="Footer">
            <Link href="/evidence/">Evidence</Link>
            <a href="https://github.com/GLAZERadr/DaVINCI-Silicon">GitHub</a>
          </nav>
        </div>
      </footer>
    </div>
  );
}
