"use client";

import { useCallback, useEffect, useState } from "react";
import ApiPanel from "./ApiPanel";
import RunProgress from "./RunProgress";
import { api, apiBase, apiToken } from "@/lib/api";
import type { Json } from "@/lib/run";

type Item = { id: string; text: string; source_location?: string; confidence?: string };
type Draft = Item & { include: boolean; maps_to: string | null; relation?: string; reason?: string; edited: boolean };

const COVER: Record<string, { mark: string; tone: string; word: string }> = {
  full: { mark: "✓", tone: "mark-pass", word: "Full" },
  partial: { mark: "○", tone: "mark-neutral", word: "Partial" },
  none: { mark: "✕", tone: "mark-fail", word: "None" },
};

// Image/PDF spec → extracted requirements → human review and approval → run.
export default function SpecIntake() {
  const [apiOk, setApiOk] = useState(false);
  const [list, setList] = useState<Json[]>([]);
  const [xid, setXid] = useState<string | null>(null);
  const [rec, setRec] = useState<Json | null>(null);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [provider, setProvider] = useState<"meta" | "fake">("meta");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);

  const refreshList = useCallback(() => {
    api("/extractions").then((r) => setList([...r.running, ...r.extractions])).catch(() => {});
  }, []);

  const open = useCallback(async (id: string) => {
    setXid(id);
    setRec(null);
    setRunId(null);
    setError(null);
    window.history.replaceState(null, "", `?x=${encodeURIComponent(id)}`);
    try {
      const r = await api(`/extractions/${encodeURIComponent(id)}`);
      setRec(r);
      if (r.extracted) {
        const remap = r.latest_remap;
        const mapping: Json[] = remap?.mapping ?? r.mapping ?? [];
        const by = new Map(mapping.map((m) => [m.id, m]));
        setDrafts((r.extracted.requirements as Item[]).map((it) => ({
          ...it, include: true, edited: false,
          maps_to: by.get(it.id)?.maps_to ?? null, relation: by.get(it.id)?.relation, reason: by.get(it.id)?.reason,
        })));
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    if (!apiOk) return;
    refreshList();
    const id = new URLSearchParams(window.location.search).get("x");
    if (id) open(id);
  }, [apiOk, refreshList, open]);

  // While the model is still reading the document, poll.
  useEffect(() => {
    if (!xid || !rec || rec.status !== "running") return;
    const t = setTimeout(() => open(xid), 2000);
    return () => clearTimeout(t);
  }, [xid, rec, open]);

  async function upload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("provider", provider);
      const r = await api("/extractions", { method: "POST", body: fd });
      refreshList();
      open(r.extraction_id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function approve(e: React.FormEvent) {
    e.preventDefault();
    if (!xid) return;
    setBusy(true);
    setError(null);
    try {
      // Always send the list: it carries the reviewer's edits, removals and the mapping shown here.
      const requirements = drafts.filter((d) => d.include).map((d) => ({ id: d.id, text: d.text, maps_to: d.maps_to }));
      await api(`/extractions/${encodeURIComponent(xid)}/approve`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved_by: name, requirements }),
      });
      await open(xid);
      refreshList();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function run(p: "meta" | "fake") {
    if (!xid) return;
    setBusy(true);
    setError(null);
    try {
      const r = await api("/runs", { method: "POST", headers: { "Content-Type": "application/json" },
                                     body: JSON.stringify({ extraction_id: xid, provider: p }) });
      setRunId(r.run_id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const setDraft = (i: number, patch: Partial<Draft>) =>
    setDrafts((ds) => ds.map((d, j) => (j === i ? { ...d, ...patch } : d)));

  const approved = rec?.approved as Json | undefined;
  const comparison: Json | undefined = rec?.latest_remap?.comparison ?? rec?.comparison;
  const refs: Json[] = rec?.reference?.requirements ?? [];
  const included = drafts.filter((d) => d.include).length;
  const pages = Number(rec?.source?.pages ?? 0);

  return (
    <main className="board">
      <section className="card">
        <p className="label">Spec intake</p>
        <p className="lede">Upload a datasheet page or timing diagram (PDF or image). Muse Spark reads it and lists the requirements it finds; it never sees <span className="mono">spec/requirements.json</span>. A second call maps each item to a reference requirement. Both are AI interpretation: a person reviews, edits and approves the list before any RTL is generated from it.</p>
        <form className="run-form" onSubmit={upload}>
          <div className="run-form-row">
            <label>
              <span className="label">Spec file</span>
              <input type="file" accept=".pdf,.png,.jpg,.jpeg,.webp" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </label>
            <label>
              <span className="label">Reader</span>
              <select value={provider} onChange={(e) => setProvider(e.target.value as "meta" | "fake")}>
                <option value="meta">Muse Spark 1.3 · live, about $0.07 · needs token</option>
                <option value="fake">Offline stand-in · $0</option>
              </select>
            </label>
          </div>
          {provider === "meta" && !apiToken() && <p className="mark-neutral">○ Live extraction needs the API token (Connection settings).</p>}
          <div><button className="btn" type="submit" disabled={!apiOk || !file || busy || (provider === "meta" && !apiToken())}>{busy ? "Uploading…" : "Extract requirements"}</button></div>
        </form>
      </section>

      <ApiPanel onChange={setApiOk} needToken="Live extraction and approval need the API token (Connection settings)." />

      {apiOk && list.length > 0 && (
        <section className="card">
          <p className="label">Extractions on the server</p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Extraction</th><th>Source</th><th>Status</th><th>Cost</th><th /></tr></thead>
              <tbody>
                {list.map((x) => (
                  <tr key={x.extraction_id}>
                    <td className="mono">{x.extraction_id}</td>
                    <td>{typeof x.source === "string" ? x.source : x.source?.name}</td>
                    <td>{x.approved ? <span className="mark-pass">✓ Approved</span> : x.status === "awaiting_approval" ? <span className="mark-neutral">○ Awaiting review</span> : <span className="mark-neutral">○ {x.status}</span>}</td>
                    <td>{x.cost_usd != null ? `$${Number(x.cost_usd).toFixed(3)}` : "–"}</td>
                    <td><button type="button" className="btn btn-quiet btn-sm" onClick={() => open(x.extraction_id)} aria-current={x.extraction_id === xid ? "true" : undefined}>Review</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {error && <p className="mark-fail" role="alert">✕ {error}</p>}

      {rec && rec.status === "running" && <section className="card"><p className="mark-neutral">○ Reading {rec.source?.name ?? "the file"}… (this takes about a minute)</p></section>}
      {rec && rec.status === "error" && <section className="card"><p className="mark-fail">✕ Extraction failed.</p><pre className="c-msg">{rec.error}</pre></section>}

      {rec && rec.extracted && (
        <>
          <section className="card">
            <div className="api-row">
              <p className="label">Review · <span className="mono">{xid}</span> · {rec.source?.name}</p>
              {approved ? <span className="pill pass">✓ Approved by {approved.approved_by}</span> : <span className="pill neutral">○ Awaiting review</span>}
            </div>
            <p className="lede">{drafts.length} items extracted from {pages} page(s) · {rec.provider} · ${Number(rec.cost_usd ?? 0).toFixed(3)}{rec.latest_remap ? " · mapping from the latest re-map" : ""}</p>
            {pages > 0 && (
              <div className="pages">
                {Array.from({ length: pages }, (_, i) => (
                  <a key={i} href={`${apiBase()}/extractions/${xid}/pages/${i + 1}`} target="_blank" rel="noreferrer">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={`${apiBase()}/extractions/${xid}/pages/${i + 1}`} alt={`Page ${i + 1} of ${rec.source?.name}`} loading="lazy" />
                  </a>
                ))}
              </div>
            )}
            {(rec.extracted.unreadable ?? []).length > 0 && (
              <p className="lede"><span className="mark-neutral">○ The model flagged as unreadable:</span> {(rec.extracted.unreadable as string[]).join(" · ")}</p>
            )}
          </section>

          <section className="grid-2 intake">
            <div className="card">
              <p className="label">Extracted from the document · AI interpretation · not verified</p>
              <ul className="drafts">
                {drafts.map((d, i) => (
                  <li key={d.id} className={d.include ? undefined : "excluded"}>
                    <div className="draft-head">
                      <label className="choice">
                        <input type="checkbox" checked={d.include} disabled={!!approved} onChange={(e) => setDraft(i, { include: e.target.checked })} />
                        <span className="mono">{d.id}</span>
                      </label>
                      <span className="draft-map">
                        {d.maps_to ? <>→ <span className="mono">{d.maps_to}</span>{d.relation ? ` (${d.relation === "part_of" ? "part of" : d.relation})` : ""}</> : <span className="mark-neutral">no matching REQ</span>}
                      </span>
                    </div>
                    {approved
                      ? <p className="draft-text">{d.text}</p>
                      : <textarea aria-label={`${d.id} text`} value={d.text} rows={2}
                          onChange={(e) => setDraft(i, { text: e.target.value, edited: true })} />}
                    <p className="draft-meta">{d.source_location}{d.confidence ? ` · confidence ${d.confidence}` : ""}{d.edited ? " · edited" : ""}{d.reason ? ` · ${d.reason}` : ""}</p>
                  </li>
                ))}
              </ul>
            </div>
            <div className="card">
              <p className="label">Reference requirements · spec/requirements.json</p>
              <p className="lede">Coverage of each reference requirement by the extracted items, as judged by the map call (AI interpretation). The frozen tests check the reference list either way.</p>
              <ul className="refs">
                {refs.map((r) => {
                  const row = comparison?.rows?.find((x: Json) => x.reference === r.id);
                  const level = row?.coverage ?? (row?.covered ? "full" : "none");
                  const c = COVER[level] ?? COVER.none;
                  return (
                    <li key={r.id}>
                      <p><span className={c.tone}>{c.mark} {c.word}</span> <span className="mono">{r.id}</span> {r.text}</p>
                      <p className="draft-meta">{row?.extracted?.length ? `from ${row.extracted.join(", ")}` : "no extracted item"}{row?.missing ? ` · missing: ${row.missing}` : ""}</p>
                    </li>
                  );
                })}
              </ul>
            </div>
          </section>

          <section className="card">
            {approved ? (
              <>
                <p className="label">Approved</p>
                <p className="lede">
                  {approved.requirements.length} requirements approved by {approved.approved_by} on {String(approved.approved_at).slice(0, 16).replace("T", " ")}.
                  {" "}{approved.untested?.length ? `${approved.untested.length} have no frozen test (${approved.untested.join(", ")}): they are part of the spec the model sees, but nothing checks them.` : "Every item maps to frozen tests."}
                  {" "}Approved file <span className="mono">sha256 {String(rec.approved_sha256).slice(0, 16)}…</span>
                </p>
                <div className="btn-row">
                  <button type="button" className="btn" disabled={busy || !apiToken()} onClick={() => run("meta")}>Generate RTL with Muse Spark</button>
                  <button type="button" className="btn btn-quiet" disabled={busy} onClick={() => run("fake")}>Offline dry run ($0)</button>
                </div>
                {!apiToken() && <p className="mark-neutral">○ The live run needs the API token.</p>}
              </>
            ) : (
              <form className="run-form" onSubmit={approve}>
                <p className="label">Approve</p>
                <p className="lede">Approving sends exactly the {included} checked items, with your edits and the mappings shown, to the RTL step. This is a human decision and is recorded with your name.</p>
                <div className="run-form-row">
                  <label>
                    <span className="label">Approved by</span>
                    <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" autoComplete="name" />
                  </label>
                </div>
                <div><button type="submit" className="btn" disabled={busy || !name.trim() || included === 0 || !apiToken()}>Approve {included} requirements</button></div>
                {!apiToken() && <p className="mark-neutral">○ Approval needs the API token.</p>}
              </form>
            )}
          </section>
        </>
      )}

      {runId && <RunProgress runId={runId} />}
    </main>
  );
}
