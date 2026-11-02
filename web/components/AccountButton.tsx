"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, api, sessionToken, setSessionToken } from "@/lib/api";

// Header account control: Sign in / Sign up, or the signed-in name with Sign out.
export default function AccountButton({ landing = false }: { landing?: boolean }) {
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
  return (
    <>
      <Link href="/account/" className="account-name" title={me.live ? "Your account · live model runs enabled" : "Your account · read-only: live runs not granted yet"}>
        <span className="account-dot" aria-hidden="true">{me.name.slice(0, 1).toUpperCase()}</span>{me.name}
        <span className="meta-text">{me.live ? " · live" : " · read-only"}</span>
      </Link>
      <button type="button" className="btn btn-quiet btn-sm" onClick={signOut}>Sign out</button>
    </>
  );
}
