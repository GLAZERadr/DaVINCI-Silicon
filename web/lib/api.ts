// Browser-side access to the DaVINCI API (api/server.py). The base URL comes from
// NEXT_PUBLIC_DAVINCI_API or a URL the viewer enters (kept in localStorage); the
// API token, needed only for live model calls and approvals, is kept in
// sessionStorage for this tab and sent as a Bearer header.
import { type Json, type Run, toRun } from "./run";

const ENV_API = process.env.NEXT_PUBLIC_DAVINCI_API ?? "";
const BASE_KEY = "davinci.api";
const TOKEN_KEY = "davinci.token";

function store(kind: "local" | "session"): Storage | null {
  try {
    return kind === "local" ? window.localStorage : window.sessionStorage;
  } catch {
    return null;
  }
}

export const LOCAL_API = "http://127.0.0.1:8000";

// A board served from this machine talks to the API on this machine by default.
function servedLocally(): boolean {
  try {
    return ["127.0.0.1", "localhost", "[::1]"].includes(window.location.hostname);
  } catch {
    return false;
  }
}

export function apiBase(): string {
  return (store("local")?.getItem(BASE_KEY) || ENV_API || (servedLocally() ? LOCAL_API : "")).replace(/\/+$/, "");
}

export function setApiBase(url: string) {
  const s = store("local");
  if (!s) return;
  if (url.trim()) s.setItem(BASE_KEY, url.trim());
  else s.removeItem(BASE_KEY);
}

export function apiToken(): string {
  return store("session")?.getItem(TOKEN_KEY) ?? "";
}

export function setApiToken(token: string) {
  const s = store("session");
  if (!s) return;
  if (token) s.setItem(TOKEN_KEY, token);
  else s.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T = Json>(path: string, init: RequestInit = {}): Promise<T> {
  const base = apiBase();
  if (!base) throw new ApiError(0, "no API configured");
  const headers = new Headers(init.headers);
  const token = apiToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${base}${path}`, { ...init, headers });
  const type = res.headers.get("content-type") ?? "";
  const body = type.includes("json") ? await res.json() : await res.text();
  if (!res.ok) {
    const detail = typeof body === "string" ? body : body?.detail ?? JSON.stringify(body);
    throw new ApiError(res.status, `${res.status}: ${typeof detail === "string" ? detail : JSON.stringify(detail)}`);
  }
  return body as T;
}

// A finished run from the API, with each attempt's verdict, RTL and prompt.
// Returns the job record instead while the run is queued or running.
export async function apiRun(id: string): Promise<{ run: Run } | { job: Json }> {
  const r = await api(`/runs/${encodeURIComponent(id)}`);
  if (!r.attempts) return { job: r };
  const file = async (n: number, p: string) => {
    try {
      return await api<string>(`/runs/${encodeURIComponent(id)}/attempts/${n}/${p}`);
    } catch {
      return null;
    }
  };
  const ns: number[] = r.attempts.map((a: Json) => a.n);
  const got = await Promise.all(ns.map(async (n) => {
    const [v, rtl, prompt] = await Promise.all([file(n, "sim/verdict.json"), file(n, `${r.block ?? "sync_fifo"}.v`), file(n, "prompt.json")]);
    const parse = (t: string | null) => { try { return t ? JSON.parse(t) : null; } catch { return null; } };
    return [n, { v: parse(v), rtl, prompt: parse(prompt) }] as const;
  }));
  const by = new Map(got);
  return { run: toRun(r, { verdict: (n) => by.get(n)?.v ?? null, rtl: (n) => by.get(n)?.rtl ?? null,
                           prompt: (n) => by.get(n)?.prompt ?? null }) };
}
