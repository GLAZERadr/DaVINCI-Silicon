"use client";

import Link from "next/link";
import Avatar from "./Avatar";
import { useCallback, useEffect, useState } from "react";
import { api, sessionToken, setSessionToken } from "@/lib/api";
import type { Json } from "@/lib/run";

// Profile page: who you are, live access, sign-in methods, your runs, your sessions.
const fmt = (s: string | number) => new Date(typeof s === "number" ? s * 1000 : s.replace(/([+-]\d{2})(\d{2})$/, "$1:$2"))
  .toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });

export default function AccountView() {
  const [acc, setAcc] = useState<Json | null>(null);
  const [runs, setRuns] = useState<Json[] | null>(null);
  const [state, setState] = useState<"loading" | "ok" | "signedout" | "down">("loading");
  const [name, setName] = useState("");
  const [pw, setPw] = useState({ current: "", next: "" });
  const [msg, setMsg] = useState<{ ok: boolean; text: string; where: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!sessionToken()) return setState("signedout");
    try {
      const a = await api("/auth/account");
      setAcc(a);
      setName(a.name);
      setState("ok");
      api("/runs?mine=1").then((r) => setRuns([...r.jobs, ...r.runs])).catch(() => setRuns([]));
    } catch (e) {
      setState(String((e as Error).message).startsWith("401") ? "signedout" : "down");
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function act(where: string, fn: () => Promise<string>) {
    setBusy(true);
    setMsg(null);
    try { setMsg({ ok: true, text: await fn(), where }); await load(); }
    catch (e) { setMsg({ ok: false, text: (e as Error).message.replace(/^\d+: /, ""), where }); }
    finally { setBusy(false); }
  }
  const post = (path: string, body?: Json) => api(path, { method: "POST", headers: { "Content-Type": "application/json" },
                                                             body: body ? JSON.stringify(body) : undefined });
  const note = (where: string) => msg?.where === where
    ? <p className={msg.ok ? "mark-pass" : "mark-fail"} role={msg.ok ? "status" : "alert"}>{msg.ok ? "✓" : "✕"} {msg.text}</p> : null;

  if (state === "loading") return <main className="board"><p className="mark-neutral">○ Loading your account…</p></main>;
  if (state !== "ok" || !acc) return (
    <main className="board">
      <section className="card">
        <p className="label">Your account</p>
        <p className="lede">{state === "down" ? "○ The DaVINCI API is not reachable from this page." : "You are not signed in."}</p>
        <Link href="/login/?next=/account/" className="btn">Sign in</Link>
      </section>
    </main>
  );

  const live = !!acc.live;
  return (
    <main className="board account">
      <section className="account-head">
        <Avatar name={String(acc.name)} src={acc.avatar} className="account-avatar" />
        <div>
          <h1 className="account-name-h">{acc.name}</h1>
          <p className="meta-text">{acc.email} · member since {fmt(acc.created)}</p>
        </div>
        <span className={live ? "state pass" : "state neutral"}>{live ? "✓ Live runs enabled" : "○ Read-only"}</span>
      </section>

      <div className="account-grid">
        <div className="account-main">
          <section className="box">
            <div className="box-header"><h2>Access</h2></div>
            <div className="box-pad">
              {live ? (
                <p className="account-p">You can start paid live runs on Muse Spark, extract requirements from a PDF or image, propose design breakdowns and approve them. Every call is recorded with its cost in the ledger.</p>
              ) : (
                <>
                  <p className="account-p">You can read every recorded run, open the Run Console and replay runs for $0. Live model runs, extractions and approvals are switched on per account by the DaVINCI team, so model credit is never spent by an account nobody checked.</p>
                </>
              )}
            </div>
          </section>

          <section className="box">
            <div className="box-header"><h2>Your runs</h2><Link href="/new/" className="btn btn-sm">New run</Link></div>
            {runs === null ? <p className="box-lede">○ Loading…</p> : runs.length === 0 ? (
              <p className="box-lede">No runs yet. Runs you start while signed in show up here. <Link href="/evidence/">Browse the recorded runs</Link>.</p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Run</th><th>Status</th><th>Attempts</th><th>Cost</th><th>Started</th></tr></thead>
                  <tbody>{runs.map((r) => (
                    <tr key={r.run_id}>
                      <td className="mono"><Link href={`/console/?run=${encodeURIComponent(r.run_id)}`}>{r.run_id}</Link></td>
                      <td>{r.status === "pass" ? <span className="mark-pass">✓ Pass</span> : ["fail", "error", "aborted", "needs_engineer"].includes(r.status) ? <span className="mark-fail">✕ {r.status}</span> : <span className="mark-neutral">○ {r.status}</span>}</td>
                      <td>{r.attempts_total ?? "—"}</td>
                      <td>{r.cost_usd != null ? `$${Number(r.cost_usd).toFixed(4)}` : "—"}</td>
                      <td className="meta-text">{r.started ? fmt(r.started) : "—"}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            )}
          </section>

          <section className="box">
            <div className="box-header"><h2>Sessions</h2><span className="meta-text">signed-in browsers · 30 days each</span></div>
            <ul className="checks checks-noid">
              {(acc.sessions as Json[]).map((s) => (
                <li key={s.token_id}>
                  <span aria-hidden="true">{s.current ? "✓" : "○"}</span>
                  <span className="check-name"><span className="mono">{s.token_id}</span>{s.current ? " · this browser" : ""} <span className="meta-text">signed in {fmt(s.created)} · expires {fmt(s.expires)}</span></span>
                  {s.current
                    ? <button type="button" className="btn btn-quiet btn-sm" onClick={async () => { await post("/auth/logout").catch(() => {}); setSessionToken(""); window.location.replace("/"); }}>Sign out</button>
                    : <button type="button" className="btn btn-quiet btn-sm" disabled={busy} onClick={() => act("sessions", async () => { await post(`/auth/sessions/${s.token_id}/revoke`); return "Session signed out."; })}>Sign out</button>}
                </li>
              ))}
            </ul>
            {note("sessions")}
          </section>
        </div>

        <aside className="account-side">
          <section className="box">
            <div className="box-header"><h2>Profile</h2></div>
            <form className="box-pad account-form" onSubmit={(e) => { e.preventDefault(); act("name", async () => { await post("/auth/account", { name }); window.dispatchEvent(new Event("davinci-session")); return "Name saved."; }); }}>
              <label><span className="label">Name</span><input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} required autoComplete="name" /></label>
              <label><span className="label">Email</span><input value={acc.email} readOnly disabled /></label>
              {note("name")}
              <div><button type="submit" className="btn btn-sm" disabled={busy || !name.trim() || name.trim() === acc.name}>Save name</button></div>
            </form>
          </section>

          <section className="box">
            <div className="box-header"><h2>Sign-in methods</h2></div>
            <ul className="checks checks-noid">
              {(["google", "github", "password"] as const).map((m) => {
                const on = (acc.methods as string[]).includes(m);
                return (
                  <li key={m}>
                    <span aria-hidden="true" className={on ? "mark-pass" : "mark-neutral"}>{on ? "✓" : "○"}</span>
                    <span className="check-name">{{ google: "Google", github: "GitHub", password: "Email and password" }[m]}</span>
                    <span className={on ? "mark-pass" : "mark-neutral"}>{on ? "Linked" : "Not set"}</span>
                  </li>
                );
              })}
            </ul>
            <p className="box-lede">Google and GitHub link to this account when they sign in with {acc.email}.</p>
            <form className="box-pad account-form" onSubmit={(e) => { e.preventDefault(); act("pw", async () => {
              await post("/auth/password", { new: pw.next, current: pw.current || null }); setPw({ current: "", next: "" });
              return (acc.methods as string[]).includes("password") ? "Password changed." : "Password added."; }); }}>
              {(acc.methods as string[]).includes("password") && (
                <label><span className="label">Current password</span><input type="password" value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} autoComplete="current-password" required /></label>
              )}
              <label><span className="label">{(acc.methods as string[]).includes("password") ? "New password" : "Add a password"}</span>
                <input type="password" value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} minLength={10} maxLength={128} autoComplete="new-password" required /></label>
              <span className="meta-text">At least 10 characters.</span>
              {note("pw")}
              <div><button type="submit" className="btn btn-quiet btn-sm" disabled={busy || pw.next.length < 10}>{(acc.methods as string[]).includes("password") ? "Change password" : "Add password"}</button></div>
            </form>
          </section>
        </aside>
      </div>
    </main>
  );
}
