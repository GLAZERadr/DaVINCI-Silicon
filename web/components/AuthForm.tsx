"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Logo from "./Logo";
import { api, apiBase, setSessionToken } from "@/lib/api";

// Sign in / register (api/auth.py). Google and GitHub run the OAuth flow on the API,
// which sends the browser back here with the session token in the URL fragment.
type Mode = "login" | "register";
type Providers = { password: boolean; google: boolean; github: boolean };
const NEXT_KEY = "davinci.next";

const GOOGLE = (
  <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
    <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
    <path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
    <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
    <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
  </svg>
);
const GITHUB = (
  <svg width="18" height="18" viewBox="0 0 16 16" aria-hidden="true" fill="currentColor">
    <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
  </svg>
);

function nextPage(): string {
  try {
    const n = sessionStorage.getItem(NEXT_KEY);
    sessionStorage.removeItem(NEXT_KEY);
    return n && n.startsWith("/") && !n.startsWith("//") ? n : "/evidence/";
  } catch {
    return "/evidence/";
  }
}

export default function AuthForm({ mode }: { mode: Mode }) {
  const [prov, setProv] = useState<Providers | null>(null);
  const [down, setDown] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Back from Google/GitHub: #dv_session=<token> or #auth_error=<reason>.
    const frag = new URLSearchParams(window.location.hash.slice(1));
    if (frag.has("dv_session") || frag.has("auth_error")) {
      history.replaceState(null, "", window.location.pathname);
      if (frag.get("dv_session")) {
        setSessionToken(frag.get("dv_session")!);
        window.location.replace(nextPage());
        return;
      }
      setError(`Sign-in did not finish: ${frag.get("auth_error")}`);
    }
    const n = new URLSearchParams(window.location.search).get("next");
    if (n) try { sessionStorage.setItem(NEXT_KEY, n); } catch {}
    api<Providers>("/auth/providers").then(setProv).catch(() => setDown(true));
  }, []);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  function sso(p: "google" | "github") {
    const back = `${window.location.origin}${window.location.pathname}`;
    window.location.href = `${apiBase()}/auth/${p}/start?return_to=${encodeURIComponent(back)}`;
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body = mode === "register" ? form : { email: form.email, password: form.password };
      const r = await api(`/auth/${mode}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      setSessionToken(r.token);
      window.location.replace(nextPage());
    } catch (err) {
      const msg = (err as Error).message.replace(/^\d+: /, "");
      setError((err as Error).message.startsWith("422") && mode === "register"
        ? "Check the fields: a valid email, a name, and a password of at least 10 characters." : msg);
      setBusy(false);
    }
  }

  const reg = mode === "register";
  const off = (p: "google" | "github") => !prov || !prov[p];
  return (
    <div className="auth-split">
      <aside className="auth-aside">
        <Link href="/" className="wordmark auth-home" aria-label="DaVINCI Silicon home"><Logo /></Link>
        <div className="auth-pitch">
          <p className="lp-eyebrow">For RTL and verification engineers</p>
          <h2 className="auth-pitch-title">Spec in, RTL out. <span className="tone-2">Proven against tests the model never touches.</span></h2>
          <ul className="auth-points">
            <li><span className="auth-point-icon" aria-hidden="true">✓</span>Frozen tests and a golden model decide every verdict, not the AI.</li>
            <li><span className="auth-point-icon" aria-hidden="true">✕</span>Planted bugs prove the tests catch failures before any RTL is trusted.</li>
            <li><span className="auth-point-icon" aria-hidden="true">↻</span>Every attempt, failure and cent is recorded, and any run replays for $0.</li>
          </ul>
        </div>
        <p className="meta-text auth-legal">© 2026 DaVINCI Silicon · <Link href="/evidence/">Evidence</Link> · <a href="https://github.com/GLAZERadr/DaVINCI-Silicon">GitHub</a></p>
      </aside>

      <main className="auth-main">
        <section className="auth-card card" aria-labelledby="auth-title">
          <h1 id="auth-title" className="auth-title">{reg ? "Create your account" : "Sign in"}</h1>
          <p className="auth-sub">{reg
            ? "Free to read the evidence and replay runs. Live model runs are switched on per account by the DaVINCI team."
            : "Welcome back. Sign in to open the evidence, the Run Console and your runs."}</p>

          <div className="auth-sso">
            <button type="button" className="btn btn-quiet auth-sso-btn" disabled={off("google")} onClick={() => sso("google")}>
              {GOOGLE}Continue with Google
            </button>
            <button type="button" className="btn btn-quiet auth-sso-btn" disabled={off("github")} onClick={() => sso("github")}>
              {GITHUB}Continue with GitHub
            </button>
            {prov && (!prov.google || !prov.github) && (
              <p className="meta-text auth-note">○ {[!prov.google && "Google", !prov.github && "GitHub"].filter(Boolean).join(" and ")} sign-in is not configured on this server yet.</p>
            )}
          </div>

          <div className="auth-or" role="separator"><span>or with email</span></div>

          <form className="auth-form" onSubmit={submit}>
            {reg && (
              <label htmlFor="auth-name"><span className="label">Name</span>
                <input id="auth-name" name="name" aria-label="Name" value={form.name} onChange={set("name")} required maxLength={80} autoComplete="name" placeholder="Ada Lovelace" /></label>
            )}
            <label htmlFor="auth-email"><span className="label">Email</span>
              <input id="auth-email" name="email" aria-label="Email" type="email" value={form.email} onChange={set("email")} required maxLength={254} autoComplete="email" placeholder="you@company.com" /></label>
            <label htmlFor="auth-password"><span className="label">Password</span>
              <input id="auth-password" name="password" aria-label="Password" type="password" value={form.password} onChange={set("password")} required minLength={reg ? 10 : 1} maxLength={128}
                autoComplete={reg ? "new-password" : "current-password"} aria-describedby={reg ? "pw-hint" : undefined} />
              {reg && <span id="pw-hint" className="meta-text">At least 10 characters.</span>}
            </label>
            {error && <p className="mark-fail" role="alert">✕ {error}</p>}
            {down && <p className="mark-neutral" role="status">○ The DaVINCI API is not reachable from this page, so signing in is not possible right now. Recorded runs stay readable.</p>}
            <button type="submit" className="btn auth-submit" disabled={busy || down}>
              {busy ? (reg ? "Creating account…" : "Signing in…") : reg ? "Create account" : "Sign in"}
            </button>
          </form>

          <p className="auth-switch">{reg
            ? <>Already have an account? <Link href="/login/">Sign in</Link></>
            : <>New to DaVINCI? <Link href="/register/">Create an account</Link></>}</p>
        </section>
      </main>
    </div>
  );
}
