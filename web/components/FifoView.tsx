"use client";

import { useEffect, useMemo, useState } from "react";
import type { Trace, TraceTest } from "@/lib/run";

type Slot = { value: number | null; written: number | null }; // written = cycle that stored it
type Frame = { slots: Slot[]; wr: number; rd: number; wrote: number | null; read: number | null; blocked: boolean };

const hex = (v: number | null | undefined) => (v == null ? "–" : v.toString(16).toUpperCase().padStart(2, "0"));

// Replays the RTL's own wr_ptr/rd_ptr through the trace. A write landed when
// wr_ptr moved (the word is the din of that cycle); a read when rd_ptr moved.
function frames(test: TraceTest, depth: number): Frame[] | null {
  if (!test.cycles.some((c) => c.ptr)) return null;
  const out: Frame[] = [];
  let slots: Slot[] = Array.from({ length: depth }, () => ({ value: null, written: null }));
  let prev = { wr: 0, rd: 0 };
  for (const c of test.cycles) {
    const wr = c.ptr?.wr_ptr ?? prev.wr, rd = c.ptr?.rd_ptr ?? prev.rd;
    let wrote: number | null = null, read: number | null = null;
    if (c.in.rst) {
      slots = slots.map(() => ({ value: null, written: null }));
    } else {
      if (wr !== prev.wr) {
        wrote = prev.wr;
        slots = slots.map((s, i) => (i === prev.wr ? { value: c.in.din ?? null, written: c.k } : s));
      }
      if (rd !== prev.rd) read = prev.rd;
    }
    out.push({ slots, wr, rd, wrote, read, blocked: !c.in.rst && !!c.in.wr_en && wrote === null });
    prev = { wr, rd };
  }
  return out;
}

