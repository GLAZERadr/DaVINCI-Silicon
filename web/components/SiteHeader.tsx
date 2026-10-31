import Link from "next/link";
import Logo from "./Logo";

// 16px line icons in the spirit of GitHub's Octicons, drawn for DaVINCI.
const ICON: Record<string, React.ReactNode> = {
  evidence: <path d="M8 1.5 2.5 3.8v3.9c0 3.3 2.3 5.9 5.5 6.8 3.2-.9 5.5-3.5 5.5-6.8V3.8L8 1.5Zm-2.3 6.6 1.6 1.6 3.1-3.3" />,
  console: <path d="M2 3h12v10H2zM4.5 6.5 6.5 8l-2 1.5M8 10h3.5" />,
  new: <path d="M5 3.2v9.6L12.5 8 5 3.2Z" />,
  spec: <path d="M4 1.8h5.2L12 4.6v9.6H4zM9 1.8v3h3M6 8h4M6 10.5h4" />,
};

const NAV = [
  { href: "/", label: "Evidence", key: "evidence" },
  { href: "/console/", label: "Run Console", key: "console" },
  { href: "/new/", label: "New run", key: "new" },
  { href: "/spec/", label: "Spec intake", key: "spec" },
] as const;

export type Section = (typeof NAV)[number]["key"];

export function Icon({ name }: { name: keyof typeof ICON }) {
  return (
    <svg className="icon" width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" focusable="false"
      fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
      {ICON[name]}
    </svg>
  );
}

export default function SiteHeader({ active, crumbs = [], children }:
  { active: Section; crumbs?: { label: string; href?: string }[]; children?: React.ReactNode }) {
  return (
    <header className="header">
      <div className="topbar">
        <Link href="/" className="wordmark" aria-label="DaVINCI home"><Logo /></Link>
        <nav className="crumbs" aria-label="Breadcrumb">
          <span className="crumb-sep" aria-hidden="true">/</span>
          <Link href="/">sync_fifo</Link>
          {crumbs.map((c) => (
            <span key={c.label} className="crumb">
              <span className="crumb-sep" aria-hidden="true">/</span>
              {c.href ? <Link href={c.href}>{c.label}</Link> : <strong>{c.label}</strong>}
            </span>
          ))}
        </nav>
        <div className="header-actions">{children}</div>
      </div>
      <nav className="tabs" aria-label="Sections">
        {NAV.map((n) => (
          <Link key={n.key} href={n.href} aria-current={n.key === active ? "page" : undefined}>
            <Icon name={n.key} />{n.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
