"use client";

// Learn mode for students: for a failing test, the requirement in plain words, the
// measured waveform at the first mismatch, and a question whose answer appears only
// on request. While the answer is hidden the Run Console locks the RTL fix (Diff,
// RTL, Prompt) and the AI diagnosis, so the view teaches instead of handing out code.
// Lesson text is generated once per requirement by agent/learn.py and stored in
// learn/<block>/; nothing here calls a model.
import { useEffect, useRef, useState } from "react";
import ModelAvatar from "./ModelAvatar";
import Waveform from "./Waveform";
import type { Requirement, TestResult, Trace } from "@/lib/run";
import s from "./LearnView.module.css";

const RANDOM = "test_random_regression";

export type LearnItem = {
  id: string;
  requirement: string;
  test: string;
  label: string;
  provider: string;
  model: string;
  costUsd: number;
  requestSha: string;
  content: { explanation: string; question: string; answer: string; signal: string; cycle: number; expected_value: number };
  check: { label: string; golden_value: number | null; answer_matches_golden: boolean; cycle_in_test: boolean };
};

export type LearnTarget = { req: string; test: string };

// Lessons that apply to this attempt: a failing directed test of a requirement with stored content.
export function learnTargets(failing: TestResult[], requirements: Requirement[], learn: Record<string, LearnItem>): LearnTarget[] {
  const out: LearnTarget[] = [];
  for (const t of failing) {
    if (t.name === RANDOM) continue;
    for (const r of requirements) if (r.tests.includes(t.name) && learn[r.id]) out.push({ req: r.id, test: t.name });
  }
  return out;
}

export function useLearn(runId: string, attempt: number | undefined, targets: LearnTarget[]) {
  const [on, setOn] = useState(false);
  const [pick, setPick] = useState<string | null>(null);
  const [revealed, setRevealed] = useState<Set<string>>(() => new Set());
  const target = targets.find((t) => t.req === pick) ?? targets[0];
  const key = target ? `${runId}/${attempt}/${target.req}` : "";
  const isRevealed = !!key && revealed.has(key);
  return {
    on, setOn, target, key, isRevealed, setPick,
    locked: on && !!target && !isRevealed,
    reveal: () => setRevealed((r) => new Set(r).add(key)),
  };
}

export function LearnToggle({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className={s.toggleRow}>
      <button type="button" className={`${s.toggle} ${on ? s.toggleOn : ""}`} aria-pressed={on} onClick={() => onChange(!on)}>
        <span className={s.knob} aria-hidden="true" />
        Learn mode
      </button>
      <span className="meta-text">{on ? "On: the fix stays hidden until you answer." : "For students: think through a failure first."}</span>
    </div>
  );
}

export function LockedNote() {
  return (
    <div className="measured">
      <p className="label">Learn mode · diagnosis hidden</p>
      <p>The AI diagnosis and the fix stay hidden until you reveal the answer to the question.</p>
    </div>
  );
}

const fake = (p: string) => p === "fake";

