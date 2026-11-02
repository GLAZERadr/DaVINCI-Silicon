"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import AccountButton from "./AccountButton";
import Logo from "./Logo";

// App shell: a left sidebar (sections + profile) and a slim breadcrumb bar above the page.
// On narrow screens the sidebar becomes a drawer opened from the bar.

// 16px line icons in the spirit of GitHub's Octicons, drawn for DaVINCI.
const ICON: Record<string, React.ReactNode> = {
  evidence: <path d="M8 1.5 2.5 3.8v3.9c0 3.3 2.3 5.9 5.5 6.8 3.2-.9 5.5-3.5 5.5-6.8V3.8L8 1.5Zm-2.3 6.6 1.6 1.6 3.1-3.3" />,
  console: <path d="M2 3h12v10H2zM4.5 6.5 6.5 8l-2 1.5M8 10h3.5" />,
  new: <path d="M5 3.2v9.6L12.5 8 5 3.2Z" />,
  spec: <path d="M4 1.8h5.2L12 4.6v9.6H4zM9 1.8v3h3M6 8h4M6 10.5h4" />,
  access: <path d="M8 1.8a3 3 0 1 1 0 6 3 3 0 0 1 0-6ZM2.8 14.2c.6-2.6 2.6-4.2 5.2-4.2s4.6 1.6 5.2 4.2" />,
  menu: <path d="M2.5 4h11M2.5 8h11M2.5 12h11" />,
  close: <path d="M3.5 3.5l9 9M12.5 3.5l-9 9" />,
};

const NAV = [
  { href: "/evidence/", label: "Evidence", key: "evidence" },
  { href: "/console/", label: "Run Console", key: "console" },
  { href: "/new/", label: "New run", key: "new" },
  { href: "/spec/", label: "Spec intake", key: "spec" },
] as const;

export type Section = (typeof NAV)[number]["key"] | "account" | "access";

export function Icon({ name }: { name: keyof typeof ICON }) {
  return (
    <svg className="icon" width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" focusable="false"
      fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
      {ICON[name]}
    </svg>
  );
}

export default function SiteHeader({ active, crumbs = [], children }:
  { active?: Section; crumbs?: { label: string; href?: string }[]; children?: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open) return;
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [open]);
  const section = active ?? (crumbs[0]?.label === "account" ? "account" : crumbs[0]?.label === "request access" ? "access" : undefined);

  return (
    <>
      <aside className={`sidebar${open ? " open" : ""}`} aria-label="DaVINCI">
        <div className="sb-top">
          <Link href="/" className="wordmark" aria-label="DaVINCI Silicon home"><Logo /></Link>
          <button type="button" className="sb-close" onClick={() => setOpen(false)} aria-label="Close menu"><Icon name="close" /></button>
        </div>
        <p className="sb-block">sync_fifo</p>
        <nav className="sb-nav" aria-label="Sections">
          {NAV.map((n) => (
            <Link key={n.key} href={n.href} aria-current={n.key === section ? "page" : undefined} onClick={() => setOpen(false)}>
              <Icon name={n.key} />{n.label}
            </Link>
          ))}
        </nav>
        <nav className="sb-nav sb-nav-2" aria-label="More">
          <Link href="/access/" aria-current={section === "access" ? "page" : undefined}><Icon name="access" />Request access</Link>
        </nav>
        <div className="sb-bottom"><AccountButton active={section === "account"} /></div>
      </aside>
      {open && <div className="sb-scrim" onClick={() => setOpen(false)} aria-hidden="true" />}

      <header className="appbar">
        <button type="button" className="sb-open" onClick={() => setOpen(true)} aria-label="Open menu" aria-expanded={open}><Icon name="menu" /></button>
        <nav className="crumbs" aria-label="Breadcrumb">
          <Link href="/evidence/">sync_fifo</Link>
          {crumbs.map((c) => (
            <span key={c.label} className="crumb">
              <span className="crumb-sep" aria-hidden="true">/</span>
              {c.href ? <Link href={c.href}>{c.label}</Link> : <strong>{c.label}</strong>}
            </span>
          ))}
        </nav>
        {children && <div className="header-actions">{children}</div>}
      </header>
    </>
  );
}
