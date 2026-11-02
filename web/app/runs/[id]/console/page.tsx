import type { Metadata } from "next";
import Link from "next/link";
import Console from "@/components/Console";
import SiteHeader from "@/components/SiteHeader";
import { consoleRuns, requirementsFor, runList, triage } from "@/lib/evidence";

export function generateStaticParams() {
  return runList().map((r) => ({ id: r.id }));
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  return { title: `${id} · Run Console · DaVINCI` };
}

export default async function RunConsole({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const runs = consoleRuns(id);
  return (
    <>
      <SiteHeader active="console" crumbs={[{ label: id, href: `/runs/${id}/` }, { label: "console" }]} />
      <nav className="subbar" aria-label="Recorded runs">
        {runList().map((r) => (
          <Link key={r.id} href={`/runs/${r.id}/console/`} aria-current={r.id === id ? "page" : undefined}>{r.id}</Link>
        ))}
        <Link className="subbar-end" href={`/runs/${id}/`}>Evidence for {id} →</Link>
      </nav>
      <Console runs={runs} requirements={requirementsFor(runs[0].run)} triage={triage()} />
    </>
  );
}
