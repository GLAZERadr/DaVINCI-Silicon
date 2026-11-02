"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import ApiPanel from "./ApiPanel";
import Console from "./Console";
import { api, apiRun } from "@/lib/api";
import { type Json, type Requirement, type Run, status } from "@/lib/run";

type Recorded = { id: string; status: string; seedBug: string | null; fromExtraction: boolean };

// Run Console entry: recorded runs (static) and, with the API, any run on the server.
export default function ConsoleIndex({ recorded, requirements, triage }: { recorded: Recorded[]; requirements: Requirement[]; triage: Json | null }) {
  const [apiOk, setApiOk] = useState(false);
  const [runs, setRuns] = useState<Json[]>([]);
  const [jobs, setJobs] = useState<Json[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [loaded, setLoaded] = useState<Run | null>(null);
  const [reqs, setReqs] = useState<{ list: Requirement[]; from: string } | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const load = useCallback(async (id: string) => {
    setOpen(id);
    setLoaded(null);
    setNote("Loading…");
    try {
      const r = await apiRun(id);
      if ("run" in r) {
        // A run from an approved extraction was generated against that list.
        const xid = r.run.extraction?.extraction_id;
        const approved = xid ? await api(`/extractions/${encodeURIComponent(xid)}`).then((x) => x.approved).catch(() => null) : null;
        setReqs(approved ? { list: approved.requirements, from: `approved extraction ${xid}` } : null);
        setLoaded(r.run);
        setNote(null);
      } else {
        setNote(`${id} is ${r.job.state}. Follow it on the New run page, or reopen when it finishes.`);
      }
    } catch (e) {
      setNote(`Could not load ${id}: ${(e as Error).message}`);
    }
  }, []);

  useEffect(() => {
    if (!apiOk) return;
    api("/runs").then((r) => { setRuns(r.runs); setJobs(r.jobs); }).catch(() => {});
    const id = new URLSearchParams(window.location.search).get("run");
    if (id) load(id);
  }, [apiOk, load]);

  function pick(id: string) {
    window.history.replaceState(null, "", `?run=${encodeURIComponent(id)}`);
    load(id);
  }

  if (open && loaded) {
    return (
      <>
        <nav className="subbar" aria-label="Run">
          <button type="button" className="subbar-back" onClick={() => { setOpen(null); setLoaded(null); window.history.replaceState(null, "", "?"); }}>← All runs</button>
          <span className="mono">{open}</span>
          <span className="subbar-end mark-neutral">from the API · requirements: {reqs?.from ?? "default list"}</span>
        </nav>
        <Console runs={[{ label: "Run", run: loaded }]} requirements={reqs?.list ?? requirements} traceSource="api" triage={triage} />
      </>
    );
  }

  const active = jobs.filter((j) => j.state !== "done");
  return (
    <main className="board">
      <section className="title-block">
        <p className="eyebrow">Run Console</p>
        <h1 className="display-title">Every attempt, line by line. <span className="tone-2">Diff, prompt, simulator output and the model&apos;s diagnosis, kept apart from what was measured.</span></h1>
      </section>
      <section className="card">
        <p className="label">Open a run</p>
        <p className="lede">Every attempt of a run: the requirements tree with per-test results, the RTL diff against the previous attempt, the prompt, simulator, compile and sweep output, and the model&apos;s diagnosis kept apart from what was measured.</p>
        <p className="label" style={{ marginTop: 8 }}>Recorded runs · work without the API</p>
        <ul className="run-cards">
          {recorded.map((r) => {
            const st = status(r.status);
            return (
              <li key={r.id}>
                <Link href={`/runs/${r.id}/console/`} className="run-card">
                  <span className="mono">{r.id}</span>
                  <span className={`pill ${st.tone}`}>{st.mark} {st.word}</span>
                  <span className="run-card-note">{r.seedBug ? `seeded ${r.seedBug} → repair` : r.fromExtraction ? "from an approved PDF extraction" : "generated from the spec"}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </section>

      <ApiPanel onChange={setApiOk} />

      {apiOk && (
        <section className="card">
          <p className="label">Runs on the API server</p>
          {note && <p className="lede" role="status">{note}</p>}
          {active.length > 0 && (
            <p className="lede">In progress: {active.map((j) => <Link key={j.run_id} href={`/new/?watch=${encodeURIComponent(j.run_id)}`} className="mono">{j.run_id} ({j.state}) </Link>)}</p>
          )}
          <div className="table-wrap">
            <table>
              <thead><tr><th>Run</th><th>Status</th><th>Model</th><th>Attempts</th><th>Cost</th><th /></tr></thead>
              <tbody>
                {runs.map((r) => {
                  const st = status(r.status);
                  const gen = r.providers?.generate;
                  const kind = r.replayed_from ? `replay of ${r.replayed_from}` : gen === "fake" ? "offline stand-in" : gen === "meta" || gen === "baseten" ? `live · ${gen}` : gen ?? "–";
                  return (
                    <tr key={r.run_id} className={`row-link ${gen === "fake" ? "row-muted" : ""}`} onClick={() => pick(r.run_id)}>
                      <td className="mono">{r.run_id}</td>
                      <td><span className={`pill ${st.tone}`}>{st.mark} {st.word}</span></td>
                      <td>{kind}</td>
                      <td>{r.attempts_total ?? "–"}</td>
                      <td>${Number(r.cost_usd ?? 0).toFixed(4)}</td>
                      <td><button type="button" className="btn btn-quiet btn-sm" onClick={(e) => { e.stopPropagation(); pick(r.run_id); }}>Open</button></td>
                    </tr>
                  );
                })}
                {runs.length === 0 && <tr><td colSpan={6} className="mark-neutral">○ No runs on the server yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}
