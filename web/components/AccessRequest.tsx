"use client";

import { useState } from "react";
import ApiPanel from "./ApiPanel";
import { api } from "@/lib/api";

const LIMITS = { name: 100, email: 254, role: 100, verify: 1000 } as const;
type Field = keyof typeof LIMITS;

// Request access (S11): the public site is read-only; a token is issued by hand.
export default function AccessRequest() {
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [form, setForm] = useState<Record<Field, string>>({ name: "", email: "", role: "", verify: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const set = (k: Field) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [k]: e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api("/access-requests", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form),
      });
      setDone(r.message ?? "Request stored.");
    } catch (err) {
      const msg = (err as Error).message;
      setError(msg.startsWith("422") ? "Check the fields: a valid email and every field filled in, within the length limits." : msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="board">
      <section className="title-block">
        <p className="eyebrow">Request access</p>
        <h1 className="display-title">Read freely, run with a token. <span className="tone-2">Evidence, Run Console and $0 replays are open to everyone; live model runs need a token issued by the DaVINCI team.</span></h1>
      </section>

      <ApiPanel onChange={(ok) => setApiOk(ok)} />

      <section className="card">
        <p className="label">Ask for a token</p>
        <p className="lede">There is no signup. We read each request and, if it fits, send you a personal token by hand. Nothing is created automatically.</p>
        {apiOk === false && (
          <p className="mark-neutral" role="status">○ The DaVINCI API is not reachable from this page, so requests cannot be sent right now. The recorded runs stay readable on the Evidence and Run Console pages.</p>
        )}
        {done ? (
          <p className="mark-pass" role="status">✓ Sent. {done}</p>
        ) : (
          <form className="run-form" onSubmit={submit}>
            <div className="run-form-row">
              <label>
                <span className="label">Name</span>
                <input value={form.name} onChange={set("name")} required maxLength={LIMITS.name} autoComplete="name" />
              </label>
              <label>
                <span className="label">Email</span>
                <input value={form.email} onChange={set("email")} required maxLength={LIMITS.email} type="email" autoComplete="email" />
              </label>
            </div>
            <label>
              <span className="label">Role</span>
              <input value={form.role} onChange={set("role")} required maxLength={LIMITS.role} placeholder="e.g. DV engineer, RTL designer, student" />
            </label>
            <label>
              <span className="label">What would you verify?</span>
              <textarea value={form.verify} onChange={set("verify")} required maxLength={LIMITS.verify} rows={4}
                placeholder="The block, the spec you would start from, what evidence you would need" />
            </label>
            <p className="lede" style={{ margin: 0 }}>Your details are used only to contact you about DaVINCI access.</p>
            {error && <p className="mark-fail" role="alert">✕ {error}</p>}
            <div>
              <button type="submit" className="btn" disabled={!apiOk || busy}>{busy ? "Sending…" : "Request access"}</button>
            </div>
          </form>
        )}
      </section>
    </main>
  );
}
