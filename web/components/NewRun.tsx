"use client";

import { useEffect, useState } from "react";
import ApiPanel from "./ApiPanel";
import RunProgress from "./RunProgress";
import { api } from "@/lib/api";
import type { Json } from "@/lib/run";

type Mutant = { id: string; req: string; desc: string };
type Mode = "replay" | "fake" | "live";

// Start a run through the API and follow it live.
export default function NewRun({ mutants, recorded }: { mutants: Mutant[]; recorded: string[] }) {
  const [apiOk, setApiOk] = useState(false);
  const [hasToken, setHasToken] = useState(false);
  const [mode, setMode] = useState<Mode>("replay");
  const [source, setSource] = useState(recorded[0] ?? "");
  const [sources, setSources] = useState<string[]>(recorded);
  const [seed, setSeed] = useState("M1");
  const [repairs, setRepairs] = useState(3);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [watch, setWatch] = useState<string | null>(null);

  useEffect(() => {
    const w = new URLSearchParams(window.location.search).get("watch");
    if (w) setWatch(w);
  }, []);

  useEffect(() => {
    if (!apiOk) return;
    // Runs a live model answered, which are the ones worth replaying.
    api("/runs").then((r) => {
      const live = r.runs.filter((x: Json) => !x.replayed_from && ["meta", "baseten"].includes(x.providers?.generate)
        && Number(x.cost_usd ?? 0) > 0 && x.status !== "aborted")
        .map((x: Json) => x.run_id as string);
      const all = Array.from(new Set([...recorded, ...live]));
      setSources(all);
      if (!all.includes(source)) setSource(all[0] ?? "");
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiOk]);

  async function start(e: React.FormEvent) {
    e.preventDefault();
    if (mode === "live" && !window.confirm(
      "Start a paid live run on Muse Spark 1.3?\n\nRecorded live runs cost $0.008–$0.051 each; every call is counted in the ledger against the $120 budget.")) return;
    setBusy(true);
    setError(null);
    try {
      const body = { provider: mode === "live" ? "meta" : "fake", seed_bug: seed || null, max_repairs: repairs };
      const r = mode === "replay"
        ? await api(`/runs/${encodeURIComponent(source)}/replay`, { method: "POST" })
        : await api("/runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      setWatch(r.run_id);
      window.history.replaceState(null, "", `?watch=${encodeURIComponent(r.run_id)}`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const needsToken = mode === "live" && !hasToken;
  return (
    <main className="board">
      <section className="title-block">
        <p className="eyebrow">New run</p>
        <h1 className="display-title">Start a run. <span className="tone-2">The model writes RTL; the frozen tests, the sweep and the sandbox decide.</span></h1>
      </section>
      <ApiPanel onChange={(ok, tok) => { setApiOk(ok); setHasToken(tok); }} />

      <section className="card">
        <p className="label">Run settings</p>
        <p className="lede">Every attempt is recorded, including rejected and failed ones. The server always simulates model-written RTL in its Docker sandbox; this page cannot change that.</p>
        <form className="run-form" onSubmit={start}>
          <fieldset>
            <legend className="label">Model</legend>
            <label className="choice">
              <input type="radio" name="mode" checked={mode === "replay"} onChange={() => setMode("replay")} />
              <span><strong>Replay a recorded run</strong> · $0 · the recorded model output, simulated again</span>
            </label>
            <label className="choice">
              <input type="radio" name="mode" checked={mode === "fake"} onChange={() => setMode("fake")} />
              <span><strong>Offline dry run</strong> · $0 · a scripted stand-in model, to exercise the loop</span>
            </label>
            <label className="choice">
              <input type="radio" name="mode" checked={mode === "live"} onChange={() => setMode("live")} />
              <span><strong>Live: Muse Spark 1.3</strong> · paid, counted in the ledger · needs the API token</span>
            </label>
          </fieldset>
          {mode === "replay" ? (
            <label>
              <span className="label">Recorded run</span>
              <select value={source} onChange={(e) => setSource(e.target.value)}>
                {sources.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
          ) : (
            <div className="run-form-row">
              <label>
                <span className="label">Seeded bug (attempt 1)</span>
                <select value={seed} onChange={(e) => setSeed(e.target.value)}>
                  <option value="">None: the model writes attempt 1</option>
                  {mutants.map((m) => <option key={m.id} value={m.id}>{m.id} · {m.req} · {m.desc}</option>)}
                </select>
              </label>
              <label>
                <span className="label">Repairs allowed</span>
                <select value={repairs} onChange={(e) => setRepairs(Number(e.target.value))}>
                  {[0, 1, 2, 3].map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
              </label>
            </div>
          )}
          {needsToken && <p className="mark-neutral">○ Add the API token under Connection settings to start a live run.</p>}
          {error && <p className="mark-fail" role="alert">✕ {error}</p>}
          <div>
            <button type="submit" className={`btn ${mode === "live" ? "btn-live" : ""}`} disabled={!apiOk || busy || needsToken || (mode === "replay" && !source)}>
              {busy ? "Starting…" : mode === "replay" ? "Replay · $0" : mode === "fake" ? "Start dry run · $0" : "Start live run · paid"}
            </button>
          </div>
        </form>
      </section>


      {watch && apiOk && <RunProgress runId={watch} />}
    </main>
  );
}
