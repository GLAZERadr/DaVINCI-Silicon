"use client";

import { useEffect, useRef, useState } from "react";
import ModelAvatar from "./ModelAvatar";
import Waveform, { pickTest } from "./Waveform";
import type { LandingData } from "./Landing";

// Landing hero visual: the real Run Console waveform of the recorded failure (same
// component and trace the app uses), next to the run's attempt timeline.
export default function ProductDemo({ data }: { data: LandingData }) {
  const tr = data.trace!;
  const s = data.story!;
  const [test, setTest] = useState(pickTest(tr));
  const tt = tr.tests.find((x) => x.name === test);
  const [cycle, setCycle] = useState(tt?.first_mismatch ?? tt?.cycles[0]?.k ?? 0);
  const wave = useRef<HTMLDivElement>(null);
  // On a narrow screen the waveform scrolls sideways: start at the mismatch, not at cycle 1.
  useEffect(() => {
    const id = requestAnimationFrame(() => {
      const sc = wave.current?.querySelector<HTMLElement>(".wf-scroll");
      if (sc && sc.scrollWidth > sc.clientWidth) sc.scrollLeft = sc.scrollWidth;
    });
    return () => cancelAnimationFrame(id);
  }, []);
  // The model's diagnosis, cut at a sentence or clause boundary rather than mid-identifier.
  const diag = (s.diagnosis ?? "").replace(/`/g, "");
  const cut = diag.search(/[;.](\s|$)/);
  const short = cut > 40 && cut < 220 ? diag.slice(0, cut + 1) : diag.slice(0, 160);
  return (
    <figure className="pd" aria-label={`Run Console for recorded run ${data.runId}`}>
      <div className="pd-chrome">
        <span className="pd-url mono">sync_fifo / <strong>{data.runId}</strong> / Run Console</span>
        <span className="tag-measured">recorded run</span>
      </div>
      <div className="pd-body">
        <div className="pd-wave" ref={wave}><Waveform trace={tr} test={test} cycle={cycle} onTest={setTest} onCycle={setCycle} /></div>
        <aside className="pd-side">
          <p className="pd-side-h">Attempts</p>
          <ol className="pd-tl">
            <li>
              <span className="pd-dot fail" aria-hidden="true">✕</span>
              <div><strong>#1 · {s.failPassed}/{s.total} tests</strong>
                <span className="pd-sub">{s.seeded ? `bug ${s.seeded} planted on purpose` : "first attempt"}</span></div>
            </li>
            {s.diagnosis && (
              <li className="pd-ai">
                <ModelAvatar model={s.model} />
                <div><span className="tag-ai">AI interpretation · not verified</span>
                  <p>{short}{short.length < diag.length ? " …" : ""}</p></div>
              </li>
            )}
            <li>
              <span className="pd-dot pass" aria-hidden="true">✓</span>
              <div><strong>#2 · {s.fixPassed}/{s.total} tests</strong><span className="pd-sub">repaired by {s.model}</span></div>
            </li>
          </ol>
          <p className="pd-foot"><span className="mark-pass">✓ Pass · measured</span><span className="meta-text">{s.seconds != null ? `${s.seconds.toFixed(1)} s` : ""} · ${s.costUsd.toFixed(4)}</span></p>
        </aside>
      </div>
      <figcaption className="pd-cap">Recorded run {data.runId}: the frozen test catches the planted bug at cycle {tt?.first_mismatch ?? "—"} (red), Muse Spark repairs it, every test passes. Step through the cycles or jump to the mismatch.</figcaption>
    </figure>
  );
}