export default function LearnView({ item, targets, target, onPick, trace, revealed, onReveal }: {
  item: LearnItem | undefined; targets: LearnTarget[]; target: LearnTarget | undefined; onPick: (req: string) => void;
  trace: Trace | null; revealed: boolean; onReveal: () => void;
}) {
  const [wave, setWave] = useState<{ test: string; cycle: number } | null>(null);
  const answerRef = useRef<HTMLDivElement>(null);
  const wasRevealed = useRef(revealed);
  useEffect(() => { // move focus to the answer once, when it is revealed
    if (revealed && !wasRevealed.current) answerRef.current?.focus();
    wasRevealed.current = revealed;
  }, [revealed]);
  if (!target || !item) {
    return <p className="c-empty">○ No lesson for this attempt: none of its failing directed tests has stored Learn content{targets.length ? "" : " (or every test passes)"}.</p>;
  }
  const c = item.content;
  const tt = trace?.tests.find((x) => x.name === target.test);
  const firstBad = tt?.first_mismatch ?? null;
  const shown = wave ?? { test: target.test, cycle: firstBad ?? c.cycle };
  const asked = tt?.cycles.find((x) => x.k === c.cycle);
  const measuredAt = asked ? asked.out[c.signal] : undefined;
  const golden = item.check.golden_value;
  const ansId = `learn-answer-${item.id}`;

  return (
    <div className={s.learn}>
      {targets.length > 1 && (
        <div className={s.picker} role="radiogroup" aria-label="Which requirement to learn">
          {targets.map((t) => (
            <button key={t.req} type="button" role="radio" aria-checked={t.req === target.req} className="c-switch-btn"
              onClick={() => { onPick(t.req); setWave(null); }}>
              <span className="mono">{t.req}</span> <span className="meta-text">· {t.test}</span>
            </button>
          ))}
        </div>
      )}

      <section className={s.step} aria-labelledby="learn-1">
        <h2 id="learn-1" className={s.h}>1 · What the requirement says</h2>
        <div className="measured">
          <p className="label">Requirement {item.id} · frozen spec</p>
          <p className={s.p}>{item.requirement}</p>
          <p className="meta-text">Checked by <span className="mono">{target.test}</span>, which fails on this attempt (measured).</p>
        </div>
        <div className="ai">
          <p className="ai-head"><ModelAvatar model={item.model} size={20} /><strong>{item.model}</strong>{fake(item.provider) ? <span className="meta-text"> · fake provider, not a model</span> : null}</p>
          <p className="label">{item.label} · in plain words</p>
          <p className={s.p}>{c.explanation}</p>
        </div>
      </section>

      <section className={s.step} aria-labelledby="learn-2">
        <h2 id="learn-2" className={s.h}>2 · What the simulator saw</h2>
        <p className="meta-text">Measured waveform of this attempt, opened at {firstBad ? `the first mismatch (cycle ${firstBad})` : `cycle ${c.cycle}`}.
          {asked && firstBad !== c.cycle ? <> The question asks about cycle {c.cycle}.{" "}
            <button type="button" className="btn btn-quiet btn-sm" onClick={() => setWave({ test: target.test, cycle: c.cycle })}>Go to cycle {c.cycle}</button></> : null}
        </p>
        {trace ? (
          <div className={s.wave}>
            <Waveform trace={trace} test={shown.test} cycle={shown.cycle}
              onTest={(t) => setWave({ test: t, cycle: trace.tests.find((x) => x.name === t)?.first_mismatch ?? 1 })}
              onCycle={(k) => setWave({ test: shown.test, cycle: k })} />
          </div>
        ) : <p className="mark-neutral">○ No trace recorded for this attempt.</p>}
      </section>

      <section className={s.step} aria-labelledby="learn-3">
        <h2 id="learn-3" className={s.h}>3 · Your turn</h2>
        <div className="ai">
          <p className="label">{item.label} · question</p>
          <p className={s.q}>{c.question}</p>
          <p className="meta-text">Think it through using the waveform before you look.</p>
        </div>
        {!revealed ? (
          <div className={s.reveal}>
            <button type="button" className="btn" aria-expanded={false} aria-controls={ansId} onClick={onReveal}>Show the answer</button>
            <span className="meta-text">The fix (Diff, RTL and Prompt tabs) and the AI diagnosis unlock after this.</span>
          </div>
        ) : (
          <div id={ansId} className={s.answer} tabIndex={-1} ref={answerRef}>
            <div className="ai">
              <p className="label">{item.label} · answer</p>
              <p className={s.p}>{c.answer}</p>
            </div>
            <div className="measured">
              <p className="label">Measured · <span className="mono">{c.signal}</span> at cycle {c.cycle}</p>
              <p className={s.p}>
                Golden model (reference trace): <span className="mono">{golden ?? "n/a"}</span>
                {" · "}{item.check.answer_matches_golden
                  ? <span className="mark-pass">✓ the answer&apos;s value agrees</span>
                  : <span className="mark-fail">✕ the answer&apos;s value ({c.expected_value}) disagrees</span>}
              </p>
              <p className={s.p}>
                This attempt: {measuredAt === undefined ? <span className="mark-neutral">○ cycle not in the recorded trace</span>
                  : <><span className="mono">{measuredAt ?? "x"}</span>{" · "}{measuredAt === golden
                    ? <span className="mark-pass">✓ matches the golden model</span>
                    : <span className="mark-fail">✕ differs from the golden model</span>}</>}
              </p>
            </div>
            <p className="meta-text">Unlocked: the Diff, RTL and Prompt tabs and the AI diagnosis for this attempt.</p>
          </div>
        )}
      </section>

      <p className="meta-text">Lesson stored in <span className="mono">learn/sync_fifo/{item.id}.json</span> · {item.provider} · {item.model} · ${item.costUsd.toFixed(4)} · request <span className="mono">{item.requestSha.slice(0, 10)}</span>. Generated once by <span className="mono">agent/learn.py</span>; no model call when you view it.</p>
    </div>
  );
}
