"use client";

import { useEffect, useState } from "react";
import { api, apiBase, apiToken, setApiBase, setApiToken } from "@/lib/api";

// API connection: base URL, health, and the token for live model calls.
export default function ApiPanel({ needToken, onChange }: { needToken?: string; onChange?: (ok: boolean) => void }) {
  const [base, setBase] = useState("");
  const [token, setToken] = useState("");
  const [health, setHealth] = useState<"checking" | "ok" | "down" | "none">("checking");
  const [open, setOpen] = useState(false);

  async function check() {
    if (!apiBase()) {
      setHealth("none");
      onChange?.(false);
      return;
    }
    setHealth("checking");
    try {
      await api("/health");
      setHealth("ok");
      onChange?.(true);
    } catch {
      setHealth("down");
      onChange?.(false);
    }
  }

  useEffect(() => {
    setBase(apiBase());
    setToken(apiToken());
    check();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function save(e: React.FormEvent) {
    e.preventDefault();
    setApiBase(base);
    setApiToken(token);
    setOpen(false);
    check();
  }

  const label = { checking: "○ Checking API…", ok: "✓ API connected", down: "✕ API not reachable", none: "○ No API configured" }[health];
  const tone = health === "ok" ? "mark-pass" : health === "down" ? "mark-fail" : "mark-neutral";

  return (
    <section className="card api-panel" aria-label="API connection">
      <div className="api-row">
        <div>
          <span className={tone}>{label}</span>
          <span className="mono api-url">{apiBase() || "set NEXT_PUBLIC_DAVINCI_API or enter a URL"}</span>
          {apiToken() ? <span className="mark-neutral"> · token set for this tab</span> : null}
        </div>
        <button type="button" className="btn btn-quiet" onClick={() => setOpen(!open)} aria-expanded={open}>
          {open ? "Close" : "Connection settings"}
        </button>
      </div>
      {health === "none" || health === "down" ? (
        <p className="lede" style={{ margin: "12px 0 0" }}>
          This page talks to the DaVINCI API (<code>make api</code>). Recorded runs stay readable on the Evidence and Run Console pages without it.
        </p>
      ) : null}
      {needToken && !apiToken() && health === "ok" ? (
        <p className="lede" style={{ margin: "12px 0 0" }}>{needToken}</p>
      ) : null}
      {open && (
        <form className="api-form" onSubmit={save}>
          <label>
            <span className="label">API URL</span>
            <input value={base} onChange={(e) => setBase(e.target.value)} placeholder="http://127.0.0.1:8000" inputMode="url" />
          </label>
          <label>
            <span className="label">API token (live model calls, approvals)</span>
            <input value={token} onChange={(e) => setToken(e.target.value)} type="password" autoComplete="off" placeholder="DAVINCI_API_TOKEN" />
          </label>
          <button type="submit" className="btn">Save</button>
        </form>
      )}
    </section>
  );
}
