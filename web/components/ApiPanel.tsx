"use client";

import { useEffect, useState } from "react";
import { LOCAL_API, api, apiBase, apiToken, setApiBase, setApiToken } from "@/lib/api";

// API connection: base URL, health, and the token for live model calls.
export default function ApiPanel({ needToken, onChange }: { needToken?: string; onChange?: (ok: boolean, hasToken: boolean) => void }) {
  const [base, setBase] = useState("");
  const [token, setToken] = useState("");
  const [health, setHealth] = useState<"checking" | "ok" | "down" | "none">("checking");
  const [open, setOpen] = useState(false);
  const [saved, setSaved] = useState({ base: "", token: false }); // read after mount: storage is browser-only

  async function check() {
    setSaved({ base: apiBase(), token: !!apiToken() });
    if (!apiBase()) {
      setHealth("none");
      onChange?.(false, !!apiToken());
      return;
    }
    setHealth("checking");
    try {
      await api("/health");
      setHealth("ok");
      onChange?.(true, !!apiToken());
    } catch {
      setHealth("down");
      onChange?.(false, !!apiToken());
    }
  }

  useEffect(() => {
    setBase(apiBase() || LOCAL_API); // prefilled: the usual local address, not a placeholder
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
          <span className="mono api-url">{saved.base || "set NEXT_PUBLIC_DAVINCI_API or enter a URL"}</span>
          {saved.token ? <span className="mark-neutral"> · token set for this tab</span> : null}
        </div>
        <button type="button" className="btn btn-quiet" onClick={() => setOpen(!open)} aria-expanded={open}>
          {open ? "Close" : "Connection settings"}
        </button>
      </div>
      {health === "none" || health === "down" ? (
        <p className="lede" style={{ margin: "12px 0 0" }}>
          This page talks to the DaVINCI API (<code>make api</code>). Recorded runs stay readable on the Evidence and Run Console pages without it.
          {health === "down" && saved.base.includes("127.0.0.1")
            ? " For an API on this computer, allow the browser's local network access prompt for this site, and check that make api is running."
            : ""}
        </p>
      ) : null}
      {needToken && !saved.token && health === "ok" ? (
        <p className="lede" style={{ margin: "12px 0 0" }}>{needToken}</p>
      ) : null}
      {open && (
        <form className="api-form" onSubmit={save}>
          <label>
            <span className="label">API URL</span>
            <input value={base} onChange={(e) => setBase(e.target.value)} placeholder="https://your-api.example.com" inputMode="url" />
          </label>
          <label>
            <span className="label">API token (live model calls, approvals)</span>
            <input value={token} onChange={(e) => setToken(e.target.value)} type="password" autoComplete="off" placeholder="paste the DAVINCI_API_TOKEN value" />
          </label>
          <button type="submit" className="btn">Save</button>
        </form>
      )}
    </section>
  );
}
