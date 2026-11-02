"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, api, apiToken, setSessionToken } from "@/lib/api";

// App pages need a signed-in account (or a token set in Connection settings). The
// landing, sign-in, register and request-access pages stay public. This is a
// client-side gate on a static site: the raw evidence also lives in the public repo.
const PUBLIC = ["/", "/login/", "/register/", "/access/"];

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const open = PUBLIC.includes(path.endsWith("/") ? path : `${path}/`);
  const [state, setState] = useState<"checking" | "ok" | "down">("checking");

  useEffect(() => {
    if (open) return;
    const toLogin = () => {
      const next = window.location.pathname + window.location.search;
      window.location.replace(`/login/?next=${encodeURIComponent(next)}`);
    };
    const check = () => {
      if (!apiToken()) return toLogin();
      api("/me")
        .then((m) => (m.owner ? setState("ok") : toLogin()))
        .catch((e) => {
          if (e instanceof ApiError && e.status === 401) { setSessionToken(""); toLogin(); }
          else setState("down");
        });
    };
    check();
    window.addEventListener("davinci-session", check);
    return () => window.removeEventListener("davinci-session", check);
  }, [open, path]);

  if (open || state === "ok") return <>{children}</>;
  return (
    <main className="auth-gate">
      {state === "checking" ? <p className="mark-neutral" role="status">○ Checking your sign-in…</p> : (
        <section className="card auth-gate-card">
          <p className="label">Sign-in could not be checked</p>
          <p className="lede">The DaVINCI API is not reachable from this page, so your account cannot be verified right now.</p>
          <div className="btn-row">
            <button type="button" className="btn" onClick={() => window.location.reload()}>Try again</button>
            <a className="btn btn-quiet" href="/">Back to the home page</a>
          </div>
        </section>
      )}
    </main>
  );
}
