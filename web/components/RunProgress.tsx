"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiBase } from "@/lib/api";
import { type Json, status } from "@/lib/run";

type Ev = Json & { type: string };

// One line per pipeline event, as the server streams them (GET /runs/{id}/events).
function line(e: Ev): { mark: string; tone: string; text: string; ai?: boolean } {
  const n = e.attempt ? `Attempt ${e.attempt}: ` : "";
  switch (e.type) {
    case "queued": return { mark: "○", tone: "mark-neutral", text: "Queued behind another run" };
    case "run_started": return { mark: "○", tone: "mark-neutral", text: `Started · generate ${e.generate}, repair ${e.repair}${e.seed_bug ? ` · seeded bug ${e.seed_bug}` : ""}` };
    case "seeded": return { mark: "○", tone: "mark-neutral", text: `${n}reference RTL with seeded bug ${e.mutant} (${e.desc})` };
    case "model_call": return { mark: "○", tone: "mark-neutral", text: `${n}asking ${e.provider} to ${e.step === "repair" ? "repair the RTL from the measured failures" : "write the RTL"}` };
    case "diagnosis": return { mark: "○", tone: "mark-neutral", text: `${n}${e.text}`, ai: true };
    case "rejected": return { mark: "✕", tone: "mark-fail", text: `${n}rejected before simulation: ${e.reason ?? e.error ?? "static check"}` };
    case "truncated": return { mark: "✕", tone: "mark-fail", text: `${n}reply cut off at the token limit` };
    case "simulating": return { mark: "○", tone: "mark-neutral", text: `${n}simulating against the frozen suite` };
    case "verdict": return { mark: e.status === "pass" ? "✓" : "✕", tone: e.status === "pass" ? "mark-pass" : "mark-fail", text: `${n}${e.passed}/${e.total} frozen tests · measured` };
    case "sweeping": return { mark: "○", tone: "mark-neutral", text: `${n}parameter sweep (never shown to the model)` };
    case "sweep": return { mark: e.status === "pass" ? "✓" : "✕", tone: e.status === "pass" ? "mark-pass" : "mark-fail", text: `${n}sweep ${e.status} · measured` };
    case "no_progress": return { mark: "✕", tone: "mark-fail", text: `${n}same design as attempt ${e.same_as}; stopping` };
    case "aborted": return { mark: "○", tone: "mark-neutral", text: `Aborted: ${e.error ?? e.reason ?? ""}` };
    case "run_finished": return { mark: status(e.status).mark, tone: status(e.status).tone === "pass" ? "mark-pass" : status(e.status).tone === "fail" ? "mark-fail" : "mark-neutral", text: `Finished: ${status(e.status).word} · ${e.attempts} attempt(s) · $${Number(e.cost_usd ?? 0).toFixed(4)}` };
    default: return { mark: "○", tone: "mark-neutral", text: `${e.type} ${JSON.stringify(e)}` };
  }
}

export default function RunProgress({ runId }: { runId: string }) {
  const [events, setEvents] = useState<Ev[]>([]);
  const [end, setEnd] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setEvents([]);
    setEnd(null);
    setError(null);
    const src = new EventSource(`${apiBase()}/runs/${encodeURIComponent(runId)}/events`);
    const add = (m: MessageEvent, type: string) => {
      try {
        setEvents((xs) => [...xs, { type, ...JSON.parse(m.data) }]);
      } catch { /* ignore malformed lines */ }
    };
    const types = ["queued", "run_started", "seeded", "model_call", "diagnosis", "rejected", "truncated", "simulating",
                   "verdict", "sweeping", "sweep", "no_progress", "aborted", "run_finished"];
    types.forEach((t) => src.addEventListener(t, (m) => add(m as MessageEvent, t)));
    src.addEventListener("end", (m) => {
      try { setEnd(JSON.parse((m as MessageEvent).data).status ?? "done"); } catch { setEnd("done"); }
      src.close();
    });
    src.onerror = () => {
      if (src.readyState === EventSource.CLOSED) setError("Lost the event stream; the run continues on the server.");
    };
    return () => src.close();
  }, [runId]);

  const st = end ? status(end) : null;
  return (
    <section className="card" aria-live="polite">
      <div className="api-row">
        <p className="label">Progress · <span className="mono">{runId}</span></p>
        {st ? <span className={`pill ${st.tone}`}>{st.mark} {st.word}</span> : <span className="mark-neutral">○ Running…</span>}
      </div>
      <ol className="timeline">
        {events.map((e, i) => {
          const l = line(e);
          return (
            <li key={i} className={l.ai ? "timeline-ai" : undefined}>
              <span className="mono timeline-t">{typeof e.t === "number" ? `${e.t.toFixed(1)}s` : ""}</span>
              <span className={l.tone} aria-hidden="true">{l.mark}</span>
              <span>{l.ai ? <><span className="label">AI interpretation · not verified </span>{l.text}</> : l.text}</span>
            </li>
          );
        })}
        {events.length === 0 && !error && <li className="mark-neutral">○ Waiting for the first event…</li>}
      </ol>
      {error && <p className="mark-fail">✕ {error}</p>}
      {end && (
        <p style={{ marginTop: 16 }}>
          <Link className="btn" href={`/console/?run=${encodeURIComponent(runId)}`}>Open in Run Console</Link>
        </p>
      )}
    </section>
  );
}