export default function FifoView({ trace, test, cycle, onTest, onCycle }:
  { trace: Trace; test: string; cycle: number; onTest: (t: string) => void; onCycle: (k: number) => void }) {
  const tt = trace.tests.find((x) => x.name === test) ?? trace.tests[0];
  const depth = trace.params.DEPTH;
  const fs = useMemo(() => (tt ? frames(tt, depth) : null), [tt, depth]);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(4);
  const cyc = tt?.cycles ?? [];
  const idx = Math.max(0, cyc.findIndex((c) => c.k === cycle));

  useEffect(() => {
    if (!playing || !cyc.length) return;
    if (idx >= cyc.length - 1) { setPlaying(false); return; }
    const t = setTimeout(() => onCycle(cyc[idx + 1].k), 1000 / speed);
    return () => clearTimeout(t);
  }, [playing, idx, speed, cyc, onCycle]);

  if (!tt) return <p className="c-empty">No trace for this attempt.</p>;
  const c = cyc[idx];
  const f = fs?.[idx];
  const occupied = new Set<number>();
  if (f && c.out.count != null) for (let i = 0; i < c.out.count; i++) occupied.add((f.rd + i) % depth);

  const R = 100, CX = 160, CY = 160, BOX = 28;
  const at = (i: number) => {
    const a = (i / depth) * Math.PI * 2 - Math.PI / 2;
    return { x: CX + R * Math.cos(a), y: CY + R * Math.sin(a), a };
  };
  const arrow = (i: number, cls: string, label: string) => {
    const p = at(i), r2 = R + 32;
    const q = { x: CX + r2 * Math.cos(p.a), y: CY + r2 * Math.sin(p.a) };
    return (
      <g className={cls}>
        <line x1={q.x} y1={q.y} x2={CX + (R + 19) * Math.cos(p.a)} y2={CY + (R + 19) * Math.sin(p.a)} />
        <text x={CX + (r2 + 11) * Math.cos(p.a)} y={CY + (r2 + 11) * Math.sin(p.a) + 4} textAnchor="middle">{label}</text>
      </g>
    );
  };
  const flags = ["full", "empty", "almost_full", "overflow", "underflow"];

  return (
    <div className="fifo">
      <div className="wf-bar">
        <label className="wf-test">
          <span className="label">Test</span>
          <select value={tt.name} onChange={(e) => { setPlaying(false); onTest(e.target.value); }}>
            {trace.tests.map((x) => <option key={x.name} value={x.name}>{x.passed ? "✓" : "✕"} {x.name}</option>)}
          </select>
        </label>
        <div className="fifo-controls" role="group" aria-label="Replay controls">
          <button type="button" className="btn btn-quiet btn-sm" onClick={() => { setPlaying(false); onCycle(cyc[0].k); }} aria-label="First cycle">⏮</button>
          <button type="button" className="btn btn-quiet btn-sm" onClick={() => { setPlaying(false); onCycle(cyc[Math.max(0, idx - 1)].k); }} aria-label="Previous cycle">←</button>
          <button type="button" className="btn btn-sm" onClick={() => { if (idx >= cyc.length - 1) onCycle(cyc[0].k); setPlaying(!playing); }}>{playing ? "Pause" : "Play"}</button>
          <button type="button" className="btn btn-quiet btn-sm" onClick={() => { setPlaying(false); onCycle(cyc[Math.min(cyc.length - 1, idx + 1)].k); }} aria-label="Next cycle">→</button>
          {tt.first_mismatch && <button type="button" className="btn btn-quiet btn-sm" onClick={() => { setPlaying(false); onCycle(tt.first_mismatch!); }}>Jump to mismatch</button>}
          <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} aria-label="Speed" className="fifo-speed">
            {[1, 2, 4, 8, 16].map((s) => <option key={s} value={s}>{s} cycles/s</option>)}
          </select>
        </div>
      </div>
      <input type="range" min={0} max={cyc.length - 1} value={idx} onChange={(e) => { setPlaying(false); onCycle(cyc[Number(e.target.value)].k); }}
        aria-label={`Cycle ${c.k} of ${tt.cycles_total}`} className="fifo-slider" />

      <div className="fifo-stage">
        {fs && f ? (
          <svg viewBox="0 0 320 320" className="fifo-ring" role="img"
            aria-label={`FIFO at cycle ${c.k}: ${c.out.count} of ${depth} slots used, write pointer ${f.wr}, read pointer ${f.rd}`}>
            <circle cx={CX} cy={CY} r={R} className="fifo-track" />
            {Array.from({ length: depth }, (_, i) => {
              const p = at(i);
              const cls = ["fifo-slot", occupied.has(i) ? "on" : "", f.wrote === i ? "wrote" : "", f.read === i ? "read" : ""].join(" ");
              return (
                <g key={i} transform={`translate(${p.x - BOX / 2},${p.y - BOX / 2})`} className={cls}>
                  <rect width={BOX} height={BOX} rx={6} />
                  <text x={BOX / 2} y={BOX / 2 + 4} textAnchor="middle">{occupied.has(i) ? hex(f.slots[i].value) : ""}</text>
                  <text x={BOX / 2} y={BOX + 11} textAnchor="middle" className="fifo-idx">{i}</text>
                </g>
              );
            })}
            {arrow(f.wr, "fifo-ptr wr", "wr")}
            {arrow(f.rd, "fifo-ptr rd", "rd")}
            <text x={CX} y={CY - 8} textAnchor="middle" className="fifo-count">{c.out.count ?? "x"}<tspan className="fifo-of">/{depth}</tspan></text>
            <text x={CX} y={CY + 14} textAnchor="middle" className="fifo-sub">count · measured</text>
            {c.mismatch.includes("count") && <text x={CX} y={CY + 32} textAnchor="middle" className="fifo-bad">golden model: {c.exp.count}</text>}
          </svg>
        ) : (
          <p className="c-empty">This RTL has no signals named wr_ptr / rd_ptr, so the ring cannot be drawn from its own state. The waveform still shows every port.</p>
        )}

        <div className="fifo-side">
          <p className="label">Cycle {c.k} of {tt.cycles_total}{tt.truncated ? " (window)" : ""}</p>
          <ul className="fifo-events">
            <li className={c.in.rst ? "on" : ""}>rst {c.in.rst ? "· reset" : ""}</li>
            <li className={c.in.wr_en ? "on" : ""}>wr_en {c.in.wr_en ? `· din ${hex(c.in.din)}` : ""}{f?.wrote != null ? ` → stored in slot ${f.wrote}` : ""}{f?.blocked ? <span className="mark-fail"> · ✕ write not stored</span> : null}</li>
            <li className={c.in.rd_en ? "on" : ""}>rd_en {f?.read != null ? `· read slot ${f.read} → dout ${hex(c.out.dout)}` : c.in.rd_en ? "· nothing read" : ""}</li>
          </ul>
          <div className="fifo-flags" aria-label="Output flags (measured)">
            {flags.map((fl) => (
              <span key={fl} className={`fifo-flag ${c.out[fl] ? "lit" : ""} ${c.mismatch.includes(fl) ? "bad" : ""}`}>{fl}{c.mismatch.includes(fl) ? " ✕" : ""}</span>
            ))}
          </div>
          {c.mismatch.length > 0
            ? <p className="measured fail"><span className="label">Measured vs golden model</span>✕ {c.mismatch.map((m) => `${m}: ${c.out[m]} (expected ${c.exp[m]})`).join(" · ")}</p>
            : <p className="measured pass"><span className="label">Measured vs golden model</span>✓ matches on this cycle</p>}
          <p className="meta-text">Slots and pointers come from the RTL&apos;s own <span className="mono">wr_ptr</span>/<span className="mono">rd_ptr</span> in the simulator waveform; a slot shows the din of the cycle the write pointer moved past it. Measured, not an illustration.</p>
        </div>
      </div>
    </div>
  );
}
