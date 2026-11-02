"use client";

import { type Trace, type TraceTest, simShort } from "@/lib/run";

const CELL = 30; // px per clock cycle
const ROW = 26;
const PAD = 5;

type Row = { key: string; label: string; kind: "bit" | "bus" | "clk"; get: (c: TraceTest["cycles"][number]) => number | null | undefined;
  group: "in" | "out" | "exp" | "ptr"; cmp?: string };

const hex = (v: number | null | undefined) => (v == null ? "x" : v.toString(16).toUpperCase());
// Readout values carry their radix, so measured and expected never look like different units.
const h0x = (v: number | null | undefined) => (v == null ? "x" : `0x${hex(v)}`);

function rows(t: Trace, test: TraceTest): Row[] {
  const r: Row[] = [
    { key: "clk", label: "clk", kind: "clk", get: () => 1, group: "in" },
    { key: "rst", label: "rst", kind: "bit", get: (c) => c.in.rst, group: "in" },
    { key: "wr_en", label: "wr_en", kind: "bit", get: (c) => c.in.wr_en, group: "in" },
    { key: "din", label: "din", kind: "bus", get: (c) => c.in.din, group: "in" },
    { key: "rd_en", label: "rd_en", kind: "bit", get: (c) => c.in.rd_en, group: "in" },
    ...["full", "empty", "almost_full", "overflow", "underflow"].map((f) => ({ key: f, label: f, kind: "bit" as const, get: (c: TraceTest["cycles"][number]) => c.out[f], group: "out" as const, cmp: f })),
    { key: "count", label: "count", kind: "bus", get: (c) => c.out.count, group: "out", cmp: "count" },
    { key: "count_exp", label: "count (expected)", kind: "bus", get: (c) => c.exp.count, group: "exp" },
    { key: "dout", label: "dout", kind: "bus", get: (c) => c.out.dout, group: "out", cmp: "dout" },
  ];
  if (test.cycles.some((c) => c.ptr)) {
    r.push({ key: "wr_ptr", label: "wr_ptr (RTL)", kind: "bus", get: (c) => c.ptr?.wr_ptr, group: "ptr" },
           { key: "rd_ptr", label: "rd_ptr (RTL)", kind: "bus", get: (c) => c.ptr?.rd_ptr, group: "ptr" });
  }
  void t;
  return r;
}

function BitWave({ vals }: { vals: (number | null | undefined)[] }) {
  const hi = PAD, lo = ROW - PAD;
  let d = "";
  vals.forEach((v, i) => {
    const x0 = i * CELL, x1 = x0 + CELL;
    const y = v == null ? (hi + lo) / 2 : v ? hi : lo;
    d += i === 0 ? `M${x0},${y}` : `L${x0},${y}`;
    d += ` L${x1},${y}`;
  });
  return <path d={d} className="wf-bit" />;
}

function ClkWave({ n }: { n: number }) {
  const hi = PAD, lo = ROW - PAD;
  let d = `M0,${lo}`;
  for (let i = 0; i < n; i++) {
    const x = i * CELL;
    d += ` L${x},${lo} L${x},${hi} L${x + CELL / 2},${hi} L${x + CELL / 2},${lo}`;
  }
  d += ` L${n * CELL},${lo}`;
  return <path d={d} className="wf-clk" />;
}

function BusWave({ vals, dashed }: { vals: (number | null | undefined)[]; dashed?: boolean }) {
  const segs: { v: number | null | undefined; a: number; b: number }[] = [];
  vals.forEach((v, i) => {
    const last = segs[segs.length - 1];
    if (last && last.v === v) last.b = i + 1;
    else segs.push({ v, a: i, b: i + 1 });
  });
  const hi = PAD, lo = ROW - PAD, mid = ROW / 2, s = 4;
  return (
    <g className={dashed ? "wf-bus wf-exp" : "wf-bus"}>
      {segs.map((g, k) => {
        const x0 = g.a * CELL, x1 = g.b * CELL;
        const p = `M${x0},${mid} L${x0 + s},${hi} L${x1 - s},${hi} L${x1},${mid} L${x1 - s},${lo} L${x0 + s},${lo} Z`;
        return (
          <g key={k}>
            <path d={p} className={g.v == null ? "wf-x" : undefined} />
            {(x1 - x0) >= 18 && <text x={(x0 + x1) / 2} y={mid + 4} textAnchor="middle">{hex(g.v)}</text>}
          </g>
        );
      })}
    </g>
  );
}

export function pickTest(t: Trace): string {
  return (t.tests.find((x) => !x.passed) ?? t.tests[0])?.name ?? "";
}

