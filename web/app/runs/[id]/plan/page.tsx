import type { Metadata } from "next";
import Link from "next/link";
import PlanView from "@/components/PlanView";
import SiteHeader from "@/components/SiteHeader";
import { planBundle, runList } from "@/lib/evidence";

export function generateStaticParams() {
  return runList().filter((r) => planBundle(r.id)).map((r) => ({ id: r.id }));
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  return { title: `${id} · Verification plan · DaVINCI Silicon` };
}

export default async function RunPlan({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const b = planBundle(id)!;
  return (
    <>
      <SiteHeader active="evidence" crumbs={[{ label: id, href: `/runs/${id}/` }, { label: "verification plan" }]} />
      <main className="board plan-page">
        <section className="title-block">
          <p className="eyebrow">Verification plan · {b.plan.date} · {b.planId}{b.planId !== id ? ` (re-checked replay of ${id})` : ""}</p>
          <h1 className="display-title">{b.plan.signoff.filter((l: { status: string }) => l.status === "met").length} of {b.plan.signoff.length} sign-off criteria met. <span className="tone-2">{b.plan.testpoints.length} testpoints traced to frozen tests, planted bugs and measured results.</span></h1>
          <p className="meta-text"><Link href={`/runs/${id}/`}>← Evidence for {id}</Link></p>
        </section>
        <PlanView plan={b.plan} csv={b.csv} hjson={b.hjson} planId={b.planId} />
      </main>
    </>
  );
}
