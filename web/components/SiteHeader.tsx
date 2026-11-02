"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import AccountButton from "./AccountButton";
import Logo from "./Logo";

// App shell: a left sidebar (sections + profile) and a slim breadcrumb bar above the page.
// On wide screens the sidebar can be collapsed to an icon rail or closed and reopened from the
// bar (remembered per browser, Ctrl/Cmd+B toggles). On narrow screens it is a drawer.

// 16px line icons in the spirit of GitHub's Octicons, drawn for DaVINCI.
const ICON: Record<string, React.ReactNode> = {
  evidence: <path d="M8 1.5 2.5 3.8v3.9c0 3.3 2.3 5.9 5.5 6.8 3.2-.9 5.5-3.5 5.5-6.8V3.8L8 1.5Zm-2.3 6.6 1.6 1.6 3.1-3.3" />,
  console: <path d="M2 3h12v10H2zM4.5 6.5 6.5 8l-2 1.5M8 10h3.5" />,
  new: <path d="M5 3.2v9.6L12.5 8 5 3.2Z" />,
  spec: <path d="M4 1.8h5.2L12 4.6v9.6H4zM9 1.8v3h3M6 8h4M6 10.5h4" />,
  menu: <path d="M2.5 4h11M2.5 8h11M2.5 12h11" />,
  close: <path d="M3.5 3.5l9 9M12.5 3.5l-9 9" />,
  collapse: <path d="M2.5 2.5h11v11h-11zM6 2.5v11M11 6 9 8l2 2" />,
  expand: <path d="M2.5 2.5h11v11h-11zM6 2.5v11M9 6l2 2-2 2" />,
};

type Mode = "expanded" | "collapsed" | "closed";
const MODE_KEY = "davinci.sidebar";
const narrow = () => typeof window !== "undefined" && window.matchMedia("(max-width: 900px)").matches;
const typing = (t: EventTarget | null) =>
  t instanceof HTMLElement && (t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName));

const NAV = [
  { href: "/evidence/", label: "Evidence", key: "evidence" },
  { href: "/console/", label: "Run Console", key: "console" },
  { href: "/new/", label: "New run", key: "new" },
  { href: "/spec/", label: "Spec intake", key: "spec" },
] as const;

export type Section = (typeof NAV)[number]["key"] | "account";

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
  const [open, setOpen] = useState(false); // narrow screens: drawer
  const [mode, setModeState] = useState<Mode>("expanded"); // wide screens
  const setMode = (m: Mode) => {
    setModeState(m);
    try { localStorage.setItem(MODE_KEY, m); } catch {}
  };
  useEffect(() => {
    try {
      const m = localStorage.getItem(MODE_KEY);
      if (m === "collapsed" || m === "closed") setModeState(m);
    } catch {}
  }, []);
  useEffect(() => {
    document.documentElement.dataset.sidebar = mode;
  }, [mode]);
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) setOpen(false);
      if (e.key.toLowerCase() === "b" && (e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && !typing(e.target)) {
        e.preventDefault();
        if (narrow()) setOpen((o) => !o);
        else setMode(mode === "expanded" ? "collapsed" : "expanded");
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [open, mode]);
  const close = () => (narrow() ? setOpen(false) : setMode("closed"));
  const reopen = () => (narrow() ? setOpen(true) : setMode("expanded"));
  const collapsed = mode === "collapsed";
  const section = active ?? (crumbs[0]?.label === "account" ? "account" : undefined);

  return (
    <>
      <aside id="app-sidebar" className={`sidebar${open ? " open" : ""}`} aria-label="DaVINCI">
        <div className="sb-top">
          <Link href="/" className="wordmark" aria-label="DaVINCI Silicon home"><Logo /></Link>
          <button type="button" className="sb-close" onClick={close} aria-label="Close sidebar"><Icon name="close" /></button>
        </div>
        <p className="sb-block">sync_fifo</p>
        <nav className="sb-nav" aria-label="Sections">
          {NAV.map((n) => (
            <Link key={n.key} href={n.href} aria-current={n.key === section ? "page" : undefined} onClick={() => setOpen(false)}
              title={collapsed ? n.label : undefined}>
              <Icon name={n.key} /><span className="sb-label">{n.label}</span>
            </Link>
          ))}
        </nav>
        <div className="sb-tools">
          <button type="button" className="sb-tool" onClick={() => setMode(collapsed ? "expanded" : "collapsed")}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} aria-expanded={!collapsed} aria-controls="app-sidebar"
            title={`${collapsed ? "Expand" : "Collapse"} sidebar (Ctrl+B)`}>
            <Icon name={collapsed ? "expand" : "collapse"} /><span className="sb-label">{collapsed ? "Expand" : "Collapse"}</span>
          </button>
          {!collapsed && (
            <button type="button" className="sb-tool" onClick={close} aria-label="Hide sidebar" title="Hide sidebar (reopen from the bar)">
              <Icon name="close" /><span className="sb-label">Hide</span>
            </button>
          )}
        </div>
        <div className="sb-bottom"><AccountButton active={section === "account"} /></div>
      </aside>
      {open && <div className="sb-scrim" onClick={() => setOpen(false)} aria-hidden="true" />}

      <header className="appbar">
        <button type="button" className="sb-open" onClick={reopen} aria-label="Open sidebar" aria-controls="app-sidebar"
          aria-expanded={open} title="Open sidebar (Ctrl+B)"><Icon name="menu" /></button>
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