export default function Waveform({ trace, test, cycle, onTest, onCycle }:
  { trace: Trace; test: string; cycle: number; onTest: (t: string) => void; onCycle: (k: number) => void }) {
  const tt = trace.tests.find((x) => x.name === test) ?? trace.tests[0];
  if (!tt) return <p className="c-empty">No trace for this attempt.</p>;
  const cyc = tt.cycles;
  const rs = rows(trace, tt);
  const idx = Math.max(0, cyc.findIndex((c) => c.k === cycle));
  const cur = cyc[idx];
  const width = cyc.length * CELL;
  const bad = cyc.map((c, i) => (c.mismatch.length ? i : -1)).filter((i) => i >= 0);

  return (
    <div className="wf">
      <div className="wf-bar">
        <label className="wf-test">
          <span className="label">Test</span>
          <select value={tt.name} onChange={(e) => onTest(e.target.value)}>
            {trace.tests.map((x) => <option key={x.name} value={x.name}>{x.passed ? "✓" : "✕"} {x.name}</option>)}
          </select>
        </label>
        <span className="meta-text">
          {tt.cycles_total} cycles{tt.truncated ? ` · showing ${cyc.length} (start and around the first mismatch)` : ""}
          {tt.first_mismatch ? <> · <span className="mark-fail">✕ first mismatch at cycle {tt.first_mismatch}</span></> : <> · <span className="mark-pass">✓ matches the golden model on every cycle</span></>}
        </span>
        <span className="wf-legend meta-text"><span className="wf-sw wf-sw-meas" /> measured <span className="wf-sw wf-sw-exp" /> golden model <span className="wf-sw wf-sw-bad" /> mismatch</span>
      </div>
      <div className="wf-body">
        <div className="wf-labels" aria-hidden="true">
          <div className="wf-ruler-label">cycle</div>
          {rs.map((r) => <div key={r.key} className={`wf-label wf-g-${r.group}`}>{r.label}</div>)}
        </div>
        <div className="wf-scroll">
          <svg width={width} height={(rs.length + 1) * ROW} viewBox={`0 0 ${width} ${(rs.length + 1) * ROW}`} role="img"
            aria-label={`Waveform of ${tt.name}: ${cyc.length} cycles${tt.first_mismatch ? `, first mismatch at cycle ${tt.first_mismatch}` : ""}`}>
            {bad.map((i) => <rect key={`b${i}`} x={i * CELL} y={0} width={CELL} height={(rs.length + 1) * ROW} className="wf-badcol" />)}
            <rect x={idx * CELL} y={0} width={CELL} height={(rs.length + 1) * ROW} className="wf-cursor" />
            <g>
              {cyc.map((c, i) => (
                <text key={c.k} x={i * CELL + CELL / 2} y={ROW / 2 + 4} textAnchor="middle" className="wf-ruler">{c.k % 5 === 0 || i === 0 || c.mismatch.length ? c.k : ""}</text>
              ))}
            </g>
            {rs.map((r, ri) => {
              const vals = cyc.map(r.get);
              return (
                <g key={r.key} transform={`translate(0,${(ri + 1) * ROW})`}>
                  <line x1={0} x2={width} y1={ROW} y2={ROW} className="wf-grid" />
                  {r.cmp && cyc.map((c, i) => c.mismatch.includes(r.cmp!) ? <rect key={i} x={i * CELL} y={1} width={CELL} height={ROW - 2} className="wf-badcell" /> : null)}
                  {r.kind === "clk" ? <ClkWave n={cyc.length} /> : r.kind === "bit" ? <BitWave vals={vals} /> : <BusWave vals={vals} dashed={r.group === "exp"} />}
                </g>
              );
            })}
            {cyc.map((c, i) => (
              <rect key={`h${c.k}`} x={i * CELL} y={0} width={CELL} height={(rs.length + 1) * ROW} fill="transparent"
                onClick={() => onCycle(c.k)} style={{ cursor: "pointer" }}><title>cycle {c.k}</title></rect>
            ))}
          </svg>
        </div>
      </div>
      {cur && (
        <div className="wf-readout" aria-live="polite">
          <strong>Cycle {cur.k}</strong>
          <span>in: <span className="mono">rst={cur.in.rst} wr_en={cur.in.wr_en} din={h0x(cur.in.din)} rd_en={cur.in.rd_en}</span></span>
          <span>out: <span className="mono">count={h0x(cur.out.count)} full={cur.out.full} empty={cur.out.empty} dout={h0x(cur.out.dout)} ovf={cur.out.overflow} unf={cur.out.underflow}</span></span>
          {cur.mismatch.length > 0
            ? <span className="mark-fail">✕ {cur.mismatch.map((f) => `${f}: measured ${h0x(cur.out[f])}, golden model ${h0x(cur.exp[f])}`).join(" · ")}</span>
            : <span className="mark-pass">✓ matches the golden model</span>}
          <span className="btn-row">
            <button type="button" className="btn btn-quiet btn-sm" onClick={() => onCycle(cyc[Math.max(0, idx - 1)].k)} aria-label="Previous cycle">←</button>
            <button type="button" className="btn btn-quiet btn-sm" onClick={() => onCycle(cyc[Math.min(cyc.length - 1, idx + 1)].k)} aria-label="Next cycle">→</button>
            {tt.first_mismatch && <button type="button" className="btn btn-quiet btn-sm" onClick={() => onCycle(tt.first_mismatch!)}>Jump to mismatch</button>}
          </span>
        </div>
      )}
      <p className="wf-note meta-text">Each column is one rising clock edge: inputs as the DUT sampled them, outputs just after the edge (what the frozen test compares). Measured from the simulator waveform of the frozen tests; the expected lane is the golden model. The waveform is a fresh re-simulation of this RTL in the sandbox ({simShort(trace.simulator)}, suite <span className="mono">{trace.suite_sha256.slice(0, 10)}</span>), not the run&apos;s original log.</p>
    </div>
  );
}
