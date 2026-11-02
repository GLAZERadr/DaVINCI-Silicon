"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, api, sessionToken, setSessionToken } from "@/lib/api";

// Account control: Sign in / Get started on the landing page; in the app sidebar the
// signed-in profile with sign-out.
export default function AccountButton({ landing = false, active = false }: { landing?: boolean; active?: boolean }) {
  const [me, setMe] = useState<{ name: string; live: boolean } | null | undefined>(undefined);

  useEffect(() => {
    const load = () => {
      if (!sessionToken()) return setMe(null);
      api("/me").then((m) => setMe(m.account ? { name: m.name ?? m.owner, live: !!m.live } : null))
        .catch((e) => {
          // Only the server saying 401 ends the session; a request aborted by a page
          // change or an unreachable API must not throw a fresh sign-in away.
          if (e instanceof ApiError && e.status === 401) setSessionToken("");
          setMe(null);
        });
    };
    load();
    window.addEventListener("davinci-session", load);
    return () => window.removeEventListener("davinci-session", load);
  }, []);

  async function signOut() {
    await api("/auth/logout", { method: "POST" }).catch(() => {});
    setSessionToken("");
    window.location.replace("/"); // signed out: back to the landing page
  }

  if (me === undefined) return null; // storage is read after mount
  // Inside the app the header stays clean when signed out; signing in starts from the landing page.
  if (!me) return landing ? (
    <>
      <Link href="/login/" className="lp-nav-link">Sign in</Link>
      <Link href="/register/" className="btn btn-sm">Get started</Link>
    </>
  ) : null;
  if (landing) return <Link href="/evidence/" className="btn btn-sm">Open DaVINCI</Link>;
  // Sidebar profile: avatar, name and access, linking to /account/, with sign-out next to it.
  return (
    <div className="sb-account">
      <Link href="/account/" className="sb-account-link" aria-current={active ? "page" : undefined}
        title={me.live ? "Your account · live model runs enabled" : "Your account · read-only: live runs not granted yet"}>
        <span className="account-dot" aria-hidden="true">{me.name.slice(0, 1).toUpperCase()}</span>
        <span className="sb-account-text"><strong>{me.name}</strong><span className="meta-text">{me.live ? "Live runs enabled" : "Read-only"}</span></span>
      </Link>
      <button type="button" className="sb-signout" onClick={signOut} aria-label="Sign out" title="Sign out">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M6 2.5H3.5v11H6M10.5 5l3 3-3 3M13.5 8H6.5" />
        </svg>
      </button>
    </div>
  );
}
