"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, api, sessionToken, setSessionToken } from "@/lib/api";

// Header account control: Sign in / Sign up, or the signed-in name with Sign out.
export default function AccountButton() {
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
  }

  if (me === undefined) return null; // storage is read after mount
  if (!me) return (
    <>
      <Link href="/login/" className="btn btn-quiet btn-sm">Sign in</Link>
      <Link href="/register/" className="btn btn-sm">Sign up</Link>
    </>
  );
  return (
    <>
      <span className="account-name" title={me.live ? "live model runs enabled" : "read-only: live runs not granted yet"}>
        <span className="account-dot" aria-hidden="true">{me.name.slice(0, 1).toUpperCase()}</span>{me.name}
        <span className="meta-text">{me.live ? " · live" : " · read-only"}</span>
      </span>
      <button type="button" className="btn btn-quiet btn-sm" onClick={signOut}>Sign out</button>
    </>
  );
}
