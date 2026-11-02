"use client";

import { useCallback, useEffect, useState } from "react";
import BreakdownView from "./BreakdownView";
import RunProgress from "./RunProgress";
import { api } from "@/lib/api";
import type { Json } from "@/lib/run";

// S1: design breakdown before RTL. Propose (AI) → a person approves → RTL is generated against it.
export default function BreakdownPanel({ apiOk, hasToken }: { apiOk: boolean; hasToken: boolean }) {
  const [list, setList] = useState<Json[]>([]);
  const [bid, setBid] = useState<string | null>(null);
  const [rec, setRec] = useState<Json | null>(null);
  const [provider, setProvider] = useState<"meta" | "fake">("meta");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api("/breakdowns").then((r) => setList([...r.running, ...r.breakdowns])).catch(() => {});
  }, []);

  const open = useCallback(async (id: string) => {
    setBid(id);
    setRunId(null);
    setError(null);
    try {
      setRec(await api(`/breakdowns/${encodeURIComponent(id)}`));
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => { if (apiOk) refresh(); }, [apiOk, refresh]);
  useEffect(() => {
    if (!bid || !rec || rec.status !== "running") return;
    const t = setTimeout(() => open(bid), 2000);
    return () => clearTimeout(t);
  }, [bid, rec, open]);

  async function act(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try { await fn(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  const create = () => act(async () => {
    const r = await api("/breakdowns", { method: "POST", headers: { "Content-Type": "application/json" },
                                         body: JSON.stringify({ provider }) });
    refresh();
    await open(r.breakdown_id);
  });
  const approve = () => act(async () => {
    setRec(await api(`/breakdowns/${encodeURIComponent(bid!)}/approve`, { method: "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({ approved_by: name }) }));
    refresh();
  });
  const run = (p: "meta" | "fake") => act(async () => {
    if (p === "meta" && !window.confirm("Start a paid live run on Muse Spark 1.3 with this breakdown?")) return;
    const r = await api("/runs", { method: "POST", headers: { "Content-Type": "application/json" },
                                   body: JSON.stringify({ provider: p, breakdown_id: bid }) });
    setRunId(r.run_id);
  });

  const approved = rec?.approved as Json | undefined;
  return (
    <section className="card" aria-labelledby="bd-title">
      <p id="bd-title" className="label">Design breakdown before RTL</p>
      <p className="lede">Before any RTL, Muse Spark proposes the microarchitecture for the approved requirements: the state it will hold with widths, the pointer scheme, control vs datapath, and which requirement each element serves. A person approves it; the approved breakdown goes into the RTL prompt, and after the run DaVINCI measures which elements made it into the final RTL.</p>
      <div className="run-form-row">
        <label className="run-form" style={{ gap: 6 }}>
          <span className="label">Proposed by</span>
          <select value={provider} onChange={(e) => setProvider(e.target.value as "meta" | "fake")}>
            <option value="meta">Muse Spark 1.3 · live, about $0.05 · needs token</option>
            <option value="fake">Offline stand-in · $0</option>
          </select>
        </label>
        <div style={{ alignSelf: "end" }}>
          <button type="button" className="btn" disabled={!apiOk || busy || (provider === "meta" && !hasToken)} onClick={create}>
            Propose a breakdown (default spec)
          </button>
        </div>
      </div>
      {list.length > 0 && (
        <div className="table-wrap" style={{ marginTop: 16 }}>
          <table>
            <thead><tr><th>Breakdown</th><th>Provider</th><th>Status</th><th>Cost</th></tr></thead>
            <tbody>
              {list.map((b) => (
                <tr key={b.breakdown_id} className="row-link" onClick={() => open(b.breakdown_id)}>
                  <td className="mono">{b.breakdown_id}</td>
                  <td>{b.provider}</td>
                  <td>{b.approved ? <span className="mark-pass">✓ Approved</span> : <span className="mark-neutral">○ {b.status === "awaiting_approval" ? "Awaiting approval" : b.status}</span>}</td>
                  <td>{b.cost_usd != null ? `$${Number(b.cost_usd).toFixed(3)}` : "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {error && <p className="mark-fail" role="alert">✕ {error}</p>}
      {rec?.status === "running" && <p className="mark-neutral">○ Muse Spark is breaking the design down…</p>}
      {rec?.status === "aborted" && <p className="mark-fail">✕ {rec.error}</p>}
      {rec?.breakdown && (
        <div style={{ marginTop: 16 }}>
          <BreakdownView breakdown={rec.breakdown} model={rec.call?.model} approvedBy={approved?.approved_by} />
          {approved ? (
            <div className="btn-row" style={{ marginTop: 12 }}>
              <button type="button" className="btn btn-live" disabled={busy || !hasToken} onClick={() => run("meta")}>Generate RTL with Muse Spark · paid</button>
              <button type="button" className="btn btn-quiet" disabled={busy} onClick={() => run("fake")}>Offline dry run · $0</button>
            </div>
          ) : (
            <div className="approve-form" style={{ marginTop: 12 }}>
              <p className="approve-text"><strong>Approve this breakdown</strong> as the plan the RTL step must follow. Recorded with your name.{!hasToken && <span className="mark-neutral"> Approval needs the API token.</span>}</p>
              <label className="approve-name"><span className="label">Approved by</span>
                <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" autoComplete="name" /></label>
              <button type="button" className="btn" disabled={busy || !name.trim() || !hasToken} onClick={approve}>Approve</button>
            </div>
          )}
        </div>
      )}
      {runId && <div style={{ marginTop: 16 }}><RunProgress runId={runId} /></div>}
    </section>
  );
}
