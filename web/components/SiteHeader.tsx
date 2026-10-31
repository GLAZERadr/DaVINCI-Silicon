import Link from "next/link";
import Logo from "./Logo";

const NAV = [
  { href: "/", label: "Evidence", key: "evidence" },
  { href: "/console/", label: "Run Console", key: "console" },
  { href: "/new/", label: "New run", key: "new" },
  { href: "/spec/", label: "Spec intake", key: "spec" },
] as const;

export type Section = (typeof NAV)[number]["key"];

export default function SiteHeader({ active, children }: { active: Section; children?: React.ReactNode }) {
  return (
    <header className="header">
      <div className="header-row">
        <Link href="/" className="wordmark" aria-label="DaVINCI home"><Logo /></Link>
        <nav className="site-nav" aria-label="Sections">
          {NAV.map((n) => (
            <Link key={n.key} href={n.href} aria-current={n.key === active ? "page" : undefined}>{n.label}</Link>
          ))}
        </nav>
        <div className="header-actions">{children}</div>
      </div>
      <div className="rule" aria-hidden="true" />
    </header>
  );
}
